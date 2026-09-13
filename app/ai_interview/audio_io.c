/*
 * AI模拟面试官 — 音频采集与播放
 * 负责：A同学
 *
 * 设计取舍：
 *   - 复用 libapps.a 里 vendor 的 set_param / pcm_read / pcm_write / xrun
 *     （它们在 hal/test/sound/ 下，由 CONFIG_COMPONENTS_AW_ALSA_UTILS 编入）。
 *     那段 ALSA hw/sw params 配置序列在真机上验证过，重写风险高。本模块只
 *     声明引用、不重复编译 —— 那 6 个 .c 与 vendor 树逐字节相同，再编一份
 *     会造成重复定义。
 *   - WAV 头的读写自己做：只有 44 个固定字节，比依赖 wav_header_t 的结构体
 *     对齐假设更稳，也不需要引入 wav_parser.h。
 */

#include <nuttx/config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include <aw-alsa-lib/pcm.h>   /* 必须先于 common.h：后者用到 snd_pcm_* 类型 */
#include <aw-alsa-lib/control.h>
#include "audio/common.h"

#include "audio_io.h"
#include "app_config.h"

/* 设备名 "default" 由 aw-alsa-lib 解析到卡 audiocodec（见 alsa_config.c）*/
#define AI_PCM_DEVICE   "default"
#define AI_CODEC_CARD   "audiocodec"

/*
 * 配置 codec。
 *
 * 两件事都必须做，缺一不可：
 *
 * 1) 打开模拟输入通路。codec 默认不启用任何 ADC 输入路由，而
 *    sunxi_codec_hw_params() 会在 sunxi_get_adc_ch() 返回负值时直接失败，
 *    并打出一条误导性的 "capture only support 1~3 channel" —— 它检查的
 *    其实不是请求的通道数，而是"模拟输入通路有没有被打开"。
 *
 * 2) 设置 ADC/DAC 音量。ADC 数字音量若为默认低值，采到的 PCM 会被压成
 *    接近全零（实测表现为持续 RMS≈1，说话也毫无反应）。这一点最初漏掉了，
 *    上板后才发现。
 *
 * 录制通道数跟着打开的输入通路走：只开 MIC1 就得到单声道，与本模块请求的
 * 1 声道一致（codec 按 adc1/adc2/adc3_flag 逐个使能 ADC 数字通道）。
 *
 * 取值来自队伍此前在这块板子上验证过的 amixer 配方
 * （amixer set 19/20/21 255、6/7 150、15 7），此处改用控件名以免索引漂移。
 */
static int codec_configure(void)
{
    static const struct {
        const char  *name;
        unsigned int value;
    } settings[] = {
        /* 采集：输入通路 + 数字音量 */
        { "MIC1 input switch",   1   },
        { "MIC1 gain volume",    19  },
        { "ADC1 digital volume", 255 },
        { "ADC2 digital volume", 255 },
        { "ADC3 digital volume", 255 },
        /* 播放：数字音量 + 耳机增益 */
        { "DACL digital volume", 150 },
        { "DACR digital volume", 150 },
        { "HPOUT gain volume",   7   },
    };
    size_t i;
    int failed = 0;

    for (i = 0; i < sizeof(settings) / sizeof(settings[0]); i++) {
        if (snd_ctl_set(AI_CODEC_CARD, settings[i].name,
                        settings[i].value) < 0) {
            printf("[Audio] 设置 %s 失败\n", settings[i].name);
            failed++;
        }
    }

    if (failed != 0) {
        printf("[Audio] codec 配置有 %d 项失败，录音可能无声\n", failed);
        return -1;
    }

    printf("[Audio] codec 已配置（输入通路 + ADC/DAC 音量）\n");
    return 0;
}

/* 录音参数：16kHz 单声道 16bit —— ASR 的通用首选，也是云端 demo 用的配置 */
#define AI_REC_RATE     16000u
#define AI_REC_CHANNELS 1u
#define AI_REC_BITS     16u

/* 分块与判定节奏，均以 100ms 为粒度（与主循环节拍一致）*/
#define AI_CHUNK_MS            100u
#define AI_SILENCE_CHUNKS      20   /* 连续 2 秒静音 -> 认为说完了 */
#define AI_MIN_SPEECH_CHUNKS    3   /* 至少 300ms 人声才允许被静音截断 */
#define AI_NOSPEECH_CHUNKS     50   /* 5 秒还没出声 -> 判定没人说话 */

static void put_le32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v);
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static void put_le16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v);
    p[1] = (uint8_t)(v >> 8);
}

static uint32_t get_le32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint16_t get_le16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

