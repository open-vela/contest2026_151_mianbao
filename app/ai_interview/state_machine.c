/*
 * AI模拟面试官 — 状态机实现
 * 负责：B同学
 * IDLE -> RECORDING -> UPLOADING -> PLAYING -> IDLE
 */

#include <stdio.h>
#include "state_machine.h"

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
    switch (state) {
        case STATE_IDLE:     led_set(LED_GREEN, LED_MODE_ON); break;
        case STATE_RECORDING: led_set(LED_RED, LED_MODE_BLINK); break;
        case STATE_UPLOADING: led_set(LED_BLUE, LED_MODE_BREATH); break;
        case STATE_PLAYING:  led_set(LED_GREEN, LED_MODE_ON); break;
        case STATE_ERROR:    led_set(LED_RED, LED_MODE_ON); break;
    }
}

void state_machine_init(void)
{
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

void led_set(led_color_t color, led_mode_t mode)
{
    printf("[LED] 颜色=%d, 模式=%d\n", color, mode);
}
