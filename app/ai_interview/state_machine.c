/*
 * AI模拟面试官 — 状态机实现
 * 负责：B同学
 * IDLE -> RECORDING -> UPLOADING -> PLAYING -> IDLE
 */

#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <nuttx/ioexpander/gpio.h>
#include "state_machine.h"

/* LED GPIO 引脚定义 */
#define LED1_GPIO  0   /* GPIO0 控制 LED1 */
#define LED2_GPIO  2   /* GPIO2 控制 LED2 */

/* LED 文件描述符 */
static int g_led1_fd = -1;
static int g_led2_fd = -1;

static system_state_t g_current_state = STATE_IDLE;
static int g_retry_count = 0;
#define MAX_RETRY_COUNT 3

static const char* state_names[] = {"IDLE", "RECORDING", "UPLOADING", "PLAYING", "ERROR"};
static const char* event_names[] = {"BUTTON_PRESS", "RECORD_DONE", "RECORD_TIMEOUT", "UPLOAD_SUCCESS", "UPLOAD_FAIL", "PLAY_DONE", "RETRY", "ERROR"};

static system_state_t get_next_state(system_state_t current, system_event_t event)
{
    switch (current) {
        case STATE_IDLE:
            if (event == EVENT_BUTTON_PRESS) { g_retry_count = 0; return STATE_RECORDING; }
            return current;
        case STATE_RECORDING:
            if (event == EVENT_RECORD_DONE || event == EVENT_RECORD_TIMEOUT) return STATE_UPLOADING;
            if (event == EVENT_ERROR) return STATE_IDLE;
            return current;
        case STATE_UPLOADING:
            if (event == EVENT_UPLOAD_SUCCESS) return STATE_PLAYING;
            if (event == EVENT_UPLOAD_FAIL) {
                g_retry_count++;
                if (g_retry_count >= MAX_RETRY_COUNT) return STATE_IDLE;
                return STATE_ERROR;
            }
            return current;
        case STATE_PLAYING:
            if (event == EVENT_PLAY_DONE) return STATE_IDLE;
            return current;
        case STATE_ERROR:
            if (event == EVENT_BUTTON_PRESS) { g_retry_count = 0; return STATE_IDLE; }
            if (event == EVENT_RETRY) return STATE_UPLOADING;
            return current;
    }
    return STATE_IDLE;
}

static void update_led_by_state(system_state_t state)
{
    /* 先关闭所有 LED */
    if (g_led1_fd >= 0) {
        ioctl(g_led1_fd, GPIOC_WRITE, 1);  /* LED1 灭 */
    }
    if (g_led2_fd >= 0) {
        ioctl(g_led2_fd, GPIOC_WRITE, 1);  /* LED2 灭 */
    }

    switch (state) {
        case STATE_IDLE:
            /* 待机: LED1 常亮 */
            if (g_led1_fd >= 0) {
                ioctl(g_led1_fd, GPIOC_WRITE, 0);  /* LED1 亮 */
            }
            break;
        case STATE_RECORDING:
            /* 录音中: LED1 快闪 (200ms间隔) */
            printf("[LED] 录音中 - LED1 快闪\n");
            break;
        case STATE_UPLOADING:
            /* 上传中: LED1 慢闪 (800ms间隔) */
            printf("[LED] 上传中 - LED1 慢闪\n");
            break;
        case STATE_PLAYING:
            /* 播放中: LED2 常亮 */
            if (g_led2_fd >= 0) {
                ioctl(g_led2_fd, GPIOC_WRITE, 0);  /* LED2 亮 */
            }
            break;
        case STATE_ERROR:
            /* 错误: LED1 三短闪循环 */
            printf("[LED] 错误状态 - LED1 三短闪\n");
            break;
    }
}

void state_machine_init(void)
{
    /* 初始化 LED GPIO */
    g_led1_fd = open("/dev/gpio0", O_RDWR);
    if (g_led1_fd < 0) {
        printf("[StateMachine] 警告: 无法打开 LED1 GPIO (GPIO0)\n");
    } else {
        /* 设置为输出模式 */
        ioctl(g_led1_fd, GPIOC_SETPINTYPE, GPIO_OUTPUT_PIN);
        /* 初始状态: LED1 灭 */
        ioctl(g_led1_fd, GPIOC_WRITE, 1);
        printf("[StateMachine] LED1 GPIO (GPIO0) 初始化成功\n");
    }

    g_led2_fd = open("/dev/gpio2", O_RDWR);
    if (g_led2_fd < 0) {
        printf("[StateMachine] 警告: 无法打开 LED2 GPIO (GPIO2)\n");
    } else {
        /* 设置为输出模式 */
        ioctl(g_led2_fd, GPIOC_SETPINTYPE, GPIO_OUTPUT_PIN);
        /* 初始状态: LED2 灭 */
        ioctl(g_led2_fd, GPIOC_WRITE, 1);
        printf("[StateMachine] LED2 GPIO (GPIO2) 初始化成功\n");
    }

    g_current_state = STATE_IDLE;
    g_retry_count = 0;
    printf("[StateMachine] 初始化完成，当前状态: %s\n", state_names[g_current_state]);
    update_led_by_state(STATE_IDLE);
}

