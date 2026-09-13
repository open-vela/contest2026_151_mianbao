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

/* ---- 云端服务地址（不含路径）---- */
#ifndef CONFIG_APP_AI_INTERVIEW_CLOUD_URL
#  define CONFIG_APP_AI_INTERVIEW_CLOUD_URL "http://192.168.1.100:5000"
#endif

/* ---- 面试官角色 ---- */
#ifndef CONFIG_APP_AI_INTERVIEW_ROLE
#  define CONFIG_APP_AI_INTERVIEW_ROLE "产品经理"
#endif

/* ---- 单轮录音上限（秒）---- */
#ifndef CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS
#  define CONFIG_APP_AI_INTERVIEW_MAX_RECORD_SECONDS 30
#endif

/* ---- 静音判定阈值（16bit 满幅 32767 的 RMS 门限）---- */
#ifndef CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD
#  define CONFIG_APP_AI_INTERVIEW_SILENCE_THRESHOLD 500
#endif

/* ---- 流水线工作线程栈大小 ----
 * 必须够大：libcurl 在这个 port 上要 200KB 量级
 * （参考 CONFIG_EXAMPLES_HTTP_STACKSIZE 默认 204800），而
 * CONFIG_PTHREAD_STACK_DEFAULT 只有 4096。
 */
#ifndef CONFIG_APP_AI_INTERVIEW_WORKER_STACKSIZE
#  define CONFIG_APP_AI_INTERVIEW_WORKER_STACKSIZE 262144
#endif

/*
 * 取云端 base 地址。
 * 环境变量 CLOUD_URL 优先于 Kconfig：演示当天换服务器只需
 *   nsh> set CLOUD_URL http://192.168.1.23:5000
 * 不必重新编译烧录（内置应用会继承 NSH 的环境变量）。
 */
static inline const char *app_cloud_base_url(void)
{
    const char *env = getenv("CLOUD_URL");

    /* 只接受带协议的完整地址，避免把空串或半截地址当成有效配置 */
    if (env != NULL && strncmp(env, "http://", 7) == 0 && env[7] != '\0') {
        return env;
    }

    return CONFIG_APP_AI_INTERVIEW_CLOUD_URL;
}

#endif /* __APP_CONFIG_H__ */
