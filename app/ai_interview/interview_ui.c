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

/* 触摸屏设备（与打地鼠同一块板、同一个设备名）。2026-10-19 起用于屏上音量控件。 */
#define UI_TOUCH_PATH "/dev/input0"

/* 三个字号：标题 / 正文 / 提示 */
#define UI_FONT_TITLE 44
#define UI_FONT_BODY  28
#define UI_FONT_HINT  22

/* 配色：深底白字、岗位用青色强调（现场拍照/投影都清楚） */
#define UI_BG_COLOR    0x0F1B2A
#define UI_TEXT_COLOR  0xFFFFFF
#define UI_ROLE_COLOR  0x4FC3F7
#define UI_HINT_COLOR  0x9FB3C8
#define UI_BTN_COLOR   0x2A4A66

static lv_obj_t *g_page_idle;
static lv_obj_t *g_page_live;
static lv_obj_t *g_page_wifi;
static lv_obj_t *g_wifi_ssid_ta;
static lv_obj_t *g_wifi_psk_ta;
static lv_obj_t *g_wifi_kb;
static lv_obj_t *g_wifi_status;
static ui_wifi_cb_t g_wifi_cb;
static int g_wifi_page_visible;
static lv_obj_t *g_idle_role;
static lv_obj_t *g_live_role;
static lv_obj_t *g_idle_pressure;
static lv_obj_t *g_live_pressure;
static lv_obj_t *g_idle_volume;
static lv_obj_t *g_live_volume;
static void (*g_volume_cb)(int delta);

static const lv_font_t *g_font_title;
static const lv_font_t *g_font_body;
static const lv_font_t *g_font_hint;

/* 前向声明：待机页的「Wi-Fi」按钮要用它（定义在文件后部的配网段）。 */
static void wifi_open_event(lv_event_t *e);

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

/* 通用文字按钮（配网页的「连接/跳过」、待机页的「Wi-Fi」共用）。 */
static lv_obj_t *make_text_button(lv_obj_t *parent, const char *text,
                                  lv_event_cb_t cb, int w, int h,
                                  const lv_font_t *font)
{
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_t *label;

    lv_obj_set_size(btn, w, h);
    lv_obj_set_style_bg_color(btn, lv_color_hex(UI_BTN_COLOR), 0);
    lv_obj_set_style_radius(btn, 10, 0);
    lv_obj_add_event_cb(btn, cb, LV_EVENT_CLICKED, NULL);

    label = lv_label_create(btn);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(UI_TEXT_COLOR), 0);
    lv_obj_center(label);
    return btn;
}

/* ---------- 触摸音量控件（2026-10-19）---------- */

static void volume_button_event(lv_event_t *e)
{
    int delta = (int)(intptr_t)lv_event_get_user_data(e);

    if (g_volume_cb != NULL) {
        g_volume_cb(delta);
    }
}

static lv_obj_t *make_volume_button(lv_obj_t *parent, const char *text, int delta,
                                    int size)
{
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_t *label;

    lv_obj_set_size(btn, size, size);
    lv_obj_set_style_bg_color(btn, lv_color_hex(UI_BTN_COLOR), 0);
    lv_obj_set_style_radius(btn, size / 2, 0);
    lv_obj_add_event_cb(btn, volume_button_event, LV_EVENT_CLICKED,
                        (void *)(intptr_t)delta);

    label = lv_label_create(btn);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, g_font_body, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(UI_TEXT_COLOR), 0);
    lv_obj_center(label);
    return btn;
}

/* 一排「- 音量 X% +」；两页各建一份，label 指针留给 set_volume 更新。
 *
 * ⚠️ 贴底摆放（2026-10-19 真机修正）：第一版按"屏幕中心 +225"摆，用户实测
 * **整排完全看不见** —— 屏的可用高度不一定是我们以为的 800（fb 分辨率由驱动
 * 决定，面板 800×1280 经硬件旋转后也可能是别的值），固定偏移一旦超出就整排
 * 在屏外。贴到父对象底边后，无论分辨率多少都落在屏幕内。
 * 小屏（high < 480）同时把按钮缩到 44、边距收到 6，给上面的文字留空间。 */