/* 写 44 字节标准 PCM WAV 头 */
static void wav_write_header(uint8_t *h, uint32_t data_size,
                             unsigned channels, unsigned rate, unsigned bits)
{
    uint16_t block_align = (uint16_t)(channels * (bits / 8));

    memcpy(h, "RIFF", 4);
    put_le32(h + 4, 36 + data_size);
    memcpy(h + 8, "WAVE", 4);
    memcpy(h + 12, "fmt ", 4);
    put_le32(h + 16, 16);            /* fmt 块长度 */
    put_le16(h + 20, 1);             /* 1 = PCM */
    put_le16(h + 22, (uint16_t)channels);
    put_le32(h + 24, rate);
    put_le32(h + 28, rate * block_align);   /* 字节率 */
    put_le16(h + 32, block_align);
    put_le16(h + 34, (uint16_t)bits);
    memcpy(h + 36, "data", 4);
    put_le32(h + 40, data_size);
}

/*
 * 解析 WAV 头。只支持标准 44 字节布局（fmt 后紧跟 data）—— 云端 TTS 返回的
 * 就是这种（实测 399404 = 44 + 399360）。带附加块的 WAV 会被判为不支持，
 * 宁可报错也不要放出一段噪声。
 */
static int wav_parse(const uint8_t *w, size_t len, unsigned *rate,
                     unsigned *channels, unsigned *bits,
                     size_t *data_off, size_t *data_len)
{
    uint32_t dlen;

    if (w == NULL || len < 44) {
        return -1;
    }
    if (memcmp(w, "RIFF", 4) != 0 || memcmp(w + 8, "WAVE", 4) != 0) {
        return -1;
    }
    if (memcmp(w + 12, "fmt ", 4) != 0 || get_le16(w + 20) != 1) {
        return -1;
    }
    if (memcmp(w + 36, "data", 4) != 0) {
        return -1;
    }

    *channels = get_le16(w + 22);
    *rate = get_le32(w + 24);
    *bits = get_le16(w + 34);
    dlen = get_le32(w + 40);

    if (*channels < 1 || *channels > 2 || *bits != 16 ||
        *rate < 8000 || *rate > 96000) {
        return -1;
    }

    *data_off = 44;
    /* 头部声明比实际文件长时不硬信声明值 */
    *data_len = (dlen <= len - 44) ? dlen : (len - 44);
    return (*data_len > 0) ? 0 : -1;
}

const char *audio_rec_strerror(ai_rec_result_t r)
{
    switch (r) {
        case AI_REC_OK:       return "成功";
        case AI_REC_NOSPEECH: return "未检测到人声";
        case AI_REC_ABORTED:  return "已取消";
        case AI_REC_ERROR:    return "录音失败";
    }
    return "未知";
}

const char *audio_play_strerror(ai_play_result_t r)
{
    switch (r) {
        case AI_PLAY_OK:      return "成功";
        case AI_PLAY_ABORTED: return "已打断";
        case AI_PLAY_ERROR:   return "播放失败";
    }
    return "未知";
}

ai_rec_result_t audio_record_wav(uint8_t **out, size_t *out_len,
                                 volatile int *abort)
{
    snd_pcm_t *handle = NULL;
    uint8_t *buf;
    size_t cap;
    size_t pcm_len = 0;
    const unsigned frame_bytes = AI_REC_CHANNELS * (AI_REC_BITS / 8);
    const unsigned chunk_frames = AI_REC_RATE / (1000 / AI_CHUNK_MS);
    int silence_run = 0;
    int speech_chunks = 0;
    int chunks = 0;
    ai_rec_result_t result = AI_REC_OK;
    int rc;

    if (out == NULL || out_len == NULL) {
        return AI_REC_ERROR;
    }

    cap = (size_t)CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS *
          AI_REC_RATE * frame_bytes;
    buf = malloc(44 + cap);
    if (buf == NULL) {
        printf("[Audio] 录音缓冲分配失败 (%u 字节)\n", (unsigned)(44 + cap));
        return AI_REC_ERROR;
    }

    /* 必须先配好 codec（输入通路 + ADC 音量），否则要么 hw_params 失败，
     * 要么采回一堆全零 */
    if (codec_configure() < 0) {
        free(buf);
        return AI_REC_ERROR;
    }

    printf("[Audio] 采集设备: %s\n", app_capture_device());

    rc = snd_vela_pcm_open(&handle, app_capture_device(),
                           SND_VELA_PCM_STREAM_CAPTURE, 0);
    if (rc < 0) {
        printf("[Audio] 打开录音设备失败: %d\n", rc);
        free(buf);
        return AI_REC_ERROR;
    }

    rc = set_param(handle, SND_PCM_FORMAT_S16_LE, AI_REC_RATE,
                   AI_REC_CHANNELS, 1024, 4096);
    if (rc < 0) {
        printf("[Audio] 录音参数配置失败: %d\n", rc);
        snd_vela_pcm_close(handle);
        free(buf);
        return AI_REC_ERROR;
    }

    printf("[Audio] 开始录音（静音 %.1f 秒自动结束，最长 %d 秒）\n",
           (double)AI_SILENCE_CHUNKS * AI_CHUNK_MS / 1000.0,
           CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS);

    for (;;) {
        const int16_t *s;
        long long sum2 = 0;
        int i;

        if (abort != NULL && *abort) {
            result = AI_REC_ABORTED;
            break;
        }
        if (pcm_len + (size_t)chunk_frames * frame_bytes > cap) {
            result = AI_REC_OK;     /* 到达时长上限，按正常结束处理 */
            break;
        }

        rc = pcm_read(handle, (const char *)(buf + 44 + pcm_len),
                      chunk_frames, frame_bytes);
        if (rc <= 0) {
            printf("[Audio] 读取失败: %d\n", rc);
            result = AI_REC_ERROR;
            break;
        }
        pcm_len += (size_t)rc * frame_bytes;

        /* 静音判定：算整块 RMS，与门限比较。
         * 用平方和与 thr²·n 比较，避免开方与浮点。 */
        s = (const int16_t *)(buf + 44 + pcm_len - (size_t)rc * frame_bytes);
        for (i = 0; i < rc; i++) {
            long long v = s[i];
            sum2 += v * v;
        }

        if (sum2 > (long long)CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD *
                   CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD * rc) {
            silence_run = 0;
            speech_chunks++;
        } else {
            silence_run++;
        }
        chunks++;

        /* 每 10 块（1 秒）打一次实测 RMS，方便现场调阈值 */
        if (chunks % 10 == 0) {
            printf("[Audio] %d 秒, 本块 RMS≈%d, 人声占比 %d%%\n",
                   chunks / 10,
                   (int)((sum2 > 0) ? (long long)(sum2 / (rc > 0 ? rc : 1)) : 0),
                   chunks ? speech_chunks * 100 / chunks : 0);
        }

        if (speech_chunks == 0 && chunks >= AI_NOSPEECH_CHUNKS) {
            result = AI_REC_NOSPEECH;
            break;
        }
        if (speech_chunks >= AI_MIN_SPEECH_CHUNKS &&
            silence_run >= AI_SILENCE_CHUNKS) {
            result = AI_REC_OK;
            break;
        }
    }

    snd_vela_pcm_drain(handle);
    snd_vela_pcm_close(handle);

    if (result != AI_REC_OK) {
        printf("[Audio] 录音结束: %s\n", audio_rec_strerror(result));
        free(buf);
        return result;
    }

    wav_write_header(buf, (uint32_t)pcm_len, AI_REC_CHANNELS,
                     AI_REC_RATE, AI_REC_BITS);
    *out = buf;
    *out_len = 44 + pcm_len;

    printf("[Audio] 录音完成: %.1f 秒, %u 字节\n",
           (double)pcm_len / (AI_REC_RATE * frame_bytes),
           (unsigned)(44 + pcm_len));
    return AI_REC_OK;
}

