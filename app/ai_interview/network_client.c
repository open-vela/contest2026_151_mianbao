/*
 * AI模拟面试官 — 网络通信模块
 * 负责：A同学
 *
 * 端侧 -> 云端：POST /api/interview，body 为 JSON，音频以 base64 内嵌
 * 云端 -> 端侧：JSON，tts_audio 为 base64 编码的 WAV
 *
 * 依赖（R528 板级配置已具备，无需改 defconfig）：
 *   CONFIG_LIB_CURL            HTTP 客户端（连带 CRYPTO_MBEDTLS / LIB_ZLIB）
 *   CONFIG_NETUTILS_CJSON      JSON 解析
 *   mbedtls/base64.h           base64 编解码（由 CONFIG_LIB_CURL 间接引入）
 *
 * 注意：libcurl 需要 200KB 量级的栈（参考 CONFIG_EXAMPLES_HTTP_STACKSIZE=204800）。
 * 本应用主任务栈已提到 32768，网络调用务必在工作线程（栈 262144）里执行。
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <curl/curl.h>
#include "netutils/cJSON.h"
#include <mbedtls/base64.h>

#include "network_client.h"
#include "app_config.h"

/* 单次响应上限：24kHz 单声道 WAV 的 base64 约 10 秒 640KB，留足余量 */
#define CLOUD_RESP_MAX  (8u * 1024u * 1024u)

/* 请求路径：只配 base URL，路径写死在这里避免两处配置漂移 */
#define CLOUD_PATH_INTERVIEW  "/api/interview"
#define CLOUD_PATH_HEALTH     "/api/health"

static char g_url_interview[192];
static char g_url_health[192];
static int  g_initialized = 0;

/* ---------- 响应缓冲 ---------- */

struct mem_chunk {
    char  *memory;
    size_t size;
};