static void build_volume_row(lv_obj_t *parent, lv_obj_t **label_out, int compact)
{
    int size = compact ? 44 : 64;
    int edge = compact ? 6 : 16;
    int gap  = compact ? 75 : 95;
    lv_obj_t *row = lv_obj_create(parent);
    lv_obj_t *minus;
    lv_obj_t *plus;

    lv_obj_set_size(row, LV_PCT(100), size);
    lv_obj_align(row, LV_ALIGN_BOTTOM_MID, 0, -edge);
    lv_obj_set_style_bg_opa(row, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(row, 0, 0);
    lv_obj_set_style_pad_all(row, 0, 0);
    lv_obj_remove_flag(row, LV_OBJ_FLAG_SCROLLABLE);

    minus = make_volume_button(row, "-", -1, size);
    plus  = make_volume_button(row, "+", +1, size);

    *label_out = make_label(row, "音量 60%", g_font_hint, UI_TEXT_COLOR,
                            LV_ALIGN_CENTER, 0, 0);
    lv_obj_align(minus, LV_ALIGN_CENTER, -gap, 0);
    lv_obj_align(plus, LV_ALIGN_CENTER, gap, 0);
}

/* 当前显示高度；拿不到时返回 0（调用方按常规布局处理）。 */
static int32_t ui_height(void)
{
    lv_display_t *disp = lv_display_get_default();

    return disp != NULL ? lv_display_get_vertical_resolution(disp) : 0;
}

static void build_idle_page(void)
{
    /* 小屏（<480 高）用紧凑坐标：常规布局的 +120/+172 会直接落到屏外。 */
    int compact = ui_height() > 0 && ui_height() < 480;

    g_page_idle = make_page();

    /* 产品名。队伍一行与串口横幅同款，评委对着屏就能对上号。 */
    make_label(g_page_idle, "AI 模拟面试官", g_font_title, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, compact ? -70 : -120);
    make_label(g_page_idle, "contest2026_151 · mianbao", g_font_hint, UI_HINT_COLOR,
               LV_ALIGN_CENTER, 0, compact ? -38 : -58);

    /* 岗位：K3 切换后这一行立刻跟着变 —— "岗位可视化"就落在这里 */
    g_idle_role = make_label(g_page_idle, "当前岗位：", g_font_body, UI_ROLE_COLOR,
                             LV_ALIGN_CENTER, 0, compact ? 6 : 30);

    /* 压力档位：赛前按 K2 循环切换 —— 与岗位一起构成"开面参数" */
    g_idle_pressure = make_label(g_page_idle, "压力档位：标准（按 K2 切换）",
                                 g_font_hint, UI_HINT_COLOR,
                                 LV_ALIGN_CENTER, 0, compact ? 38 : 82);

    make_label(g_page_idle, "按 K1 开始面试", g_font_body, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, compact ? 70 : 120);

    /* 小屏放不下这一行提示 —— K3 的用法在 README 与串口里都有。 */
    if (!compact) {
        make_label(g_page_idle, "按 K3 切换岗位（两场面试之间）", g_font_hint,
                   UI_HINT_COLOR, LV_ALIGN_CENTER, 0, 172);
    }

    /* 触摸音量：待机页就能调好，面试中页也有一排（见 build_live_page） */
    build_volume_row(g_page_idle, &g_idle_volume, compact);

    /* 右上角「Wi-Fi」：随时重开配网页（密码写错、换热点时不用清 /data）。
     * 用 hint 字号 —— body(28) 塞进这个小按钮会顶边。 */
    {
        lv_obj_t *wifi_btn = make_text_button(g_page_idle, "Wi-Fi",
                                              wifi_open_event,
                                              compact ? 74 : 100,
                                              compact ? 34 : 42,
                                              g_font_hint);
        lv_obj_align(wifi_btn, LV_ALIGN_TOP_RIGHT,
                     compact ? -6 : -18, compact ? 6 : 16);
    }
}

static void build_live_page(void)
{
    int compact = ui_height() > 0 && ui_height() < 480;

    g_page_live = make_page();

    make_label(g_page_live, "面试中…", g_font_title, UI_TEXT_COLOR,
               LV_ALIGN_CENTER, 0, compact ? -46 : -60);
    g_live_role = make_label(g_page_live, "", g_font_body, UI_ROLE_COLOR,
                             LV_ALIGN_CENTER, 0, compact ? 2 : 25);
    g_live_pressure = make_label(g_page_live, "", g_font_hint, UI_HINT_COLOR,
                                 LV_ALIGN_CENTER, 0, compact ? 32 : 68);
    make_label(g_page_live, "请对着开发板回答，说完停顿两秒", g_font_hint,
               UI_HINT_COLOR, LV_ALIGN_CENTER, 0, compact ? 58 : 105);

    build_volume_row(g_page_live, &g_live_volume, compact);

    lv_obj_add_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);   /* 开机先显示待机页 */
}

