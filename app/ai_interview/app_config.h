/*
 * AI模拟面试官 — 编译期配置与运行时覆盖
 * 负责：A同学
 *
 * 这里所有带 CONFIG_ 前缀的宏都有 #ifndef 兜底：Kconfig 项要等 mkkconfig.sh
 * 重新扫描目录后才会进 .config，本地工作区若尚未构建过，宏不存在会导致编译失败。
 */

#ifndef __APP_CONFIG_H__
#define __APP_CONFIG_H__

#include <stdlib.h>
#include <string.h>

/* ---- 云端服务地址（不含路径）----
 * 默认值填的是**演示环境的实际地址**，不是占位符。
 *
 * 原先这里是 "http://192.168.1.100:5000"（占位用）。当时观察到应用报
 * "Couldn't connect to server" 且抓包看不到任何包，据此判定"运行期
 * `nsh> set CLOUD_URL` 覆盖不生效"，于是把地址直接编了进来。
 *
 * 事后查明那个结论是**错的**：真正的原因是板子的 wlan0 掉出了热点，
 * 根本没在发包 —— 跟 URL 从哪儿来无关。代码路径本身是通的：
 * apps/builtin/exec_builtin.c 虽然给 posix_spawn 传 envp = NULL，但
 * nuttx/sched/task/task_spawn.c:226 会退化成 environ，内置应用确实继承
 * NSH 的环境变量。
 *
 * 但要注意：运行期覆盖至今**没有在真机上正面验证过**。所以默认值仍然填
 * 实际地址，保证不 set 任何东西也能直接跑通。想验证覆盖是否生效，可以故意
 * 设一个错的端口，看应用打印的是不是那个错端口：
 *   nsh> set CLOUD_URL http://172.20.10.2:9999
 *
 * 172.20.10.2 是 Windows 宿主机在手机热点上的地址，VMware NAT 把它的
 * 5000 端口转发到虚拟机的 Flask。演示环境固定，故直接编进来。
 */
#ifndef CONFIG_APP_AI_INTERVIEW_CLOUD_URL
#  define CONFIG_APP_AI_INTERVIEW_CLOUD_URL "http://172.20.10.2:5000"
#endif

/* ---- 面试官角色 ---- */
#ifndef CONFIG_APP_AI_INTERVIEW_ROLE
#  define CONFIG_APP_AI_INTERVIEW_ROLE "产品经理"
#endif

/* ---- 单轮录音上限（秒）---- */
#ifndef CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS
#  define CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS 30
#endif

/* ---- 静音判定阈值（16bit 满幅 32767 的 RMS 门限）----
 * 500 是 9/13 定的，9/14 晚按现场底噪上调到 900 —— 依据见
 * documents/progress_audit_2026-09-11.md §11.19。
 */
#ifndef CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD
#  define CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD 900
#endif

/* ---- 采集 PCM 设备名 ----
 * 实测确认：这块板子的麦克风接在**数字麦（DMIC）**上，走 hw:snddmic。
 * "default" 解析到模拟 codec（audiocodec），那条通路上没有麦克风，
 * 采回来的是恒定的全零。
 *
 * 仍支持运行期覆盖，便于换板子时验证：
 *   nsh> set PCM_DEV hw:snddmic
 */
#ifndef CONFIG_APP_AI_INTERVIEW_CAPTURE_DEV
#  define CONFIG_APP_AI_INTERVIEW_CAPTURE_DEV "hw:snddmic"
#endif

/* ---- 采集声道数 ----
 * DMIC 以 2 声道采集（实测可用）。录音时会下混成单声道再送 ASR。
 */
#ifndef CONFIG_APP_AI_INTERVIEW_CAPTURE_CHANNELS
#  define CONFIG_APP_AI_INTERVIEW_CAPTURE_CHANNELS 2
#endif

/* ---- 麦克风数字增益（软件）----
 * DMIC 驱动没有暴露增益控件，实测录音偏小，所以在下混时做数字放大。
 * 运行期可调，省得为试一个数值重烧：
 *   nsh> set MIC_GAIN 8
 */
#ifndef CONFIG_APP_AI_INTERVIEW_MIC_GAIN
#  define CONFIG_APP_AI_INTERVIEW_MIC_GAIN 4
#endif

static inline const char *app_capture_device(void)
{
    const char *env = getenv("PCM_DEV");

    if (env != NULL && env[0] != '\0') {
        return env;
    }

    return CONFIG_APP_AI_INTERVIEW_CAPTURE_DEV;
}