static size_t write_memory_cb(void *contents, size_t size, size_t nmemb,
                              void *userp)
{
    size_t realsize = size * nmemb;
    struct mem_chunk *mem = (struct mem_chunk *)userp;
    char *ptr;

    /* 超限返回 0 让 curl 以 CURLE_WRITE_ERROR 中止，而不是把内存吃光 */
    if (mem->size + realsize > CLOUD_RESP_MAX) {
        printf("[Cloud] 响应超过上限 %u 字节，中止\n", (unsigned)CLOUD_RESP_MAX);
        return 0;
    }

    ptr = realloc(mem->memory, mem->size + realsize + 1);
    if (ptr == NULL) {
        printf("[Cloud] 响应缓冲分配失败\n");
        return 0;
    }

    mem->memory = ptr;
    memcpy(&(mem->memory[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->memory[mem->size] = '\0';

    return realsize;
}

/* ---------- 初始化 ---------- */

void cloud_init(void)
{
    const char *base;

    if (g_initialized) {
        return;
    }

    curl_global_init(CURL_GLOBAL_ALL);

    base = app_cloud_base_url();
    snprintf(g_url_interview, sizeof(g_url_interview), "%s%s",
             base, CLOUD_PATH_INTERVIEW);
    snprintf(g_url_health, sizeof(g_url_health), "%s%s",
             base, CLOUD_PATH_HEALTH);

    printf("[Cloud] 云端接口: %s\n", g_url_interview);

    g_initialized = 1;
}

/* ---------- 健康检查 ---------- */

int cloud_health_check(void)
{
    CURL *curl;
    CURLcode res;
    struct mem_chunk chunk;
    long status = 0;
    int ret = CLOUD_ERR_HTTP;

    cloud_init();

    chunk.memory = malloc(1);
    if (chunk.memory == NULL) {
        return CLOUD_ERR_NOMEM;
    }
    chunk.size = 0;

    curl = curl_easy_init();
    if (curl == NULL) {
        free(chunk.memory);
        return CLOUD_ERR_HTTP;
    }

    curl_easy_setopt(curl, CURLOPT_URL, g_url_health);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_memory_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

    res = curl_easy_perform(curl);
    if (res == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
        if (status >= 200 && status < 300) {
            ret = CLOUD_OK;
        }
    } else {
        printf("[Cloud] 健康检查失败: %s\n", curl_easy_strerror(res));
    }

    curl_easy_cleanup(curl);
    free(chunk.memory);

    printf("[Cloud] 健康检查 HTTP %ld -> %s\n", status,
           ret == CLOUD_OK ? "云端在线" : "云端不可达");
    return ret;
}

/* ---------- 响应解析 ---------- */

/* 从 JSON 里取字符串字段并复制一份堆内存；字段缺失返回 NULL（不算错误） */
static char *dup_string_field(const cJSON *root, const char *name)
{
    const cJSON *item = cJSON_GetObjectItem(root, name);
    size_t len;
    char *out;

    if (!cJSON_IsString(item) || item->valuestring == NULL) {
        return NULL;
    }

    len = strlen(item->valuestring);
    out = malloc(len + 1);
    if (out == NULL) {
        return NULL;
    }

    memcpy(out, item->valuestring, len + 1);
    return out;
}

/*
 * 失败时统一从这里返回：释放已分配字段并把 resp 归零，
 * 保证调用者无论成败都可以安全地调 cloud_response_free()，
 * 也保证错误路径不会留下半成品结构体。
 */
static int parse_fail(cloud_response_t *resp, int err)
{
    free(resp->text);
    free(resp->user_text);
    free(resp->tts_wav);
    memset(resp, 0, sizeof(*resp));
    return err;
}

int cloud_parse_response(const char *body, size_t len, cloud_response_t *resp)
{
    cJSON *root;
    const cJSON *item;
    size_t b64_len;
    size_t wav_len = 0;
    unsigned char *wav;
    int rc;

    if (body == NULL || resp == NULL || len == 0) {
        return CLOUD_ERR_JSON;
    }

    root = cJSON_ParseWithLength(body, len);
    if (root == NULL) {
        printf("[Cloud] 响应不是合法 JSON\n");
        return CLOUD_ERR_JSON;
    }

    /* session_id / next_action 是定长字段，直接拷进结构体 */
    item = cJSON_GetObjectItem(root, "session_id");
    if (cJSON_IsString(item) && item->valuestring != NULL) {
        strncpy(resp->session_id, item->valuestring,
                sizeof(resp->session_id) - 1);
        resp->session_id[sizeof(resp->session_id) - 1] = '\0';
    }

    item = cJSON_GetObjectItem(root, "next_action");
    if (cJSON_IsString(item) && item->valuestring != NULL) {
        strncpy(resp->next_action, item->valuestring,
                sizeof(resp->next_action) - 1);
        resp->next_action[sizeof(resp->next_action) - 1] = '\0';
    }

    resp->text = dup_string_field(root, "text");
    resp->user_text = dup_string_field(root, "user_text");

    /*
     * 防线 2：tts_audio 必须存在、是字符串、且非空。
     *
     * 云端在缺 MIMO_API_KEY 时会返回 HTTP 200 但 tts_audio 为空串，
     * 若这里放过，端侧会一路"成功"到播放环节却没有声音——演示时最难查。
     */
    item = cJSON_GetObjectItem(root, "tts_audio");
    if (!cJSON_IsString(item) || item->valuestring == NULL ||
        item->valuestring[0] == '\0') {
        /* text 里通常有云端给的兜底文案，打到串口便于定位 */
        printf("[Cloud] 响应缺少 tts_audio（云端可能未配置 API key）: %s\n",
               resp->text ? resp->text : "(无 text)");
        cJSON_Delete(root);
        return parse_fail(resp, CLOUD_ERR_EMPTY_TTS);
    }

    b64_len = strlen(item->valuestring);

    /* 先探解码后长度，再分配：mbedtls 在缓冲不足时回填所需大小 */
    rc = mbedtls_base64_decode(NULL, 0, &wav_len,
                               (const unsigned char *)item->valuestring, b64_len);
    if (rc != 0 && rc != MBEDTLS_ERR_BASE64_BUFFER_TOO_SMALL) {
        printf("[Cloud] tts_audio 不是合法 base64\n");
        cJSON_Delete(root);
        return parse_fail(resp, CLOUD_ERR_BAD_AUDIO);
    }

    if (wav_len < 60) {  /* 44 字节头 + 至少一点数据 */
        cJSON_Delete(root);
        return parse_fail(resp, CLOUD_ERR_BAD_AUDIO);
    }

    wav = malloc(wav_len);
    if (wav == NULL) {
        cJSON_Delete(root);
        return parse_fail(resp, CLOUD_ERR_NOMEM);
    }

    rc = mbedtls_base64_decode(wav, wav_len, &wav_len,
                               (const unsigned char *)item->valuestring, b64_len);
    cJSON_Delete(root);  /* 后续不再需要 JSON 树，尽早释放 */

    if (rc != 0) {
        free(wav);
        return parse_fail(resp, CLOUD_ERR_BAD_AUDIO);
    }

    /*
     * 防线 3：解码后必须是 WAV。
     * 云端异常时 tts_audio 里可能是错误文本或 HTML，直接送播放器会放出噪声。
     */
    if (wav_len < 44 || memcmp(wav, "RIFF", 4) != 0 ||
        memcmp(wav + 8, "WAVE", 4) != 0) {
        printf("[Cloud] tts_audio 解码后不是 WAV\n");
        free(wav);
        return parse_fail(resp, CLOUD_ERR_BAD_AUDIO);
    }

    resp->tts_wav = wav;
    resp->tts_wav_len = wav_len;

    return CLOUD_OK;
}

/* ---------- 主请求 ---------- */

int cloud_send_audio(const cloud_request_t *req, cloud_response_t *resp)
{
    CURL *curl = NULL;
    struct curl_slist *headers = NULL;
    struct mem_chunk chunk;
    CURLcode res;
    long status = 0;
    char *b64 = NULL;
    char *body = NULL;
    size_t b64_cap;
    size_t b64_len = 0;
    size_t body_cap;
    const char *sid;
    int ret;

    if (req == NULL || resp == NULL || req->wav == NULL || req->wav_len == 0) {
        return CLOUD_ERR_JSON;
    }

    cloud_init();

    memset(resp, 0, sizeof(*resp));
    chunk.memory = malloc(1);
    if (chunk.memory == NULL) {
        return CLOUD_ERR_NOMEM;
    }
    chunk.size = 0;

    /*
     * base64 编码。mbedtls 会在末尾写 '\0'，所以容量要 +1。
     * 用 mbedtls 而不是 apps/netutils/codecs：后者需要 CONFIG_CODECS_BASE64，
     * 而该配置在板级 defconfig 里没开，且 defconfig 不在本仓库内。
     */
    b64_cap = 4 * ((req->wav_len + 2) / 3) + 1;
    b64 = malloc(b64_cap);
    if (b64 == NULL) {
        ret = CLOUD_ERR_NOMEM;
        goto out;
    }

    if (mbedtls_base64_encode((unsigned char *)b64, b64_cap, &b64_len,
                              req->wav, req->wav_len) != 0) {
        printf("[Cloud] 音频 base64 编码失败\n");
        ret = CLOUD_ERR_NOMEM;
        goto out;
    }

    /*
     * 手写拼 JSON，不用 cJSON_Print：后者会把 1MB 级的 base64 串再复制转义
     * 一遍，峰值内存翻倍。
     * 无需转义——session_id 是 uuid、role 是固定常量、base64 只含 A-Za-z0-9+/=。
     * history 恒为空数组：多轮上下文由云端按 session_id 维护。
     */
    sid = (req->session_id != NULL) ? req->session_id : "";
    body_cap = b64_len + strlen(sid) + strlen(req->role) +
               strlen(req->state) + 256;
    body = malloc(body_cap);
    if (body == NULL) {
        ret = CLOUD_ERR_NOMEM;
        goto out;
    }

    snprintf(body, body_cap,
             "{\"session_id\":\"%s\",\"audio\":\"%s\",\"audio_format\":\"wav\","
             "\"role\":\"%s\",\"state\":\"%s\",\"history\":[]}",
             sid, b64, req->role, req->state);

    /* body 已拼好，立刻释放 base64 缓冲，降低峰值内存 */
    free(b64);
    b64 = NULL;

    curl = curl_easy_init();
    if (curl == NULL) {
        ret = CLOUD_ERR_HTTP;
        goto out;
    }

    /*
     * 两个头缺一不可：
     *   Content-Type  缺了 Flask 的 request.get_json() 返回 None，云端直接回
     *                 400「请求体不能为空」，很容易误判成音频格式问题
     *   Expect:       抑制 100-continue，否则 body 超过 1KB 时 curl 会先发
     *                 Expect 头等待应答，白等 1 秒甚至失败
     */
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers, "Expect:");

    curl_easy_setopt(curl, CURLOPT_URL, g_url_interview);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)strlen(body));
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_memory_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);
    /* 云端要串行跑 ASR + LLM + TTS，实测可能十几秒，给足余量 */
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 120L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    /*
     * TLS 证书校验默认是打开的（libcurl 默认行为）。
     *
     * 注意：板级 rootfs 里没有任何 CA 根证书
     * （CONFIG_LIB_CURL_CA_PATH 默认 /etc/ssl/curl，该路径不存在），
     * 因此走 https:// 时校验必然失败。
     *
     * 两条出路 —— 优先前者：
     *   1. 在设备上放一份 CA bundle，并把 CURLOPT_CAINFO 指过去
     *   2. 显式打开 APP_AI_INTERVIEW_TLS_INSECURE 跳过校验
     *      （仅适用于连自己的服务，演示用；不要长期开着）
     *
     * 用 http:// 时这里完全没有影响。
     */
