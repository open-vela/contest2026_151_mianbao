/*
 * AI模拟面试官 — 音频采集与播放
 * 负责：A同学
 *
 * 只做两件事：录一段话到内存（带静音检测与超时），把云端返回的音频放出来。
 *
 * 注意：本模块复用 libapps.a 里 vendor 的 set_param / pcm_read / pcm_write
 * （它们在 hal/test/sound/ 下，由 CONFIG_COMPONENTS_AW_ALSA_UTILS 编入），
 * 只通过 audio/common.h 声明引用、不重复编译 —— 那 6 个 .c 文件与 vendor 树
 * 逐字节相同，再编一份会造成重复定义。
 */

#ifndef __AUDIO_IO_H__
#define __AUDIO_IO_H__

#include <stddef.h>
#include <stdint.h>

/* 录音结果 */
typedef enum {
    AI_REC_OK = 0,      /* 正常结束（静音收尾或达到时长上限）*/
    AI_REC_NOSPEECH,    /* 一直没检测到人声，不浪费一次上传 */
    AI_REC_ABORTED,     /* 被 K2 取消 */
    AI_REC_ERROR        /* 打开设备 / 配置参数 / 读取失败 */
} ai_rec_result_t;

/* 播放结果 */
typedef enum {
    AI_PLAY_OK = 0,
    AI_PLAY_ABORTED,    /* 被 K2 打断 */
    AI_PLAY_ERROR
} ai_play_result_t;

/*
 * 录一段话，输出带 44 字节头的完整 WAV（*wav 由 malloc 分配，调用者负责 free）。
 * abort 指向一个 volatile int，置 1 时在 100ms 粒度内退出。
 */
ai_rec_result_t audio_record_wav(uint8_t **wav, size_t *len,
                                 volatile int *abort);

/*
 * 播放一段 WAV（按头里的采样率/声道播放，不重采样）。
 * abort 指向一个 volatile int，置 1 时在 100ms 粒度内停止。
 */
ai_play_result_t audio_play_wav(const uint8_t *wav, size_t len,
                                volatile int *abort);

/* 结果码转可读文本，用于串口日志 */
const char *audio_rec_strerror(ai_rec_result_t r);
const char *audio_play_strerror(ai_play_result_t r);

#endif /* __AUDIO_IO_H__ */
