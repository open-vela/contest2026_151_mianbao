/*
 * AI模拟面试官 — 主程序入口
 * 负责：A/B同学
 *
 * 线程模型：
 *   主线程     按键扫描 + LED 刷新 + 排空事件队列（100ms 节拍）
 *   工作线程   录音 -> 上传 -> 播放 三段阻塞流水线
 *
 * 约束：state_machine 只由主线程调用。原因见 state_machine.c —— 它的
 * post_event / update_led 全程无锁（read-modify-write + GPIO ioctl + 闪烁
 * 计数器），多线程投递会丢状态、LED 交错，且是偶发问题最难复现。
 * 工作线程只往事件队列里放事件，不碰状态机、不碰 GPIO。
 *
 * 为什么必须分线程：单轮上传实测要 22 秒，若在主循环里做，LED 会僵住 22 秒
 * ——"系统还在工作"的唯一反馈就没了，按键也全部失灵。
 */

#include <nuttx/config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <sys/ioctl.h>
#include <nuttx/ioexpander/gpio.h>

#include "state_machine.h"
#include "network_client.h"
#include "audio_io.h"
#include "app_config.h"

/* ---- 按键 GPIO ---- */
#define KEY1_GPIO  1   /* K1 开始面试 */
#define KEY2_GPIO  3   /* K2 取消/返回 */
#define KEY3_GPIO  4   /* K3 切换模式（暂未实现）*/

static int g_key1_fd = -1;
static int g_key2_fd = -1;
static int g_key3_fd = -1;

static int g_key1_last = 1;  /* 默认高电平（松开）*/
static int g_key2_last = 1;
static int g_key3_last = 1;

#define MAIN_LOOP_MS      100
#define UPLOAD_MAX_RETRY  2

/* ---- 主线程 -> 工作线程 ---- */
typedef enum {
    CMD_NONE = 0,
    CMD_START,      /* K1：开始一轮面试 */
    CMD_CANCEL      /* K2：取消 */
} app_cmd_t;

static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static app_cmd_t g_cmd = CMD_NONE;
static volatile int g_abort = 0;     /* 置 1 让录音/播放尽快退出 */
static int g_worker_busy = 0;

/* ---- 工作线程 -> 主线程 ---- */
#define EVQ_LEN 8
static system_event_t g_evq[EVQ_LEN];
static int g_evq_head = 0;
static int g_evq_tail = 0;

/* 跨线程只读的会话状态（在锁内更新）*/
static char g_session_id[64];
static char g_last_text[256];

/* ---------- 事件队列 ---------- */

/* 工作线程调用 */
static void app_post_event(system_event_t e)
{
    int next;

    pthread_mutex_lock(&g_lock);
    next = (g_evq_head + 1) % EVQ_LEN;
    if (next != g_evq_tail) {
        g_evq[g_evq_head] = e;
        g_evq_head = next;
    } else {
        printf("[Main] 警告: 事件队列已满，丢弃事件 %d\n", (int)e);
    }
    pthread_mutex_unlock(&g_lock);
}

/* 主线程调用 */
static int app_pop_event(system_event_t *e)
{
    int got = 0;

    pthread_mutex_lock(&g_lock);
    if (g_evq_tail != g_evq_head) {
        *e = g_evq[g_evq_tail];
        g_evq_tail = (g_evq_tail + 1) % EVQ_LEN;
        got = 1;
    }
    pthread_mutex_unlock(&g_lock);

    return got;
}

/* ---------- 流水线 ---------- */

static int upload_once(const uint8_t *wav, size_t wav_len, cloud_response_t *resp)
{
    cloud_request_t req;
    char sid[64];

    pthread_mutex_lock(&g_lock);
    strncpy(sid, g_session_id, sizeof(sid) - 1);
    sid[sizeof(sid) - 1] = '\0';
    pthread_mutex_unlock(&g_lock);

    req.session_id = sid;
    req.wav = wav;
    req.wav_len = wav_len;
    req.role = CONFIG_APP_AI_INTERVIEW_ROLE;
    req.state = "recording_finished";

    return cloud_send_audio(&req, resp);
}

