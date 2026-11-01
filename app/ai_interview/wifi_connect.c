/*
 * AI模拟面试官 — 开机自动联网（2026-10-27 加）
 *
 * 为什么**不经过 nsh**（2026-10-31 真机事故后改）：
 *   * nsh 每次启动都会先执行 /etc/init.d/rcS；rcS 现在会自启 ai_interview。
 *     主程序里再 `posix_spawn("nsh", ...)`，就会重跑 rcS → 又启动一个主程序，
 *     无限递归、串口刷 `NuttShell (NSH)`（`g_nsh_script_initialized` 是进程内
 *     静态量，拦不住新 nsh）。
 *   * 现在：`ifup` 直接调 `netlib_ifup()`；`wapi` 与 `renew` 用 posix_spawn
 *     直接启动**内置命令**（不经过 nsh 的初始化），行为与手工命令一致；
 *     密码也不会出现在 shell 命令行里。
 *
 * 为什么逐条 spawn、不等一整串脚本：
 *   每条等它退出再跑下一条，顺序确定、失败点可读；代价是多几次任务创建，
 *   开机时多花一两秒，可以接受。
 *
 * 凭据安全：
 *   * **密码绝不打印、绝不写进仓库**；
 *   * 凭据只来自环境变量、串口首次配置或 /data/ai_interview_wifi；
 *   * 涉及密码的命令只打固定标签，日志里不出现明文；
 *   * 字符白名单校验（拒绝空格/引号/分号/管道等），避免配置被误写。
 */
#include <nuttx/config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <termios.h>
#include <spawn.h>
#include <sys/wait.h>
#include <netutils/netlib.h>

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