void state_machine_post_event(system_event_t event)
{
    system_state_t new_state = get_next_state(g_current_state, event);
    if (new_state != g_current_state) {
        printf("[StateMachine] %s --[%s]--> %s\n", state_names[g_current_state], event_names[event], state_names[new_state]);
        g_current_state = new_state;
        update_led_by_state(new_state);
        switch (new_state) {
            case STATE_RECORDING: printf("[StateMachine] 开始录音...\n"); break;
            case STATE_UPLOADING: printf("[StateMachine] 开始上传音频...\n"); break;
            case STATE_PLAYING:   printf("[StateMachine] 开始播放...\n"); break;
            case STATE_ERROR:     printf("[StateMachine] 错误状态，等待处理...\n"); break;
            default: break;
        }
    }
}

system_state_t state_machine_get_current_state(void) { return g_current_state; }
int state_machine_is_busy(void) {
    return (g_current_state == STATE_RECORDING || g_current_state == STATE_UPLOADING || g_current_state == STATE_PLAYING);
}

/* LED 闪烁控制变量 */
static int g_led_blink_state = 0;  /* 闪烁状态: 0=灭, 1=亮 */
static int g_led_blink_count = 0;  /* 闪烁计数 */
static int g_led_blink_pattern = 0; /* 闪烁模式: 0=快闪, 1=慢闪, 2=三短闪 */

void state_machine_update_led(void)
{
    switch (g_current_state) {
        case STATE_IDLE:
            /* 待机: LED1 常亮 */
            if (g_led1_fd >= 0) {
                ioctl(g_led1_fd, GPIOC_WRITE, 0);  /* LED1 亮 */
            }
            break;

        case STATE_RECORDING:
            /* 录音中: LED1 快闪 (200ms间隔) */
            if (g_led1_fd >= 0) {
                g_led_blink_state = !g_led_blink_state;
                ioctl(g_led1_fd, GPIOC_WRITE, g_led_blink_state ? 1 : 0);
            }
            break;

        case STATE_UPLOADING:
            /* 上传中: LED1 慢闪 (800ms间隔) */
            if (g_led1_fd >= 0) {
                g_led_blink_state = !g_led_blink_state;
                ioctl(g_led1_fd, GPIOC_WRITE, g_led_blink_state ? 1 : 0);
            }
            break;

        case STATE_PLAYING:
            /* 播放中: LED2 常亮 */
            if (g_led2_fd >= 0) {
                ioctl(g_led2_fd, GPIOC_WRITE, 0);  /* LED2 亮 */
            }
            break;

        case STATE_ERROR:
            /* 错误: LED1 三短闪循环 */
            if (g_led1_fd >= 0) {
                g_led_blink_count++;
                if (g_led_blink_count <= 6) {  /* 3次闪烁 = 6次状态切换 */
                    g_led_blink_state = !g_led_blink_state;
                    ioctl(g_led1_fd, GPIOC_WRITE, g_led_blink_state ? 1 : 0);
                } else if (g_led_blink_count <= 12) {  /* 停顿 */
                    ioctl(g_led1_fd, GPIOC_WRITE, 1);  /* LED1 灭 */
                } else {
                    g_led_blink_count = 0;  /* 重新开始 */
                }
            }
            break;
    }
}

void led_set(led_color_t color, led_mode_t mode)
{
    printf("[LED] 颜色=%d, 模式=%d\n", color, mode);

    /* 根据颜色选择 GPIO */
    int fd = -1;
    if (color == LED_GREEN || color == LED_RED) {
        fd = g_led1_fd;  /* LED1 用于绿色/红色指示 */
    } else if (color == LED_BLUE) {
        fd = g_led2_fd;  /* LED2 用于蓝色指示 */
    }

    if (fd < 0) {
        printf("[LED] 错误: GPIO 未初始化\n");
        return;
    }

    /* 根据模式控制 LED */
    switch (mode) {
        case LED_MODE_ON:
            /* 常亮 - 低电平有效 */
            ioctl(fd, GPIOC_WRITE, 0);
            break;
        case LED_MODE_OFF:
            /* 熄灭 - 高电平有效 */
            ioctl(fd, GPIOC_WRITE, 1);
            break;
        case LED_MODE_BLINK:
            /* 闪烁 - 快闪 (200ms间隔) */
            printf("[LED] 闪烁模式需要在主循环中实现\n");
            break;
        case LED_MODE_BREATH:
            /* 呼吸灯 - 慢闪 (800ms间隔) */
            printf("[LED] 呼吸灯模式需要在主循环中实现\n");
            break;
        default:
            break;
    }
}