/* ---------- Wi-Fi 配网页（2026-10-27）---------- */
/*
 * 目标：第一次拿到板子的普通用户，不用记 wapi 命令、不用连串口 —— 开机直接
 * 在屏上输入热点名和密码。输入用 LVGL 自带键盘（固件里 LV_USE_KEYBOARD=y）。
 *
 * 线程纪律不变：本页只在主线程建/改；"连接"回调里**不做阻塞操作**，只保存
 * 凭据并让 main.c 给工作线程投一条 CMD_WIFI_CONNECT。
 */

static void wifi_ta_event(lv_event_t *e)
{
    lv_obj_t *ta = (lv_obj_t *)lv_event_get_target(e);

    if (g_wifi_kb != NULL && ta != NULL) {
        lv_keyboard_set_textarea(g_wifi_kb, ta);   /* 点哪个框，键盘就输哪个 */
    }
}

static void wifi_skip_event(lv_event_t *e)
{
    (void)e;
    interview_ui_show_wifi(0);
}

/* 待机页右上角的「Wi-Fi」：随时重开配网页（密码写错时不用清 /data）。 */
static void wifi_open_event(lv_event_t *e)
{
    (void)e;
    if (g_wifi_ssid_ta != NULL) {
        lv_textarea_set_text(g_wifi_ssid_ta, "");
    }
    if (g_wifi_psk_ta != NULL) {
        lv_textarea_set_text(g_wifi_psk_ta, "");
    }
    interview_ui_show_wifi(1);
}

static void wifi_connect_event(lv_event_t *e)
{
    const char *ssid;
    const char *psk;

    (void)e;
    ssid = g_wifi_ssid_ta != NULL ? lv_textarea_get_text(g_wifi_ssid_ta) : NULL;
    psk  = g_wifi_psk_ta  != NULL ? lv_textarea_get_text(g_wifi_psk_ta)  : NULL;

    if (ssid == NULL || ssid[0] == '\0' || psk == NULL || psk[0] == '\0') {
        if (g_wifi_status != NULL) {
            lv_label_set_text(g_wifi_status, "请填写热点名称和密码");
        }
        return;
    }
    if (g_wifi_cb == NULL || g_wifi_cb(ssid, psk) != 0) {
        if (g_wifi_status != NULL) {
            lv_label_set_text(g_wifi_status, "保存失败，请重试");
        }
        return;
    }
    if (g_wifi_status != NULL) {
        lv_label_set_text(g_wifi_status, "已保存，正在连接…");
    }
    interview_ui_show_wifi(0);      /* 回到待机页；连接在工作线程继续 */
}