static int persist_creds(const char *ssid, const char *psk)
{
    FILE *fp = fopen(WIFI_PREF_PATH, "w");

    if (fp == NULL) {
        printf("[Wifi] 提示: 无法写入 %s（下次仍需重新设置）\n", WIFI_PREF_PATH);
        return -1;
    }
    fprintf(fp, "%s\n%s\n", ssid, psk);
    fclose(fp);
    printf("[Wifi] 凭据已保存到 %s（下次开机自动使用）\n", WIFI_PREF_PATH);
    return 0;
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
        (void)persist_creds(ssid, psk);   /* 首次设了环境变量就记住 */
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

/* 直接启动内置命令（wapi / renew）并等它结束 —— **不要经过 nsh**。
 *
 * 为什么不经 nsh（2026-10-31 真机踩到）：
 *   nsh 启动时会先执行 /etc/init.d/rcS；而 rcS 现在会自启 ai_interview。
 *   主程序里每 spawn 一个 nsh，就重新跑一遍 rcS → 又启动一个主程序 →
 *   又 spawn nsh → 无限递归，串口被 "NuttShell (NSH)" 刷屏停不下来。
 *   直接 spawn 内置命令不经过 nsh 的初始化，就没有这个问题。
 *
 * NuttX 的 posix_spawn 把 argv[0] 当任务名、argv[1..] 原样交给新任务，
 * 所以这里照正常命令行写 argv 即可。
 */
static int run_builtin(const char *prog, char *const argv[], const char *label)
{
    pid_t pid;
    int status = 0;
    int ret;

    ret = posix_spawn(&pid, prog, NULL, NULL, argv, NULL);
    if (ret != 0) {
        printf("[Wifi] %s: 启动 %s 失败 (%d)\n", label, prog, ret);
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

int wifi_have_creds(void)
{
    char ssid[WIFI_CRED_MAX];
    char psk[WIFI_CRED_MAX];

    return load_creds(ssid, psk) == 0;
}

int wifi_save_creds(const char *ssid, const char *psk)
{
    if (!cred_ok(ssid) || !cred_ok(psk)) {
        printf("[Wifi] 凭据不合法（空或含不支持字符），未保存\n");
        return -2;
    }
    return persist_creds(ssid, psk);
}

int wifi_connect_boot(void)
{
    char ssid[WIFI_CRED_MAX] = { 0 };
    char psk[WIFI_CRED_MAX]  = { 0 };
    char *mode_argv[]  = { (char *)"wapi", (char *)"mode",
                           (char *)WIFI_IFACE, (char *)"2", NULL };
    char *psk_argv[]   = { (char *)"wapi", (char *)"psk",
                           (char *)WIFI_IFACE, psk, (char *)"3", NULL };
    char *essid_argv[] = { (char *)"wapi", (char *)"essid",
                           (char *)WIFI_IFACE, ssid, (char *)"1", NULL };
    char *ps_argv[]    = { (char *)"wapi", (char *)"power_save",
                           (char *)WIFI_IFACE, (char *)"off", NULL };
    char *renew_argv[] = { (char *)"renew", (char *)WIFI_IFACE, NULL };
    int critical_failed = 0;

    if (load_creds(ssid, psk) != 0) {
        printf("[Wifi] 未配置 Wi-Fi，跳过自动联网\n");
        printf("[Wifi] 首次开机直接在串口输入即可（见 wifi_serial_setup）\n");
        return -1;
    }

    if (!cred_ok(ssid) || !cred_ok(psk)) {
        printf("[Wifi] 凭据含不支持的字符（空格/引号/分号/管道等），拒绝执行\n");
        return -2;
    }

    printf("[Wifi] 开始连接热点 %s ...\n", ssid);
    fflush(stdout);         /* 串口缓冲：连接过程要几秒，先把这句吐出去 */

    /* ifup 在"已经 up"时可能返回非 0 —— 只提示，不算失败。 */
    if (netlib_ifup(WIFI_IFACE) != 0) {
        printf("[Wifi] 提示: ifup 返回非 0（网卡可能已经启用），继续\n");
    }

    if (run_builtin("wapi", mode_argv, "设置 STA 模式") != 0) {
        critical_failed++;
    }

    if (run_builtin("wapi", psk_argv, "设置 WPA2 密码") != 0) {
        critical_failed++;
    }

    if (run_builtin("wapi", essid_argv, "设置热点名") != 0) {
        critical_failed++;
    }

    /* renew 内置命令的栈是 2MB（DHCP 客户端需要），单独任务跑；
     * 不要改成在当前线程直接调 netlib_obtain_ipv4addr —— 工作线程栈只有 256KB。 */
    if (run_builtin("renew", renew_argv, "获取 IP（DHCP）") != 0) {
        critical_failed++;
    }

    /* Realtek 省电模式是 wlan0 随机掉线的头号嫌疑（README 4.5.1）。
     * 失败不致命：只是少了一道稳定性保险。 */
    if (run_builtin("wapi", ps_argv, "关闭省电") != 0) {
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

/* ---------- 串口首次配置（2026-10-31） ---------- */

/* 密码输入时不回显：直接操作终端的 ECHO 位。
 * CONFIG_SERIAL_TERMIOS=y（本板已确认），换行/退格仍由 tty 的规范模式处理。 */
static void console_echo(int enable)
{
#ifdef CONFIG_SERIAL_TERMIOS
    struct termios t;

    if (tcgetattr(STDIN_FILENO, &t) == 0) {
        if (enable) {
            t.c_lflag |= ECHO;
        } else {
            t.c_lflag &= ~ECHO;
        }
        (void)tcsetattr(STDIN_FILENO, TCSANOW, &t);
    }
#else
    (void)enable;
#endif
}

static int read_console_line(const char *prompt, char *buf, size_t cap,
                             int hidden)
{
    printf("%s", prompt);
    fflush(stdout);

    if (hidden) {
        console_echo(0);
    }

    if (fgets(buf, (int)cap, stdin) == NULL) {
        if (hidden) {
            console_echo(1);
        }
        return -1;
    }

    /* 超长输入只取了前 cap-1 字节，把本行剩下的吃掉，
     * 免得下一行（密码）读到残留。 */
    if (strchr(buf, '\n') == NULL) {
        int c;

        while ((c = getchar()) != '\n' && c != EOF) {
        }
    }

    if (hidden) {
        console_echo(1);
        printf("\n");       /* 关了回显，换行得自己补 */
    }

    trim(buf);
    return 0;
}

int wifi_serial_setup(void)
{
    char ssid[WIFI_CRED_MAX];
    char psk[WIFI_CRED_MAX];
    int tries;

    /* 从串口工具启动时 stdin 才是终端；被重定向时不要傻等输入 */
    if (!isatty(STDIN_FILENO)) {
        printf("[Wifi] 标准输入不是串口终端，跳过串口配置\n");
        return -1;
    }

    printf("\n");
    printf("========================================\n");
    printf("  首次使用：配置 Wi-Fi\n");
    printf("  直接回车可跳过（之后可在屏幕右上角 Wi-Fi 重设）\n");
    printf("========================================\n");

    for (tries = 0; tries < 3; tries++) {
        if (read_console_line("热点名称（SSID）: ", ssid, sizeof(ssid), 0) != 0) {
            return -1;
        }
        if (ssid[0] == '\0') {
            printf("[Wifi] 已跳过串口配置\n");
            return -1;
        }
        if (!cred_ok(ssid)) {
            printf("[Wifi] SSID 含不支持的字符（空格/引号/分号/管道等），请重试\n");
            continue;
        }

        if (read_console_line("热点密码（输入不回显，输完回车）: ",
                              psk, sizeof(psk), 1) != 0) {
            return -1;
        }
        if (!cred_ok(psk)) {
            printf("[Wifi] 密码不能为空或含不支持的字符，请重试\n");
            continue;
        }
        if (strlen(psk) < 8 || strlen(psk) > 63) {
            printf("[Wifi] 密码长度应为 8~63 位（当前 %u 位），请重试\n",
                   (unsigned)strlen(psk));
            continue;
        }

        if (persist_creds(ssid, psk) != 0) {
            return -1;
        }

        printf("[Wifi] 已保存热点「%s」，开始连接...\n", ssid);
        return 0;
    }

    printf("[Wifi] 连续 3 次输入不合法，跳过（可在屏幕右上角 Wi-Fi 重设）\n");
    return -1;
}