#if defined(CONFIG_APP_AI_INTERVIEW_TLS_INSECURE)
    printf("[Cloud] 警告: 已跳过 TLS 证书校验\n");
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
#endif

    res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        printf("[Cloud] 上传失败: %s\n", curl_easy_strerror(res));
        resp->http_status = 0;
        ret = CLOUD_ERR_HTTP;
        goto out;
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    resp->http_status = status;

    /* 防线 1：HTTP 状态码 */
    if (status < 200 || status >= 300) {
        printf("[Cloud] 云端返回 HTTP %ld\n", status);
        ret = CLOUD_ERR_HTTP;
        goto out;
    }

    /* 防线 2、3 都在 cloud_parse_response 内，保持判定逻辑单点 */
    ret = cloud_parse_response(chunk.memory, chunk.size, resp);
    resp->http_status = status;

    if (ret == CLOUD_OK) {
        printf("[Cloud] 本轮成功: %u 字节 WAV, next_action=%s\n",
               (unsigned)resp->tts_wav_len,
               resp->next_action[0] ? resp->next_action : "?");
    }

out:
    if (headers != NULL) {
        curl_slist_free_all(headers);
    }
    if (curl != NULL) {
        curl_easy_cleanup(curl);
    }
    free(b64);
    free(body);
    free(chunk.memory);
    return ret;
}

/* ---------- 清理 ---------- */

void cloud_response_free(cloud_response_t *resp)
{
    if (resp == NULL) {
        return;
    }

    free(resp->text);
    free(resp->user_text);
    free(resp->tts_wav);

    memset(resp, 0, sizeof(*resp));
}
