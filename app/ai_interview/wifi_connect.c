/*
 * AI模拟面试官 — 开机自动联网（2026-10-27 加）
 *
 * 为什么用 `nsh -c` 跑命令，而不是直接调 wapi 库：
 *   * wapi 的公开头文件（apps/include/wireless/wapi.h）**没有 PSK 设置函数**
 *     —— `$ wapi psk ...` 是 CLI 自己解析的，库层不暴露；
 *   * 下面这串命令是用户在本板真机上验证过的，行为确定；
 *   * `posix_spawn("nsh", "-c", ...)` 在本固件可用（CONFIG_LIBC_EXECFUNCS=y、
 *     CONFIG_SYSTEM_NSH=y，nsh 支持 -c <command>，见 apps/nshlib/nsh_session.c）。
 *
 * 为什么逐条 spawn、不等一整串脚本：
 *   每条等它退出再跑下一条，顺序确定、失败点可读；代价是多几次任务创建，
 *   开机时多花一两秒，可以接受。
 *
 * 凭据安全：
 *   * **密码绝不打印、绝不写进仓库**；
 *   * 凭据只来自环境变量或 /data/ai_interview_wifi；
 *   * 命令串里出现密码的那一条用固定标签记录，日志里不出现命令行本身；
 *   * 字符白名单校验（拒绝空格/引号/分号/管道等），避免命令注入。
 */
#include <nuttx/config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <spawn.h>
#include <sys/wait.h>

#include "wifi_connect.h"

#define WIFI_IFACE       "wlan0"
#define WIFI_PREF_PATH   "/data/ai_interview_wifi"
#define WIFI_CRED_MAX    64

static void trim(char *s)
{
    char *start = s;
    size_t len;

    while (*start == ' ' || *start == '\t' || *start == '\r' || *start == '\n') {
        start++;
    }
    if (start != s) {
        memmove(s, start, strlen(start) + 1);
    }
    len = strlen(s);
    while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' ||
                       s[len - 1] == '\r' || s[len - 1] == '\n')) {
        s[--len] = '\0';
    }
}

/* 白名单式校验：只挡"会破坏 nsh 命令解析"的字符。
 * SSID 里带空格的情况这里不支持 —— 走环境变量的 `set` 本来也会按空白分词，
 * 与其半支持，不如明确拒绝并打印原因。 */
static int cred_ok(const char *s)
{
    const char *bad = " \t\r\n\"'`$;&|<>\\";
    size_t i;

    if (s == NULL || s[0] == '\0') {
        return 0;
    }
    if (strlen(s) >= WIFI_CRED_MAX) {
        return 0;
    }
    for (i = 0; s[i] != '\0'; i++) {
        if (strchr(bad, s[i]) != NULL) {
            return 0;
        }
    }
    return 1;
}

static void persist_creds(const char *ssid, const char *psk)
{
    FILE *fp = fopen(WIFI_PREF_PATH, "w");

    if (fp == NULL) {
        printf("[Wifi] 提示: 无法写入 %s（下次仍需设环境变量）\n", WIFI_PREF_PATH);
        return;
    }
    fprintf(fp, "%s\n%s\n", ssid, psk);
    fclose(fp);
    printf("[Wifi] 凭据已保存到 %s（下次开机自动使用）\n", WIFI_PREF_PATH);
}

static int load_creds(char *ssid, char *psk)
{
    const char *env_ssid = getenv("WIFI_SSID");
    const char *env_psk  = getenv("WIFI_PSK");
    FILE *fp;

    if (env_ssid != NULL && env_ssid[0] != '\0' &&
        env_psk != NULL && env_psk[0] != '\0') {
        strncpy(ssid, env_ssid, WIFI_CRED_MAX - 1);
        strncpy(psk, env_psk, WIFI_CRED_MAX - 1);
        ssid[WIFI_CRED_MAX - 1] = '\0';
        psk[WIFI_CRED_MAX - 1] = '\0';
        printf("[Wifi] 凭据来源: 环境变量 WIFI_SSID / WIFI_PSK\n");
        persist_creds(ssid, psk);       /* 首次设了环境变量就记住 */
        return 0;
    }

    fp = fopen(WIFI_PREF_PATH, "r");
    if (fp == NULL) {
        return -1;
    }
    if (fgets(ssid, WIFI_CRED_MAX, fp) == NULL ||
        fgets(psk, WIFI_CRED_MAX, fp) == NULL) {
        fclose(fp);
        return -1;
    }
    fclose(fp);
    trim(ssid);
    trim(psk);
    if (ssid[0] == '\0' || psk[0] == '\0') {
        return -1;
    }
    printf("[Wifi] 凭据来源: %s\n", WIFI_PREF_PATH);
    return 0;
}

