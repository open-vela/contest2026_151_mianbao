/*
 * AI模拟面试官 — 主程序入口
 * 负责：A/B同学
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "state_machine.h"

#define RECORD_TIMEOUT_SECONDS  180
#define SILENCE_TIMEOUT_SECONDS 2

int main(int argc, char *argv[])
{
    printf("========================================\n");
    printf("  AI模拟面试官 - 端侧主程序 v0.1\n");
    printf("  队伍: mianbao (contest2026_151)\n");
    printf("========================================\n\n");

    state_machine_init();

    printf("\n[Main] 系统就绪，等待按键开始面试...\n");

    while (1) {
        /* TODO: 检测按键 -> 投递 EVENT_BUTTON_PRESS */
        /* TODO: 静音检测 -> 投递 EVENT_RECORD_DONE */
        /* TODO: 录音超时检测 -> 投递 EVENT_RECORD_TIMEOUT */
        /* TODO: 上传完成回调 -> 投递 EVENT_UPLOAD_SUCCESS/FAIL */
        /* TODO: 播放完成回调 -> 投递 EVENT_PLAY_DONE */

        usleep(100000);
    }

    return 0;
}
