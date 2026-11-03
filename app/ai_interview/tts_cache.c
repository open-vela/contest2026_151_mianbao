/*
 * 固定话术的本地 WAV 缓存 —— 实现；取舍见 tts_cache.h 顶部。
 *
 * 布局：/data/tts_cache/<key>.wav，key 只允许字母/数字/下划线（防路径穿越）。
 * 文件就是完整的 WAV（含 44 字节头），直接喂 audio_play_wav()。
 */
#include <nuttx/config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>

#include "audio_io.h"
#include "tts_cache.h"

#define TTS_CACHE_DIR  "/data/tts_cache"

/* 单个缓存文件的大小上限：开场白实测约百 KB 量级，4MB 是防御性余量
 * （超过就当坏文件丢掉，防止把堆吃穿）。 */
#define TTS_CACHE_MAX_WAV (4u * 1024u * 1024u)

/* key 白名单：字母/数字/下划线，1~32 字符。key 全是本应用的常量，
 * 但仍校验 —— 万一日后有人拿它拼了外部输入，路径穿越在这里被挡住。 */
static int key_valid(const char *key)
{
    size_t i;

    if (key == NULL) {
        return 0;
    }
    for (i = 0; key[i] != '\0'; i++) {
        char c = key[i];

        if (i >= 32) {
            return 0;
        }
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_')) {
            return 0;
        }
    }
    return i > 0;
}

static void cache_path(char *out, size_t cap, const char *key)
{
    snprintf(out, cap, "%s/%s.wav", TTS_CACHE_DIR, key);
}

int tts_cache_store(const char *key, const uint8_t *wav, size_t len)
{
    char path[96];
    FILE *fp;

    if (!key_valid(key) || wav == NULL || len < 44 || len > TTS_CACHE_MAX_WAV) {
        return -1;
    }

    /* /data 可能是只读挂载 / 没这个分区 —— 失败只影响"下次断网能不能出声"，
     * 不能影响本次面试（调用方先播后存）。 */
    if (mkdir(TTS_CACHE_DIR, 0755) != 0 && errno != EEXIST) {
        printf("[TTS] 缓存目录建不了（%s）—— 本次有效，不落盘\n", TTS_CACHE_DIR);
        return -1;
    }

    cache_path(path, sizeof(path), key);
    fp = fopen(path, "wb");
    if (fp == NULL) {
        printf("[TTS] 缓存写不了（%s）\n", path);
        return -1;
    }
    if (fwrite(wav, 1, len, fp) != len) {
        printf("[TTS] 缓存写入不完整（%s）\n", path);
        fclose(fp);
        (void)remove(path);      /* 半截文件当坏文件清掉 */
        return -1;
    }
    fclose(fp);
    return 0;
}

int tts_cache_has(const char *key)
{
    char path[96];
    struct stat st;

    if (!key_valid(key)) {
        return 0;
    }
    cache_path(path, sizeof(path), key);
    if (stat(path, &st) != 0) {
        return 0;
    }
    /* WAV 头 44 字节 + 至少一点数据；太大视为坏文件 */
    return (st.st_size >= 44 && (size_t)st.st_size <= TTS_CACHE_MAX_WAV) ? 1 : 0;
}

int tts_cache_play(const char *key, volatile int *abort)
{
    char path[96];
    struct stat st;
    FILE *fp;
    uint8_t *wav;
    size_t len;

    if (!tts_cache_has(key)) {
        return -1;
    }
    cache_path(path, sizeof(path), key);

    fp = fopen(path, "rb");
    if (fp == NULL) {
        return -1;
    }
    if (stat(path, &st) != 0) {
        fclose(fp);
        return -1;
    }
    len = (size_t)st.st_size;
    wav = (uint8_t *)malloc(len);
    if (wav == NULL) {
        fclose(fp);
        return -1;
    }
    if (fread(wav, 1, len, fp) != len) {
        printf("[TTS] 缓存读取不完整（%s）\n", path);
        free(wav);
        fclose(fp);
        return -1;
    }
    fclose(fp);

    /* 落过盘的都是完整 WAV，audio_play_wav 里的头校验再兜一层 */
    if (audio_play_wav(wav, len, abort) != AI_PLAY_OK) {
        free(wav);
        return -1;
    }
    free(wav);
    return 0;
}