static inline unsigned int app_capture_channels(void)
{
    const char *env = getenv("PCM_CH");
    int v;

    if (env != NULL && env[0] != '\0') {
        v = atoi(env);
        if (v >= 1 && v <= 8) {
            return (unsigned int)v;
        }
    }

    return CONFIG_APP_AI_INTERVIEW_CAPTURE_CHANNELS;
}

static inline unsigned int app_mic_gain(void)
{
    const char *env = getenv("MIC_GAIN");
    int v;

    if (env != NULL && env[0] != '\0') {
        v = atoi(env);
        if (v >= 1 && v <= 64) {
            return (unsigned int)v;
        }
    }

    return CONFIG_APP_AI_INTERVIEW_MIC_GAIN;
}

/*
 * 下面三个原本是编译期常量，改成运行期可覆盖 —— 理由是它们都属于
 * "必须对着现场实测值反复试"的参数，而重烧一次的成本远高于输入一条命令：
 *
 *   nsh> set SILENCE_THRESHOLD 800   # 静音门限（RMS，16bit 满幅）
 *   nsh> set MAX_REC_SEC 15          # 单轮录音上限（秒）
 *   nsh> set ROLE 技术总监            # 面试官角色
 */

/* ---- 静音判定阈值（16bit 满幅 32767 的 RMS 门限）----
 * 调法：先在日志里看实测 RMS —— 说话时取一个偏低的稳定值，安静时取偏高的，
 * 门限放在两者中间。开太低会把环境噪声当人声（永远不停），开太高会把
 * 说话当静音（录不满就截断）。
 *
 * 注意这不是"绝对灵敏度"，而是**当前房间底噪 + 这块板子自噪**的匹配值：
 * 同一个固件换个房间就该重调。判据是日志里静音段那几行的"RMS 平均"，
 * 它越过门限就意味着程序把安静当成了说话。
 */
static inline unsigned int app_silence_threshold(void)
{
    const char *env = getenv("SILENCE_THRESHOLD");
    int v;

    if (env != NULL && env[0] != '\0') {
        v = atoi(env);
        if (v >= 1 && v <= 32767) {
            return (unsigned int)v;
        }
    }

    return CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD;
}

static inline unsigned int app_max_record_seconds(void)
{
    const char *env = getenv("MAX_REC_SEC");
    int v;

    if (env != NULL && env[0] != '\0') {
        v = atoi(env);
        if (v >= 1 && v <= 300) {
            return (unsigned int)v;
        }
    }

    return CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS;
}

/* 面试官角色。演示时换个岗位只需 set ROLE，不必重烧。 */
static inline const char *app_role(void)
{
    const char *env = getenv("ROLE");

    if (env != NULL && env[0] != '\0') {
        return env;
    }

    return CONFIG_APP_AI_INTERVIEW_ROLE;
}

/* ---- 流水线工作线程栈大小 ----
 * 必须够大：libcurl 在这个 port 上要 200KB 量级
 * （参考 CONFIG_EXAMPLES_HTTP_STACKSIZE 默认 204800），而
 * CONFIG_PTHREAD_STACK_DEFAULT 只有 4096。
 */
#ifndef CONFIG_APP_AI_INTERVIEW_WORKER_STACKSIZE
#  define CONFIG_APP_AI_INTERVIEW_WORKER_STACKSIZE 262144
#endif

/* 判断是不是一个可用的完整 URL（http 或 https，且协议后有内容）*/
static inline int app_url_is_valid(const char *u)
{
    const char *rest;

    if (u == NULL) {
        return 0;
    }

    if (strncmp(u, "https://", 8) == 0) {
        rest = u + 8;
    } else if (strncmp(u, "http://", 7) == 0) {
        rest = u + 7;
    } else {
        return 0;
    }

    return rest[0] != '\0';
}

/*
 * 取云端 base 地址。
 * 环境变量 CLOUD_URL 优先于 Kconfig：演示当天换服务器只需
 *   nsh> set CLOUD_URL http://192.168.1.23:5000
 * 不必重新编译烧录（内置应用会继承 NSH 的环境变量）。
 *
 * 同样接受 https:// —— 走内网穿透或公网部署时给的就是 https 地址。
 * 端侧能跑 TLS：CONFIG_LIB_CURL 会带入 mbedtls。
 */
static inline const char *app_cloud_base_url(void)
{
    const char *env = getenv("CLOUD_URL");

    /* 只接受带协议的完整地址，避免把空串或半截地址当成有效配置 */
    if (app_url_is_valid(env)) {
        return env;
    }

    return CONFIG_APP_AI_INTERVIEW_CLOUD_URL;
}

#endif /* __APP_CONFIG_H__ */
