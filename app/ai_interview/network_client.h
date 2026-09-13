/*
 * AI模拟面试官 — 网络通信模块头文件
 * 负责：A同学
 *
 * 协议见 documents/api_protocol.md，服务端实现在 cloud/app.py。
 */

#ifndef __NETWORK_CLIENT_H__
#define __NETWORK_CLIENT_H__

#include <stddef.h>
#include <stdint.h>

/* 返回码：0 成功，负值为具体失败原因 */
#define CLOUD_OK               0
#define CLOUD_ERR_HTTP       (-1)   /* 传输失败 / HTTP 非 2xx */
#define CLOUD_ERR_JSON       (-2)   /* 响应体不是合法 JSON，或结构不符合协议 */
#define CLOUD_ERR_EMPTY_TTS  (-3)   /* tts_audio 字段缺失或为空串 */
#define CLOUD_ERR_BAD_AUDIO  (-4)   /* base64 解码后不是可播放的 WAV */
#define CLOUD_ERR_NOMEM      (-5)   /* 内存不足 */

/*
 * 返回码的可读名字，用于串口日志。
 * 原来日志里只有 "-1"、"-3" 这种数字，现场排查要回头翻头文件才知道是什么，
 * 演示时更没法一眼看出问题出在网络还是内容。
 */
const char *cloud_strerror(int rc);

/* 请求参数 */
typedef struct {
    const char    *session_id;  /* "" 或 NULL 表示让云端新建会话 */
    const uint8_t *wav;         /* 含 44 字节头的完整 WAV（不是裸 PCM） */
    size_t         wav_len;
    const char    *role;        /* 面试官角色，如 "产品经理" */
    const char    *state;       /* 录音结束固定传 "recording_finished" */
} cloud_request_t;

/*
 * 响应结果。
 * text / user_text / tts_wav 为堆内存，用完必须调 cloud_response_free()。
 */
typedef struct {
    char     session_id[64];    /* 多轮对话要回传；空串表示云端未返回 */
    char    *text;              /* 面试官回复文本，可为 NULL */
    char    *user_text;         /* ASR 识别结果（调试用），可为 NULL */
    uint8_t *tts_wav;           /* 已 base64 解码的 WAV，失败时为 NULL */
    size_t   tts_wav_len;
    char     next_action[16];   /* "continue" 继续面试 / "finish" 出报告 */
    long     http_status;       /* 便于串口排查：到底是网络还是内容的问题 */
} cloud_response_t;

/* 进程内一次性初始化（curl_global_init + 组装 URL），重复调用无副作用 */
void cloud_init(void);

/* 云端健康检查：0 可达，负值不可达 */
int cloud_health_check(void);

/*
 * 上行音频并取回本轮结果。
 * 内部会调用 cloud_parse_response()，保证失败判定逻辑只有一个实现点。
 */
int cloud_send_audio(const cloud_request_t *req, cloud_response_t *resp);

/*
 * 解析云端响应体。独立出来是为了能在 PC 上脱离硬件做单元测试。
 * 这是"空 tts_audio 判为失败"的唯一实现点。
 */
int cloud_parse_response(const char *body, size_t len, cloud_response_t *resp);

/* 释放 resp 里由本模块分配的内存；可重复调用 */
void cloud_response_free(cloud_response_t *resp);

#endif /* __NETWORK_CLIENT_H__ */