static void build_wifi_page(void)
{
    int32_t h = ui_height();
    int compact = h > 0 && h < 480;
    lv_obj_t *btn_connect;
    lv_obj_t *btn_skip;

    if (h <= 0) {
        h = 800;        /* 取不到分辨率时按常规布局走，总比除零好 */
    }

    g_page_wifi = make_page();

    make_label(g_page_wifi, "连接 Wi-Fi", g_font_title, UI_TEXT_COLOR,
               LV_ALIGN_TOP_MID, 0, compact ? 10 : (int)(h * 0.05));
    make_label(g_page_wifi, "首次使用：输入热点名称和密码（只需设置一次）",
               g_font_hint, UI_HINT_COLOR,
               LV_ALIGN_TOP_MID, 0, compact ? 44 : (int)(h * 0.14));

    g_wifi_ssid_ta = lv_textarea_create(g_page_wifi);
    lv_textarea_set_one_line(g_wifi_ssid_ta, true);
    lv_textarea_set_placeholder_text(g_wifi_ssid_ta, "热点名称（SSID）");
    lv_obj_set_size(g_wifi_ssid_ta, LV_PCT(80), compact ? 40 : 52);
    lv_obj_align(g_wifi_ssid_ta, LV_ALIGN_TOP_MID, 0,
                 compact ? 80 : (int)(h * 0.21));

    g_wifi_psk_ta = lv_textarea_create(g_page_wifi);
    lv_textarea_set_one_line(g_wifi_psk_ta, true);
    lv_textarea_set_password_mode(g_wifi_psk_ta, true);
    lv_textarea_set_placeholder_text(g_wifi_psk_ta, "密码");
    lv_obj_set_size(g_wifi_psk_ta, LV_PCT(80), compact ? 40 : 52);
    lv_obj_align(g_wifi_psk_ta, LV_ALIGN_TOP_MID, 0,
                 compact ? 130 : (int)(h * 0.30));

    btn_connect = make_text_button(g_page_wifi, "连接", wifi_connect_event,
                                   compact ? 120 : 180, compact ? 40 : 52,
                                   g_font_body);
    btn_skip = make_text_button(g_page_wifi, "跳过", wifi_skip_event,
                                compact ? 100 : 140, compact ? 40 : 52,
                                g_font_body);
    lv_obj_align(btn_connect, LV_ALIGN_TOP_MID, compact ? -80 : -110,
                 compact ? 185 : (int)(h * 0.40));
    lv_obj_align(btn_skip, LV_ALIGN_TOP_MID, compact ? 80 : 110,
                 compact ? 185 : (int)(h * 0.40));

    g_wifi_status = make_label(g_page_wifi, "", g_font_hint, UI_ROLE_COLOR,
                               LV_ALIGN_TOP_MID, 0, compact ? 235 : (int)(h * 0.48));

    g_wifi_kb = lv_keyboard_create(g_page_wifi);
    lv_obj_set_size(g_wifi_kb, LV_PCT(100),
                    compact ? (h * 42 / 100) : (h * 45 / 100));
    lv_obj_align(g_wifi_kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_keyboard_set_mode(g_wifi_kb, LV_KEYBOARD_MODE_TEXT_LOWER);
    lv_keyboard_set_textarea(g_wifi_kb, g_wifi_ssid_ta);
    lv_obj_set_style_bg_color(g_wifi_kb, lv_color_hex(UI_BG_COLOR), 0);
    lv_obj_set_style_bg_opa(g_wifi_kb, LV_OPA_COVER, 0);

    /* 点输入框就把键盘绑过去（CLICKED 与 FOCUSED 都挂：触摸与键盘导航都覆盖） */
    lv_obj_add_event_cb(g_wifi_ssid_ta, wifi_ta_event, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(g_wifi_ssid_ta, wifi_ta_event, LV_EVENT_FOCUSED, NULL);
    lv_obj_add_event_cb(g_wifi_psk_ta, wifi_ta_event, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(g_wifi_psk_ta, wifi_ta_event, LV_EVENT_FOCUSED, NULL);

    lv_obj_add_flag(g_page_wifi, LV_OBJ_FLAG_HIDDEN);   /* 默认不显示 */
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
#ifdef CONFIG_INPUT_TOUCHSCREEN
        /* 触摸屏：屏上音量控件要它（2026-10-19）。设备名同打地鼠。 */
        info.input_path = UI_TOUCH_PATH;
#endif
        /* 触摸这一版不用（设计见头文件）—— 不填 input_path，LVGL 就没有输入设备 */
        lv_nuttx_init(&info, &result);

        if (result.disp == NULL) {
            printf("[UI] 显示屏初始化失败 —— 本次不带屏运行\n");
            return -1;
        }

        /* 触摸排障用（2026-10-19）：第一版音量控件"完全没显示"，先确认
         * 输入设备到底有没有接上。点按钮时 main.c 还会打「音量：X%」。 */
        printf("[UI] 触摸输入 %s（%s）\n",
               result.indev != NULL ? "已接上" : "未接上", UI_TOUCH_PATH);
    } else if (lv_display_get_default() == NULL) {
        /* 别的应用（如打地鼠）初始化过 LVGL 又没留下可用的显示 —— 同样退化。
         * 本应用重启后能复用已初始化的 LVGL，靠的就是上面这条分支。 */
        printf("[UI] LVGL 已初始化但没有可用显示 —— 本次不带屏运行\n");
        return -1;
    }

    {
        /* 排障用：实际 fb 分辨率决定布局（见 build_volume_row 的注释）。 */
        lv_display_t *disp = lv_display_get_default();

        if (disp != NULL) {
            printf("[UI] 屏幕分辨率 %d×%d\n",
                   (int)lv_display_get_horizontal_resolution(disp),
                   (int)lv_display_get_vertical_resolution(disp));
        }
    }

    g_font_title = load_font(UI_FONT_TITLE, lv_font_default());
    g_font_body  = load_font(UI_FONT_BODY,  lv_font_default());
    g_font_hint  = load_font(UI_FONT_HINT,  lv_font_default());

    build_idle_page();
    build_live_page();
    build_wifi_page();

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

void interview_ui_set_volume_cb(void (*cb)(int delta))
{
    g_volume_cb = cb;
}

void interview_ui_set_volume(int percent)
{
    if (!g_ready) {
        return;
    }
    if (g_idle_volume != NULL) {
        lv_label_set_text_fmt(g_idle_volume, "音量 %d%%", percent);
    }
    if (g_live_volume != NULL) {
        lv_label_set_text_fmt(g_live_volume, "音量 %d%%", percent);
    }
}

void interview_ui_set_pressure(const char *pressure)
{
    if (pressure == NULL || pressure[0] == '\0') {
        return;
    }
    if (!g_ready) {
        return;
    }
    if (g_idle_pressure != NULL) {
        lv_label_set_text_fmt(g_idle_pressure, "压力档位：%s（按 K2 切换）", pressure);
    }
    if (g_live_pressure != NULL) {
        lv_label_set_text_fmt(g_live_pressure, "压力档位：%s", pressure);
    }
}

void interview_ui_set_wifi_cb(ui_wifi_cb_t cb)
{
    g_wifi_cb = cb;
}

void interview_ui_show_wifi(int show)
{
    show = show ? 1 : 0;

    if (!g_ready || g_page_wifi == NULL || show == g_wifi_page_visible) {
        return;
    }
    g_wifi_page_visible = show;

    if (show) {
        lv_obj_add_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(g_page_wifi, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(g_page_wifi);
    } else {
        lv_obj_add_flag(g_page_wifi, LV_OBJ_FLAG_HIDDEN);
        if (g_in_session) {
            lv_obj_remove_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(g_page_live);
        } else {
            lv_obj_remove_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(g_page_idle);
        }
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
        /* 配网页只是"首次使用"的过渡页：一旦开始面试就收起，别挡住面试中页。 */
        if (g_page_wifi != NULL && g_wifi_page_visible) {
            lv_obj_add_flag(g_page_wifi, LV_OBJ_FLAG_HIDDEN);
            g_wifi_page_visible = 0;
        }
        lv_obj_add_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(g_page_live);
    } else if (!g_wifi_page_visible) {
        lv_obj_add_flag(g_page_live, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(g_page_idle, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(g_page_idle);
    }
}