ai_play_result_t audio_play_wav(const uint8_t *wav, size_t len,
                                volatile int *abort)
{
    snd_pcm_t *handle = NULL;
    unsigned rate = 0, channels = 0, bits = 0;
    size_t off = 0, data_len = 0;
    unsigned frame_bytes;
    size_t chunk_bytes;
    size_t pos;
    ai_play_result_t result = AI_PLAY_OK;
    int rc;

    if (wav_parse(wav, len, &rate, &channels, &bits, &off, &data_len) != 0) {
        printf("[Audio] 音频格式不支持（需要 16bit PCM WAV）\n");
        return AI_PLAY_ERROR;
    }

    frame_bytes = channels * (bits / 8);

    rc = snd_vela_pcm_open(&handle, AI_PCM_DEVICE,
                           SND_VELA_PCM_STREAM_PLAYBACK, 0);
    if (rc < 0) {
        printf("[Audio] 打开播放设备失败: %d\n", rc);
        return AI_PLAY_ERROR;
    }

    /* 云端 TTS 是 24kHz 单声道，这里按头里的实际值配，不重采样 */
    rc = set_param(handle, SND_PCM_FORMAT_S16_LE, rate, channels, 1024, 4096);
    if (rc < 0) {
        printf("[Audio] 播放参数配置失败: %d\n", rc);
        snd_vela_pcm_close(handle);
        return AI_PLAY_ERROR;
    }

    printf("[Audio] 开始播放: %u Hz / %u 声道 / %.1f 秒\n",
           rate, channels, (double)data_len / (rate * frame_bytes));

    chunk_bytes = (rate / (1000 / AI_CHUNK_MS)) * frame_bytes;

    for (pos = 0; pos < data_len; ) {
        size_t n = data_len - pos;
        snd_pcm_uframes_t frames;

        if (abort != NULL && *abort) {
            result = AI_PLAY_ABORTED;
            break;
        }
        if (n > chunk_bytes) {
            n = chunk_bytes;
        }

        frames = (snd_pcm_uframes_t)(n / frame_bytes);
        if (frames == 0) {
            break;
        }

        rc = pcm_write(handle, (char *)(wav + off + pos), frames, frame_bytes);
        if (rc <= 0) {
            printf("[Audio] 写入失败: %d\n", rc);
            result = AI_PLAY_ERROR;
            break;
        }
        pos += (size_t)rc * frame_bytes;
    }

    snd_vela_pcm_drain(handle);
    snd_vela_pcm_close(handle);

    printf("[Audio] 播放结束: %s\n", audio_play_strerror(result));
    return result;
}
