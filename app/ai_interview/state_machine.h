/*
 * AI模拟面试官 — 状态机头文件
 * 负责：B同学
 */

#ifndef __STATE_MACHINE_H__
#define __STATE_MACHINE_H__

typedef enum {
    STATE_IDLE = 0,
    STATE_RECORDING,
    STATE_UPLOADING,
    STATE_PLAYING,
    STATE_ERROR
} system_state_t;

typedef enum {
    EVENT_BUTTON_PRESS,
    EVENT_RECORD_DONE,
    EVENT_RECORD_TIMEOUT,
    EVENT_UPLOAD_SUCCESS,
    EVENT_UPLOAD_FAIL,
    EVENT_PLAY_DONE,
    EVENT_RETRY,
    EVENT_ERROR
} system_event_t;

typedef enum {
    LED_OFF = 0,
    LED_GREEN,
    LED_RED,
    LED_BLUE
} led_color_t;

typedef enum {
    LED_MODE_OFF = 0,
    LED_MODE_ON,
    LED_MODE_BLINK,
    LED_MODE_BREATH
} led_mode_t;

void state_machine_init(void);
void state_machine_post_event(system_event_t event);
system_state_t state_machine_get_current_state(void);
void led_set(led_color_t color, led_mode_t mode);
int state_machine_is_busy(void);

#endif /* __STATE_MACHINE_H__ */
