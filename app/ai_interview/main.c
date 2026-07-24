/*
 * AI模拟面试官 — 主程序入口
 * 负责：A/B同学
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <nuttx/ioexpander/gpio.h>
#include "state_machine.h"

#define RECORD_TIMEOUT_SECONDS  180
#define SILENCE_TIMEOUT_SECONDS 2

/* 按键 GPIO 引脚定义 */
#define KEY1_GPIO  1   /* K1 按键 */
#define KEY2_GPIO  3   /* K2 按键 */
#define KEY3_GPIO  4   /* K3 按键 */

/* 按键文件描述符 */
static int g_key1_fd = -1;
static int g_key2_fd = -1;
static int g_key3_fd = -1;

/* 按键状态 */
static int g_key1_last_state = 1;  /* 默认高电平（松开） */
static int g_key2_last_state = 1;
static int g_key3_last_state = 1;

/* 初始化按键 GPIO */
static void init_buttons(void)
{
    /* 打开 K1 GPIO */
    g_key1_fd = open("/dev/gpio1", O_RDWR);
    if (g_key1_fd < 0) {
        printf("[Main] 警告: 无法打开 K1 GPIO (GPIO1)\n");
    } else {
        /* 设置为输入模式（带下拉电阻） */
        ioctl(g_key1_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K1 GPIO (GPIO1) 初始化成功\n");
    }

    /* 打开 K2 GPIO */
    g_key2_fd = open("/dev/gpio3", O_RDWR);
    if (g_key2_fd < 0) {
        printf("[Main] 警告: 无法打开 K2 GPIO (GPIO3)\n");
    } else {
        /* 设置为输入模式（带下拉电阻） */
        ioctl(g_key2_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K2 GPIO (GPIO3) 初始化成功\n");
    }

    /* 打开 K3 GPIO */
    g_key3_fd = open("/dev/gpio4", O_RDWR);
    if (g_key3_fd < 0) {
        printf("[Main] 警告: 无法打开 K3 GPIO (GPIO4)\n");
    } else {
        /* 设置为输入模式（带下拉电阻） */
        ioctl(g_key3_fd, GPIOC_SETPINTYPE, GPIO_INPUT_PIN_PULLDOWN);
        printf("[Main] K3 GPIO (GPIO4) 初始化成功\n");
    }
}

/* 读取按键状态 */
static int read_button(int fd)
{
    bool value = false;
    if (fd < 0) {
        return -1;
    }
    ioctl(fd, GPIOC_READ, (unsigned long)((uintptr_t)&value));
    return value ? 1 : 0;
}

/* 检测按键按下（下降沿检测） */
static void check_buttons(void)
{
    int key1_state, key2_state, key3_state;

    /* 读取按键状态 */
    key1_state = read_button(g_key1_fd);
    key2_state = read_button(g_key2_fd);
    key3_state = read_button(g_key3_fd);

    /* 检测 K1 按下（下降沿） */
    if (key1_state == 0 && g_key1_last_state == 1) {
        printf("[Main] K1 按键按下\n");
        state_machine_post_event(EVENT_BUTTON_PRESS);
    }
    g_key1_last_state = key1_state;

    /* 检测 K2 按下（下降沿） */
    if (key2_state == 0 && g_key2_last_state == 1) {
        printf("[Main] K2 按键按下\n");
        /* K2 可用于其他功能，比如取消/返回 */
    }
    g_key2_last_state = key2_state;

    /* 检测 K3 按下（下降沿） */
    if (key3_state == 0 && g_key3_last_state == 1) {
        printf("[Main] K3 按键按下\n");
        /* K3 可用于其他功能，比如切换模式 */
    }
    g_key3_last_state = key3_state;
}

int main(int argc, char *argv[])
{
    printf("========================================\n");
    printf("  AI模拟面试官 - 端侧主程序 v0.1\n");
    printf("  队伍: mianbao (contest2026_151)\n");
    printf("========================================\n\n");

    /* 初始化状态机 */
    state_machine_init();

    /* 初始化按键 */
    init_buttons();

    printf("\n[Main] 系统就绪，等待按键开始面试...\n");
    printf("[Main] K1: 开始面试\n");
    printf("[Main] K2: 取消/返回\n");
    printf("[Main] K3: 切换模式\n\n");

    while (1) {
        /* 更新 LED 状态（处理闪烁等效果） */
        state_machine_update_led();

        /* 检测按键 */
        check_buttons();

        /* TODO: 静音检测 -> 投递 EVENT_RECORD_DONE */
        /* TODO: 录音超时检测 -> 投递 EVENT_RECORD_TIMEOUT */
        /* TODO: 上传完成回调 -> 投递 EVENT_UPLOAD_SUCCESS/FAIL */
        /* TODO: 播放完成回调 -> 投递 EVENT_PLAY_DONE */

        usleep(100000);  /* 100ms 更新间隔 */
    }

    return 0;
}