/* 跑一条 nsh 命令并等它结束。label 用于日志 —— 涉及密码的命令只打标签。 */
static int run_cmd(const char *cmd, const char *label)
{
    char *argv[] = { (char *)"nsh", (char *)"-c", (char *)cmd, NULL };
    pid_t pid;
    int status = 0;
    int ret;

    /* envp 传 NULL：nuttx 自己的 builtin 执行器（apps/builtin/exec_builtin.c）
     * 也是这么传的；nsh 的 ifup/wapi/renew 都是编译进固件的内置命令，
     * 不依赖子进程环境。 */
    ret = posix_spawn(&pid, "nsh", NULL, NULL, argv, NULL);
    if (ret != 0) {
        printf("[Wifi] %s: 启动 nsh 失败 (%d)\n", label, ret);
        return -1;
    }

    ret = (int)waitpid(pid, &status, 0);
    if (ret < 0) {
        printf("[Wifi] %s: 等待命令结束失败 (%d)\n", label, errno);
        return -1;
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        printf("[Wifi] %s: 命令返回异常 (status=%d)\n", label, status);
        return -1;
    }
    return 0;
}

int wifi_connect_boot(void)
{
    char ssid[WIFI_CRED_MAX] = { 0 };
    char psk[WIFI_CRED_MAX]  = { 0 };
    char cmd[192];
    int critical_failed = 0;

    if (load_creds(ssid, psk) != 0) {
        printf("[Wifi] 未配置 Wi-Fi，跳过自动联网\n");
        printf("[Wifi] 配置方法（任选其一）:\n");
        printf("[Wifi]   1) nsh> set WIFI_SSID <热点名>\n");
        printf("[Wifi]      nsh> set WIFI_PSK <密码>\n");
        printf("[Wifi]      nsh> ai_interview        （首次运行会自动记住）\n");
        printf("[Wifi]   2) 在 %s 写两行: SSID、密码\n", WIFI_PREF_PATH);
        return -1;
    }

    if (!cred_ok(ssid) || !cred_ok(psk)) {
        printf("[Wifi] 凭据含不支持的字符（空格/引号/分号/管道等），拒绝执行\n");
        return -2;
    }

    printf("[Wifi] 开始连接热点 %s ...\n", ssid);
    fflush(stdout);         /* 串口缓冲：连接过程要几秒，先把这句吐出去 */

    /* ifup 在"已经 up"时可能返回非 0 —— 只提示，不算失败。 */
    snprintf(cmd, sizeof(cmd), "ifup " WIFI_IFACE);
    if (run_cmd(cmd, "启用网卡") != 0) {
        printf("[Wifi] 提示: ifup 返回非 0（网卡可能已经启用），继续\n");
    }

    snprintf(cmd, sizeof(cmd), "wapi mode " WIFI_IFACE " 2");
    if (run_cmd(cmd, "设置 STA 模式") != 0) {
        critical_failed++;
    }

    snprintf(cmd, sizeof(cmd), "wapi psk " WIFI_IFACE " %s 3", psk);
    if (run_cmd(cmd, "设置 WPA2 密码") != 0) {
        critical_failed++;
    }

    snprintf(cmd, sizeof(cmd), "wapi essid " WIFI_IFACE " %s 1", ssid);
    if (run_cmd(cmd, "设置热点名") != 0) {
        critical_failed++;
    }

    snprintf(cmd, sizeof(cmd), "renew " WIFI_IFACE);
    if (run_cmd(cmd, "获取 IP（DHCP）") != 0) {
        critical_failed++;
    }

    /* Realtek 省电模式是 wlan0 随机掉线的头号嫌疑（README 4.5.1）。
     * 失败不致命：只是少了一道稳定性保险。 */
    snprintf(cmd, sizeof(cmd), "wapi power_save " WIFI_IFACE " off");
    if (run_cmd(cmd, "关闭省电") != 0) {
        printf("[Wifi] 提示: 关闭省电失败，继续\n");
    }

    if (critical_failed != 0) {
        printf("[Wifi] 有 %d 条关键命令失败 —— 连接可能未建立\n", critical_failed);
        printf("[Wifi] 检查热点名/密码、热点是否已开、板子是否在覆盖范围内\n");
        return -3;
    }

    printf("[Wifi] 联网命令执行完毕（连接结果以云端健康检查为准）\n");
    return 0;
}