static void run_one_round(void)
{
    uint8_t *wav = NULL;
    size_t wav_len = 0;
    cloud_response_t resp;
    ai_rec_result_t rec;
    int rc;
    int attempt;

    memset(&resp, 0, sizeof(resp));

    /* ---- 1. 录音 ---- */
    rec = audio_record_wav(&wav, &wav_len, &g_abort);
    if (rec != AI_REC_OK) {
        /* 三种失败都回到 IDLE：状态机里 RECORDING --ERROR--> IDLE */
        app_post_event(EVENT_ERROR);
        return;
    }

    app_post_event(EVENT_RECORD_DONE);   /* RECORDING -> UPLOADING */

    /* ---- 2. 上传（带重试）---- */
    rc = CLOUD_ERR_HTTP;
    for (attempt = 1; attempt <= UPLOAD_MAX_RETRY; attempt++) {
        rc = upload_once(wav, wav_len, &resp);
        if (rc == CLOUD_OK) {
            break;
        }
        printf("[Main] 上传失败(%d)，第 %d/%d 次: %d\n",
               rc, attempt, UPLOAD_MAX_RETRY, rc);
        if (rc == CLOUD_ERR_EMPTY_TTS) {
            break;      /* 云端缺 key 之类，重试没意义 */
        }
        sleep(1);
    }

    free(wav);
    wav = NULL;

    if (rc != CLOUD_OK) {
        cloud_response_free(&resp);
        app_post_event(EVENT_UPLOAD_FAIL);   /* -> ERROR 或 IDLE */
        return;
    }

    /* ---- 3. 记录会话状态，供下一轮回传 ---- */
    pthread_mutex_lock(&g_lock);
    if (resp.session_id[0] != '\0') {
        strncpy(g_session_id, resp.session_id, sizeof(g_session_id) - 1);
        g_session_id[sizeof(g_session_id) - 1] = '\0';
    }
    if (resp.text != NULL) {
        strncpy(g_last_text, resp.text, sizeof(g_last_text) - 1);
        g_last_text[sizeof(g_last_text) - 1] = '\0';
    }
    pthread_mutex_unlock(&g_lock);

    printf("[Main] 面试官: %s\n", resp.text ? resp.text : "(无文本)");

    app_post_event(EVENT_UPLOAD_SUCCESS);    /* UPLOADING -> PLAYING */

    /* ---- 4. 播放 ---- */
    (void)audio_play_wav(resp.tts_wav, resp.tts_wav_len, &g_abort);

    /* 面试结束则清空会话，下次 K1 开新面试 */
    if (strcmp(resp.next_action, "continue") != 0) {
        printf("[Main] 本轮面试结束（next_action=%s）\n", resp.next_action);
        pthread_mutex_lock(&g_lock);
        g_session_id[0] = '\0';
        pthread_mutex_unlock(&g_lock);
    }

    cloud_response_free(&resp);

    /*
     * 必须是本函数最后一条语句。
     * 若在 free 之前投递，主线程会立刻转 IDLE，用户马上按 K1 开下一轮，
     * 而本线程还在收尾 —— 下一轮录音与上一轮释放并发。
     */
    app_post_event(EVENT_PLAY_DONE);         /* PLAYING -> IDLE */
}

static void *pipeline_worker(void *arg)
{
    (void)arg;

    /* libcurl 一律只在本线程里用：它需要 200KB 量级的栈
     * （参考 CONFIG_EXAMPLES_HTTP_STACKSIZE 默认 204800），主任务栈
     * 远不够。cloud_init 也放这里，避免主线程先初始化造成竞争。 */
    cloud_init();

    printf("[Main] 云端健康检查...\n");
    if (cloud_health_check() != CLOUD_OK) {
        printf("[Main] 警告: 云端不可达，请检查 CLOUD_URL 与网络\n");
    }

    for (;;) {
        app_cmd_t cmd;

        pthread_mutex_lock(&g_lock);
        cmd = g_cmd;
        g_cmd = CMD_NONE;
        pthread_mutex_unlock(&g_lock);

        if (cmd != CMD_START) {
            usleep(MAIN_LOOP_MS * 1000 / 2);
            continue;
        }

        pthread_mutex_lock(&g_lock);
        g_worker_busy = 1;
        g_abort = 0;
        pthread_mutex_unlock(&g_lock);

        run_one_round();

        pthread_mutex_lock(&g_lock);
        g_worker_busy = 0;
        pthread_mutex_unlock(&g_lock);
    }

    return NULL;
}

/* ---------- 按键 ---------- */

