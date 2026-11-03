/*
 * 固定话术的本地 WAV 缓存 —— 断网也能出声（2026-11-02，断网体验第 3 层兜底）。
 *
 * 产品口径（台账 §11.65）：断网 = 暂停练习不丢进度，不是离线可用。但有两句
 * 措辞固定的话不需要云端也能说：
 *   1. 开场白（按岗位 6 个变体）—— 缓存键 greet0..greet5（下标 = 岗位表下标）；
 *   2. 「抱歉，我没听清，请再说一次。」—— 本地静音判定（AI_REC_NOSPEECH）时说，
 *      不上传、不进历史，缓存键 TTS_CACHE_NO_HEAR。
 * 开机在线时预合成一次落 /data/tts_cache/，之后断网 / TTS 服务故障也照样出声。
 *
 * 线程纪律：文件 IO 很短且没有共享状态，但调用点全在工作线程（同网络函数），
 * 这里也只在工作线程调用，保持一致。
 */
#ifndef __TTS_CACHE_H__
#define __TTS_CACHE_H__

#include <stddef.h>
#include <stdint.h>

/* 「抱歉，我没听清」的缓存键 */
#define TTS_CACHE_NO_HEAR "no_hear"

/*
 * 播放缓存里的固定话术。返回 0 = 已播放；-1 = 没有缓存或读取失败（调用方
 * 自行降级：现合成 / 跳过）。abort 语义同 audio_play_wav（100ms 粒度打断）。
 */
int tts_cache_play(const char *key, volatile int *abort);

/*
 * 把一段合成好的 WAV 存进缓存（key 同上）。返回 0 = 已存；非 0 = 写失败
 * （下次在线时会再补，不影响本次播放 —— 调用方是先播后存）。
 */
int tts_cache_store(const char *key, const uint8_t *wav, size_t len);

/* 1 = 缓存里有这个键且大小合理。 */
int tts_cache_has(const char *key);

#endif /* __TTS_CACHE_H__ */
