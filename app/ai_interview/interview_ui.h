/*
 * 面试官屏幕界面（LVGL）—— 2026-10-16 加
 *
 * 为什么有这一层：板子上装着 8 寸触摸屏，LVGL/驱动/触摸在固件里本来就全开
 * （打地鼠就是用它跑的）。这一版先把三件事搬上屏：
 *   1. 待机页 —— 产品名 + 「按 K1 开始面试」
 *   2. 面试中页 —— 一个大大的「面试中」
 *   3. 岗位可视化 —— K3 切换后，两页上的岗位文字立刻跟着变
 * 触摸用于屏上的音量控件（2026-10-19；两页各一排「- 音量 X% +」）。
 * 布局按实际 fb 高度自适应：小屏压缩坐标、音量排贴底摆放。
 *
 * ⚠️ 三条线程纪律（本板 LVGL 配的是 LV_OS_NONE，**无线程安全**）：
 *   1. 本文件的函数**只允许主线程调用**（main.c 的主循环）；
 *   2. 工作线程只更新共享状态，绝不碰界面；
 *   3. 主循环每个节拍（100ms）调一次 `interview_ui_pump()` 即可 —— 界面是静态
 *      文字，10Hz 刷新足够，不必为它改主循环节奏。
 *
 * ⚠️ **屏是附件，不是主链路**：初始化失败只打印告警、面试照常跑（同 §11.25
 * "优雅退化"的取舍）。main.c 不因屏的问题中断。
 */
#ifndef __INTERVIEW_UI_H__
#define __INTERVIEW_UI_H__

/* 初始化：初始化 LVGL + 建好两页，显示待机页。返回 0 成功、-1 失败（无屏可用）。 */
int interview_ui_init(void);

/* 每个主循环节拍调用：推进 LVGL 定时器（刷新界面）。未初始化时是 no-op。 */
void interview_ui_pump(void);

/* 当前岗位变化 —— K3 切换后调用，两页上的岗位文字都会更新。 */
void interview_ui_set_role(const char *role);

/* 当前压力档位变化 —— K2 赛前切换后调用（温和 / 标准 / 压力）。 */
void interview_ui_set_pressure(const char *pressure);

/* 触摸音量控件（2026-10-19）：每次按 ± 按钮上报 ±1，由调用方决定步长（一般 10%）。
 * 回调运行在**主线程**（LVGL 的事件上下文）—— 与其它界面函数同一线程纪律。 */
void interview_ui_set_volume_cb(void (*cb)(int delta));

/* 当前音量百分比（0~100）—— 两页上的"音量 X%"都会更新。 */
void interview_ui_set_volume(int percent);

/* 会话开始/结束 → 切页：1 = 面试中页，0 = 待机页。只在真的变化时才动界面。 */
void interview_ui_set_session(int in_session);

#endif /* __INTERVIEW_UI_H__ */