static void init_buttons(void)
{
    g_key1_fd = open("/dev/gpio1", O_RDWR);
    if (g_key1_fd < 0) {
        printf("[Main] 警告: 无法打开 K1 GPIO (GPIO1)\n");
    } else {
        ioctl(g_key1_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K1 GPIO (GPIO1) 初始化成功\n");
    }

    g_key2_fd = open("/dev/gpio3", O_RDWR);
    if (g_key2_fd < 0) {
        printf("[Main] 警告: 无法打开 K2 GPIO (GPIO3)\n");
    } else {
        ioctl(g_key2_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K2 GPIO (GPIO3) 初始化成功\n");
    }

    g_key3_fd = open("/dev/gpio4", O_RDWR);
    if (g_key3_fd < 0) {
        printf("[Main] 警告: 无法打开 K3 GPIO (GPIO4)\n");
    } else {
        ioctl(g_key3_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K3 GPIO (GPIO4) 初始化成功\n");
    }
}

static int read_button(int fd)
{
    bool value = false;

    if (fd < 0) {
        return -1;
    }
    ioctl(fd, GPIOC_READ, (unsigned long)((uintptr_t)&value));
    return value ? 1 : 0;
}

static void check_buttons(void)
{
    int s1 = read_button(g_key1_fd);
    int s2 = read_button(g_key2_fd);
    int s3 = read_button(g_key3_fd);
    int busy;

    pthread_mutex_lock(&g_lock);
    busy = g_worker_busy;
    pthread_mutex_unlock(&g_lock);

    /* K1 下降沿：开始一轮。忙碌时忽略，避免重入 */
    if (s1 == 0 && g_key1_last == 1) {
        if (busy) {
            printf("[Main] K1 按下，但正在进行中，忽略\n");
        } else {
            printf("[Main] K1 按下 —— 开始面试\n");
            pthread_mutex_lock(&g_lock);
            g_cmd = CMD_START;
            pthread_mutex_unlock(&g_lock);
            state_machine_post_event(EVENT_BUTTON_PRESS);  /* -> RECORDING */
        }
    }
    g_key1_last = s1;

    /* K2 下降沿：取消。置 abort，工作线程会在 100ms 粒度内退出 */
    if (s2 == 0 && g_key2_last == 1) {
        printf("[Main] K2 按下 —— 取消\n");
        g_abort = 1;
        /* 不忙碌时说明停在 ERROR 态，按一下回 IDLE。
         * 状态机调用放在锁外：持锁做 ioctl/printf 没有必要。 */
        if (!busy) {
            state_machine_post_event(EVENT_BUTTON_PRESS);
        }
    }
    g_key2_last = s2;

    if (s3 == 0 && g_key3_last == 1) {
        printf("[Main] K3 按下（切换模式未实现）\n");
    }
    g_key3_last = s3;
}

/* ---------- 入口 ---------- */

int main(int argc, char *argv[])
{
    pthread_t tid;
    pthread_attr_t attr;

    (void)argc;
    (void)argv;

    printf("========================================\n");
    printf("  AI模拟面试官 - 端侧主程序 v0.2\n");
    printf("  队伍: mianbao (contest2026_151)\n");
    printf("========================================\n\n");

    state_machine_init();
    init_buttons();

    /* 流水线工作线程：栈必须够大，libcurl 要 200KB 量级。
     * 本函数内不得出现任何 curl 调用 —— 主任务栈放不下。 */
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, CONFIG_APP_AI_INTERVIEW_WORKER_STACKSIZE);
    if (pthread_create(&tid, &attr, pipeline_worker, NULL) != 0) {
        printf("[Main] 致命错误: 工作线程创建失败 (%d)\n", errno);
        return 1;
    }
    pthread_attr_destroy(&attr);

    printf("\n[Main] 系统就绪，等待按键开始面试...\n");
    printf("[Main] K1: 开始面试\n");
    printf("[Main] K2: 取消/返回\n");
    printf("[Main] K3: 切换模式\n\n");

    for (;;) {
        system_event_t ev;

        state_machine_update_led();
        check_buttons();

        /* 把工作线程投来的事件交给状态机 —— 只有主线程能碰它 */
        while (app_pop_event(&ev)) {
            state_machine_post_event(ev);
        }

        usleep(MAIN_LOOP_MS * 1000);
    }

    return 0;
}
