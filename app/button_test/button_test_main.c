/****************************************************************************
 * app/button_test/button_test_main.c
 *
 * 按键 GPIO 测试程序
 * 用于确认按键对应的 GPIO 引脚
 *
 * 使用方法:
 *   nsh> button_test
 *
 * 测试步骤:
 *   1. 程序会逐个读取 GPIO 状态
 *   2. 按下按键，观察哪个 GPIO 状态发生变化
 *   3. 记录下 K1、K2、K3 对应的 GPIO 引脚号
 ****************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <nuttx/ioexpander/gpio.h>

#define GPIO_DEVICE "/dev/gpio"
#define TEST_COUNT  20  /* 测试次数 */
#define TEST_DELAY_US 500000  /* 500ms 延迟 */

static int read_gpio(int gpio_num)
{
    char dev_path[16];
    int fd;
    int ret;
    bool value = false;

    /* 构建设备路径 */
    snprintf(dev_path, sizeof(dev_path), "%s%d", GPIO_DEVICE, gpio_num);

    /* 打开 GPIO 设备 */
    fd = open(dev_path, O_RDWR);
    if (fd < 0)
    {
        printf("  无法打开 %s (错误: %d)\n", dev_path, fd);
        return -1;
    }

    /* 尝试读取 GPIO 值（不设置模式） */
    ret = ioctl(fd, GPIOC_READ, (unsigned long)((uintptr_t)&value));
    if (ret < 0)
    {
        printf("  读取失败 (错误: %d)\n", ret);
        close(fd);
        return -1;
    }

    close(fd);
    return value ? 1 : 0;
}

int main(int argc, char *argv[])
{
    int i, j;
    int gpio_count = 6;  /* 测试 GPIO0 - GPIO5 */
    int last_values[6];
    int current_values[6];

    printf("\n");
    printf("========================================\n");
    printf("  按键 GPIO 测试程序 v1.0\n");
    printf("  队伍: mianbao (contest2026_151)\n");
    printf("========================================\n\n");

    printf("说明:\n");
    printf("  - 程序会持续读取 GPIO 状态\n");
    printf("  - 按下 K1、K2、K3 按键，观察哪个 GPIO 状态发生变化\n");
    printf("  - 按键按下时值为 0，松开时值为 1\n");
    printf("  - 按 Ctrl+C 退出\n\n");

    /* 读取初始状态 */
    printf("=== 初始 GPIO 状态 ===\n");
    for (i = 0; i < gpio_count; i++)
    {
        printf("[GPIO%d] 尝试读取...\n", i);
        last_values[i] = read_gpio(i);
        if (last_values[i] >= 0)
        {
            printf("[GPIO%d] 初始值: %d\n", i, last_values[i]);
        }
        else
        {
            printf("[GPIO%d] 无法读取\n", i);
            last_values[i] = -1;
        }
    }

    printf("\n=== 等待按键按下 ===\n");
    printf("请按下 K1、K2 或 K3 按键...\n\n");

    /* 持续监测 GPIO 状态变化 */
    for (i = 0; i < TEST_COUNT; i++)
    {
        usleep(TEST_DELAY_US);

        for (j = 0; j < gpio_count; j++)
        {
            current_values[j] = read_gpio(j);
            if (current_values[j] >= 0 && last_values[j] >= 0)
            {
                if (current_values[j] != last_values[j])
                {
                    printf("[GPIO%d] 状态变化: %d -> %d", j, last_values[j], current_values[j]);
                    if (current_values[j] == 0)
                    {
                        printf(" (按键按下)");
                    }
                    else
                    {
                        printf(" (按键松开)");
                    }
                    printf("\n");
                }
            }
        }

        /* 保存当前状态 */
        for (j = 0; j < gpio_count; j++)
        {
            if (current_values[j] >= 0)
            {
                last_values[j] = current_values[j];
            }
        }
    }

    printf("\n========================================\n");
    printf("  测试完成！\n");
    printf("  请记录下按键对应的 GPIO 引脚号\n");
    printf("========================================\n\n");

    return 0;
}
