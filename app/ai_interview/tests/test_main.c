/*
 * cloud_parse_response 的 PC 端单元测试
 *
 * 编译时把真实的 network_client.c 与树里的 cJSON / mbedtls base64 一起编进来，
 * 不走桩、不复制逻辑 —— 测的就是端侧将来真正跑的那份代码。
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "network_client.h"

static int g_fail = 0;

static char *read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    long n;
    char *buf;

    if (f == NULL) {
        printf("  (无法打开 %s)\n", path);
        return NULL;
    }

    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);

    buf = malloc((size_t)n + 1);
    if (buf == NULL || fread(buf, 1, (size_t)n, f) != (size_t)n) {
        fclose(f);
        free(buf);
        return NULL;
    }

    buf[n] = '\0';
    fclose(f);
    *len = (size_t)n;
    return buf;
}

static void expect(const char *name, int want, int got)
{
    int ok = (want == got);

    printf("%s  %-26s 期望 %2d  实际 %2d\n",
           ok ? "PASS" : "FAIL", name, want, got);
    if (!ok) {
        g_fail++;
    }
}

int main(int argc, char **argv)
{
    const char *dir = (argc > 1) ? argv[1] : ".";
    char path[512];
    size_t len;
    char *body;
    cloud_response_t resp;
    int rc;

    /* ---- 用例 1：正常响应 ---- */
    printf("\n[1] 正常响应\n");
    snprintf(path, sizeof(path), "%s/sample_ok.json", dir);
    body = read_file(path, &len);
    if (body != NULL) {
        memset(&resp, 0, sizeof(resp));
        rc = cloud_parse_response(body, len, &resp);
        expect("返回码", CLOUD_OK, rc);
        if (rc == CLOUD_OK) {
            printf("       session_id=%s\n", resp.session_id);
            printf("       next_action=%s\n", resp.next_action);
            printf("       text=%.36s\n", resp.text ? resp.text : "(null)");
            printf("       user_text=%.36s\n",
                   resp.user_text ? resp.user_text : "(null)");
            printf("       tts_wav=%zu 字节\n", resp.tts_wav_len);
            expect("  WAV 魔数 RIFF", 0, memcmp(resp.tts_wav, "RIFF", 4));
            expect("  WAV 魔数 WAVE", 0, memcmp(resp.tts_wav + 8, "WAVE", 4));
        }
        cloud_response_free(&resp);
        free(body);
    }

    /* ---- 用例 2：空 tts_audio（缺 API key 时云端的真实行为，实测抓取）---- */
    printf("\n[2] 空 tts_audio（缺 API key 的真实响应）\n");
    snprintf(path, sizeof(path), "%s/sample_empty_tts.json", dir);
    body = read_file(path, &len);
    if (body != NULL) {
        memset(&resp, 0, sizeof(resp));
        rc = cloud_parse_response(body, len, &resp);
        expect("返回码必须为 EMPTY_TTS", CLOUD_ERR_EMPTY_TTS, rc);
        expect("  tts_wav 未被分配", 1, resp.tts_wav == NULL);
        expect("  失败时结构体已清空", 1, resp.text == NULL && resp.user_text == NULL);
        cloud_response_free(&resp);
        free(body);
    }

    /* ---- 用例 3：服务端错误结构 ---- */
    printf("\n[3] 服务端 error 响应\n");
    snprintf(path, sizeof(path), "%s/sample_error.json", dir);
    body = read_file(path, &len);
    if (body != NULL) {
        memset(&resp, 0, sizeof(resp));
        rc = cloud_parse_response(body, len, &resp);
        expect("返回码必须为 EMPTY_TTS", CLOUD_ERR_EMPTY_TTS, rc);
        expect("  失败时结构体已清空", 1, resp.text == NULL && resp.user_text == NULL);
        expect("  重复 free 安全", 1, (cloud_response_free(&resp), 1));
        cloud_response_free(&resp);
        free(body);
    }

    /* ---- 用例 4：非 JSON（网关返回 HTML）---- */
    printf("\n[4] 非 JSON（HTML 错误页）\n");
    snprintf(path, sizeof(path), "%s/sample_html.json", dir);
    body = read_file(path, &len);
    if (body != NULL) {
        memset(&resp, 0, sizeof(resp));
        rc = cloud_parse_response(body, len, &resp);
        expect("返回码必须为 JSON", CLOUD_ERR_JSON, rc);
        cloud_response_free(&resp);
        free(body);
    }

    /* ---- 用例 5：空 body / NULL 入参 ---- */
    printf("\n[5] 边界入参\n");
    memset(&resp, 0, sizeof(resp));
    expect("空 body", CLOUD_ERR_JSON, cloud_parse_response(NULL, 0, &resp));
    expect("零长度", CLOUD_ERR_JSON, cloud_parse_response("", 0, &resp));
    cloud_response_free(&resp);
    cloud_response_free(NULL);  /* 不应崩溃 */

    printf("\n%s  失败 %d 项\n", g_fail == 0 ? "全部通过" : "存在失败", g_fail);
    return g_fail == 0 ? 0 : 1;
}
