/****************************************************************************
 * app/led_test/led_test_main.c
 *
 * LED GPIO 测试程序
 * 用于确认 LED 对应的 GPIO 引脚
 *
 * 使用方法:
 *   nsh> led_test
 *
 * 测试步骤:
 *   1. 程序会逐个测试 GPIO 引脚
 *   2. 观察哪个 GPIO 引脚控制 LED 亮灭
 *   3. 记录下 LED1 和 LED2 对应的 GPIO 引脚号
 ****************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <nuttx/ioexpander/gpio.h>

#define GPIO_DEVICE "/dev/gpio"
#define TEST_DELAY_US 500000  /* 500ms delay between tests */

static int read_gpio(int gpio_num)
{
    char dev_path[16];
    int fd;
    int ret;
    int value = -1;

    /* 构建设备路径 */
    snprintf(dev_path, sizeof(dev_path), "%s%d", GPIO_DEVICE, gpio_num);

    /* 打开 GPIO 设备 */
    fd = open(dev_path, O_RDWR);
    if (fd < 0)
    {
        return -1;
    }

    /* 尝试读取 GPIO 值 */
    ret = ioctl(fd, GPIOC_READ, (unsigned long)((uintptr_t)&value));
    if (ret < 0)
    {
        close(fd);
        return -1;
    }

    close(fd);
    return value;
}

static int test_gpio(int gpio_num)
{
    char dev_path[16];
    int fd;
    int ret;

    /* 构建设备路径 */
    snprintf(dev_path, sizeof(dev_path), "%s%d", GPIO_DEVICE, gpio_num);

    /* 打开 GPIO 设备 */
    fd = open(dev_path, O_RDWR);
    if (fd < 0)
    {
        printf("[GPIO%d] 无法打开 %s\n", gpio_num, dev_path);
        return -1;
    }

    /* 设置为输出模式 */
    ret = ioctl(fd, GPIOC_SETPINTYPE, GPIO_OUTPUT_PIN);
    if (ret < 0)
    {
        printf("[GPIO%d] 设置输出模式失败\n", gpio_num);
        close(fd);
        return -1;
    }

    /* 测试亮灭 - 增加暂停时间，方便观察 */
    printf("[GPIO%d] 测试: LED 亮 (等待2秒)...", gpio_num);
    ioctl(fd, GPIOC_WRITE, 0);  /* 低电平有效，输出0=亮 */
    usleep(2000000);  /* 等待2秒，方便观察 */

    printf(" LED 灭 (等待1秒)...");
    ioctl(fd, GPIOC_WRITE, 1);  /* 输出1=灭 */
    usleep(1000000);  /* 等待1秒 */

    printf(" 完成\n");

    close(fd);
    return 0;
}

int main(int argc, char *argv[])
{
    int i;
    int gpio_count = 6;  /* 只测试 GPIO0 - GPIO5 */
    int led1_gpio = -1;  /* LED1 对应的 GPIO */
    int led2_gpio = 2;   /* LED2 对应的 GPIO (已确认) */

    printf("\n");
    printf("========================================\n");
    printf("  LED GPIO 测试程序 v1.0\n");
    printf("  队伍: mianbao (contest2026_151)\n");
    printf("========================================\n\n");

    printf("说明:\n");
    printf("  - 程序将逐个测试 GPIO 引脚\n");
    printf("  - 观察哪个 GPIO 引脚控制 LED 亮灭\n");
    printf("  - 两个 LED 都是绿色，低电平有效\n");
    printf("  - 测试间隔: %d ms\n\n", TEST_DELAY_US / 1000);

    /* 第一阶段：读取所有 GPIO 的当前状态 */
    printf("=== 第一阶段：读取 GPIO 状态 ===\n");
    printf("请确保 LED1 是亮着的，然后运行此程序\n\n");

    for (i = 0; i < gpio_count; i++)
    {
        int value = read_gpio(i);
        if (value >= 0)
        {
            printf("[GPIO%d] 当前值: %d\n", i, value);
        }
        else
        {
            printf("[GPIO%d] 无法读取\n", i);
        }
    }

    printf("\n=== 第二阶段：逐个测试 GPIO ===\n");
    printf("请观察哪个 GPIO 让 LED 亮了\n\n");

    for (i = 0; i < gpio_count; i++)
    {
        test_gpio(i);
    }

    printf("\n");
    printf("========================================\n");
    printf("  测试完成！\n");
    printf("  已确认: GPIO%d 控制 LED2\n", led2_gpio);
    printf("  请观察第一阶段的 GPIO 状态，找到 LED1 对应的 GPIO\n");
    printf("  (LED1 亮着时，对应的 GPIO 值应该是 0)\n");
    printf("========================================\n\n");

    return 0;
}
