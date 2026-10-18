/*
 * 面试官屏幕界面（LVGL）—— 实现；设计取舍见 interview_ui.h 顶部
 *
 * 素材约定与打地鼠（~/vela-opensource/apps/examples/MyWhackMole）一致：
 * 字体走板子上的 /data/res/fonts/，用 FreeType 渲染中文。
 * 本文件不加载任何图片 —— 这一版全是文字与色块，少一个素材就少一个失败点。
 */
#include <nuttx/config.h>

#include <stdio.h>
#include <string.h>

#include <lvgl/lvgl.h>

#include "interview_ui.h"

/* 中文渲染依赖它；文件不在也不致命 —— 退回 LVGL 内置字体（只有 ASCII），
 * 中文会显示不出来，但界面结构、切页、岗位切换照常（日志里有告警）。 */
#define UI_FONT_PATH  "/data/res/fonts/MiSans-Normal.ttf"

/* 三个字号：标题 / 正文 / 提示 */
#define UI_FONT_TITLE 44
#define UI_FONT_BODY  28
#define UI_FONT_HINT  22

/* 配色：深底白字、岗位用青色强调（现场拍照/投影都清楚） */
#define UI_BG_COLOR    0x0F1B2A
#define UI_TEXT_COLOR  0xFFFFFF
#define UI_ROLE_COLOR  0x4FC3F7
#define UI_HINT_COLOR  0x9FB3C8

static lv_obj_t *g_page_idle;
static lv_obj_t *g_page_live;
static lv_obj_t *g_idle_role;
static lv_obj_t *g_live_role;

static const lv_font_t *g_font_title;
static const lv_font_t *g_font_body;
static const lv_font_t *g_font_hint;

static int g_ready;             /* LVGL 与两页都就绪才置 1 —— pump/切页的守卫 */
static int g_in_session = -1;   /* 界面当前在哪一页；-1 = 尚未决定 */

/* ---------- 字体 ---------- */

static const lv_font_t *load_font(int size, const lv_font_t *fallback)
{
    const lv_font_t *font = lv_freetype_font_create(
        UI_FONT_PATH, LV_FREETYPE_FONT_RENDER_MODE_BITMAP, size,
        LV_FREETYPE_FONT_STYLE_NORMAL);

    if (font == NULL) {
        printf("[UI] 字体加载失败（%s，字号 %d）—— 退回内置字体，中文将显示不出来\n",
               UI_FONT_PATH, size);
        return fallback;
    }
    return font;
}

/* ---------- 构件 ---------- */

/* 一整页：铺满屏、深底、不可滚动 —— 两页都这么建，靠显隐切换。 */
static lv_obj_t *make_page(void)
{
    lv_obj_t *page = lv_obj_create(lv_screen_active());

    lv_obj_set_size(page, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(page, lv_color_hex(UI_BG_COLOR), 0);
    lv_obj_set_style_bg_opa(page, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(page, 0, 0);
    lv_obj_set_style_radius(page, 0, 0);
    lv_obj_set_style_pad_all(page, 0, 0);
    lv_obj_remove_flag(page, LV_OBJ_FLAG_SCROLLABLE);
    return page;
}

static lv_obj_t *make_label(lv_obj_t *parent, const char *text,
                            const lv_font_t *font, uint32_t color,
                            lv_align_t align, int x, int y)
{
    lv_obj_t *label = lv_label_create(parent);

    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(color), 0);
    lv_obj_align(label, align, x, y);
    return label;
}

static void build_idle_page(void)
{
    g_page_idle = make_page();

    /* 产品名。队伍一行与串口横幅同款，评委对着屏就能对上号。 */
    make_label(g_page_idle, "AI 模拟面试官", g_font_title, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, -120);
    make_label(g_page_idle, "contest2026_151 · mianbao", g_font_hint, UI_HINT_COLOR,
               LV_ALIGN_CENTER, 0, -58);

    /* 岗位：K3 切换后这一行立刻跟着变 —— "岗位可视化"就落在这里 */
    g_idle_role = make_label(g_page_idle, "当前岗位：", g_font_body, UI_ROLE_COLOR,
                             LV_ALIGN_CENTER, 0, 30);

    make_label(g_page_idle, "按 K1 开始面试", g_font_body, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, 120);
    make_label(g_page_idle, "按 K3 切换岗位（两场面试之间）", g_font_hint,
               UI_HINT_COLOR, LV_ALIGN_CENTER, 0, 172);
}

static void build_live_page(void)
{
    g_page_live = make_page();

    make_label(g_page_live, "面试中…", g_font_title, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, -60);
    g_live_role = make_label(g_page_live, "", g_font_body, UI_ROLE_COLOR,
                             LV_ALIGN_CENTER, 0, 25);
    make_label(g_page_live, "请对着开发板回答，说完停顿四秒", g_font_hint,
               UI_HINT_COLOR, LV_ALIGN_CENTER, 0, 105);

    lv_obj_add_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);   /* 开机先显示待机页 */
}

/* ---------- 对外接口 ---------- */

int interview_ui_init(void)
{
    static lv_nuttx_result_t result;
    lv_nuttx_dsc_t info;

    if (!lv_is_initialized()) {
        lv_init();

        lv_nuttx_dsc_init(&info);
#ifdef CONFIG_LV_USE_NUTTX_LCD
        info.fb_path = "/dev/lcd0";
#endif
        /* 触摸这一版不用（设计见头文件）—— 不填 input_path，LVGL 就没有输入设备 */
        lv_nuttx_init(&info, &result);

        if (result.disp == NULL) {
            printf("[UI] 显示屏初始化失败 —— 本次不带屏运行\n");
            return -1;
        }
    } else if (lv_display_get_default() == NULL) {
        /* 别的应用（如打地鼠）初始化过 LVGL 又没留下可用的显示 —— 同样退化。
         * 本应用重启后能复用已初始化的 LVGL，靠的就是上面这条分支。 */
        printf("[UI] LVGL 已初始化但没有可用显示 —— 本次不带屏运行\n");
        return -1;
    }

    g_font_title = load_font(UI_FONT_TITLE, lv_font_default());
    g_font_body  = load_font(UI_FONT_BODY,  lv_font_default());
    g_font_hint  = load_font(UI_FONT_HINT,  lv_font_default());

    build_idle_page();
    build_live_page();

    g_ready = 1;
    g_in_session = 0;
    printf("[UI] 屏幕界面就绪（待机页）\n");
    return 0;
}

void interview_ui_pump(void)
{
    if (g_ready) {
        /* 返回的"距下次刷新毫秒数"这里不用 —— 主循环 100ms 一拍，
         * 界面是静态文字，10Hz 足够（头文件里有取舍说明）。 */
        lv_timer_handler();
    }
}

void interview_ui_set_role(const char *role)
{
    if (role == NULL || role[0] == '\0') {
        return;
    }
    if (!g_ready) {
        return;
    }
    if (g_idle_role != NULL) {
        lv_label_set_text_fmt(g_idle_role, "当前岗位：%s", role);
    }
    if (g_live_role != NULL) {
        lv_label_set_text_fmt(g_live_role, "岗位：%s", role);
    }
}

void interview_ui_set_session(int in_session)
{
    in_session = in_session ? 1 : 0;

    if (!g_ready || in_session == g_in_session) {
        return;
    }
    g_in_session = in_session;

    if (in_session) {
        lv_obj_add_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(g_page_live);
    } else {
        lv_obj_add_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(g_page_idle);
    }
}
