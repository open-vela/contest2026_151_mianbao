#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按官方评分标准排版答辩 PPT，生成两份 PPTX。

2026-11-04 起内容按大赛评分权重组织（技术难度 30 / 产品创新性 20 /
项目完整度 20 / AI 开发 10 / 商业潜力 10 / 展示效果 10）：
    完整版 13 页：定位 → 架构 → 技术难度×3 → 创新性 → 完整度 → 产品化 →
                  AI 开发 → 商业潜力 → 总结
    精简版 12 页：技术难度合并为 1 页（+演示视频位）

用法（答辩材料 2026-11-04 起放仓库外，见 D:\面包包\demo）：
    python tools/build_ppt.py "<模板.pptx 路径>" "D:\面包包\demo"

做法：模板每种版式只用一次，按【模板页码 -> 形状名 -> 文本】替换文字，
保留原有字体/字号/配色。改文案后重跑本脚本即可；不要直接改生成出来的 PPTX。
"""
import sys
import os

# Windows 控制台默认 GBK，打印 ✅/⚠/中文会崩 —— 统一按 UTF-8 出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pptx import Presentation

# ---------------------------------------------------------------------------
# 内容（按评分标准组织；每个形状：单字符串 = 一段；列表 = 多段）
# ---------------------------------------------------------------------------

COVER = {
    "文本框 9": "预面 Preview · AI 模拟面试官",
    "Text 3": "团队：mianbao（contest2026_151）",
}

P2定位 = {
    "AutoShape 3": "项目定位 · 痛点、方案与市场锚点",
    "AutoShape 11": "痛点：缺陪练、缺反馈",
    "AutoShape 12": "真人陪练贵且约不到；软件 AI 面试多是网页点选，练完没有成长记录。",
    "AutoShape 13": "我们的方案",
    "AutoShape 14": "软硬一体的 AI 模拟面试官：对着开发板语音面试，AI 多轮追问，结束出评分报告与成长曲线。",
    "AutoShape 15": "需求已被验证",
    "AutoShape 16": "高校 AI 面试舱 4~19.5 万/间；AI 就业学习机销量翻倍——我们用消费级开发板成本做同一件事。",
    "AutoShape 17": "",
}

P3架构 = {
    "AutoShape 3": "整体架构 · 端云协同 + 三端联动",
    "AutoShape 11": "端云协同",
    "AutoShape 12": "手感在端 · 智能在云",
    # 分支正文卡只有 2.08 英寸高 —— 正文压到 2 行以内（细节进口播）
    "AutoShape 15": "板端（openvela/NuttX）",
    "AutoShape 16": "R528 · LVGL 8 寸屏 · 数字麦 · 三按键 · LED",
    "AutoShape 19": "云端（Flask + MIMO）",
    "AutoShape 20": "ASR / LLM / TTS · 五段引擎 · 2830 题库 · 评分报告",
    "AutoShape 23": "手机 H5（扫码绑定）",
    "AutoShape 24": "扫码认领账号，练习记录跟人走",
    "AutoShape 27": "网页（报告 / 成长）",
    "AutoShape 28": "评分报告、成长曲线、PDF 导出",
    "AutoShape 29": "",
}

P4驱动 = {
    "AutoShape 3": "技术难度① · openvela 适配与底层驱动",
    "AutoShape 7": "数字麦音频通路",
    "AutoShape 8": "默认音频通路采回全零 → 换设备实测定位数字麦（纯采集）；驱动无增益控件 → 软件 ×4 增益 + 静音门限标定；播放按 0.75dB/步寄存器重映射音量。",
    "AutoShape 11": "Wi-Fi 驱动崩溃",
    "AutoShape 12": "Realtek 驱动 mallinfo() 无锁遍历堆，与界面并发即 data abort → 初始化独占主线程 + 补丁遍历两层修复。",
    "AutoShape 15": "屏幕与触摸接入",
    "AutoShape 16": "LVGL 接 fb / touch 设备，分辨率自适应布局；界面全在主线程（LV_OS_NONE），工作线程只投事件。",
    "AutoShape 19": "按键与开机自启",
    "AutoShape 20": "GPIO 电平极性与开机误触修正；rcS 自启 + 修复无限递归 / NETINIT 断网两坑。",
    "AutoShape 21": "全部问题均上板暴露、逐一定位修复——细节写进 4000+ 行工程台账。",
}

P5架构 = {
    "AutoShape 3": "技术难度② · 系统架构设计",
    "AutoShape 7": "端侧：实时流水线",
    "AutoShape 8": [
        "主线程 100ms 节拍（按键 / LED / 界面）+ 工作线程三段流水线（录音 → 上传 → 播放），阻塞调用不卡交互。",
        "五态状态机 + LED 图案 + 屏幕四页；单实例信号量防重复启动；串口逃逸起精简 sh 不断网。",
        "断网三层兜底：屏幕提示 → 回答自动补送不丢进度 → 固定话术本地缓存。",
    ],
    "AutoShape 11": "云端：单服务全链路",
    "AutoShape 12": [
        "Flask 单服务 + 文档化 HTTP/JSON 协议；云端地址运行期可改，固件不用重烧。",
        "skills 热加载（改提示词不重启）；396 项单元测试回归；响应体上限防御。",
        "板端只做交互，报告 / 成长曲线全在云端生成，多设备天然一致。",
    ],
    "AutoShape 13": "",
}

P6框架 = {
    "AutoShape 3": "技术难度③ · AI 智能框架深度使用",
    "AutoShape 8": "识别与防护",
    "AutoShape 9": "MIMO ASR；空识别短路 1.8s，不进模型不进历史",
    "AutoShape 13": "取题与导演",
    "AutoShape 14": "2830 题库按岗位检索注入；导演环规则定本轮动作",
    "AutoShape 18": "出题与回传",
    "AutoShape 19": "MIMO LLM 3.1~3.7s，输出净化后 TTS 回传",
    "AutoShape 23": "评分与落库",
    "AutoShape 24": "证据逐字核对 → 四维评分 → 报告 / PDF / 成长",
    "AutoShape 28": "396 项单元测试全绿；完整一轮约 30 秒，静音轮 1.8 秒。",
}

P7创新 = {
    "AutoShape 3": "产品创新性 · 交互模式与硬件形态",
    "AutoShape 13": "交互模式新颖",
    "AutoShape 14": "按键即面试：K1 开始、K3 切岗位、K2 压力档——语音实体交互，不是网页点选",
    "AutoShape 15": "硬件形态自研",
    "AutoShape 16": "官方无机械数据 → 实测标定 + 参数化建模 → 3D 打印外壳，已试装成品",
    "AutoShape 17": "场景痛点精准",
    "AutoShape 18": "校招 / 转岗练习与院校就业中心；公共设备扫码认领，记录跟人走",
    "AutoShape 19": "功能思路新",
    "AutoShape 20": "五段节奏 + 导演环追问 + 跨场成长曲线 + 副语言反馈",
    "AutoShape 21": "与网页点选式 AI 面试相比，练的是「开口说」与「被追问」的真实压力。",
}

P8完整度 = {
    "AutoShape 3": "项目完整度 · 可运行、可交付、可协同",
    "AutoShape 8": "可运行 Demo",
    "AutoShape 9": "真机全链路：按键开始 → 语音问答 → 评分报告 → 网页成长曲线。",
    "AutoShape 13": "文档齐全",
    "AutoShape 14": "README / 接口协议 / 部署与构建指南 + 4000+ 行工程台账。",
    "AutoShape 18": "质量保证",
    "AutoShape 19": "云端 396 项单元测试；PC 文字演练可复跑全链路。",
    "AutoShape 23": "系统稳定",
    "AutoShape 24": "硬件三坑修复、单实例、断网兜底、错误可恢复。",
    "AutoShape 28": "跨设备协同",
    "AutoShape 29": "板端 ↔ 云端 ↔ 手机 H5 ↔ 网页：扫码绑定、记录同步、报告导出。",
    "AutoShape 33": "完整交付物",
    "AutoShape 34": "固件镜像 + 云端服务 + 3D 外壳 STL + 2830 题题库。",
}

P9产品化 = {
    "AutoShape 3": "产品化闭环 · 从单场报告到跨场成长",
    "AutoShape 6": "跨场成长追踪",
    "AutoShape 8": [
        "总分曲线、维度对比，同岗位同口径才画进曲线。",
        "薄弱点生命周期：一个弱点出现后按 1 / 3 / 7 / 14 天提醒复习，连续答好自动归档。",
        "每场报告带「下次练习重点」，直接指导下一次练什么。",
    ],
    "AutoShape 10": "副语言反馈",
    "AutoShape 12": [
        "语速、停顿、口头语（呃 / 那个 / 就是）统计。",
        "口径诚实：没有音频不编造语速；文字链路只算口头语。",
        "口头语是行业标配（Yoodli、牛客、BOSS），开源同类全部无 LICENSE——自研。",
    ],
}

P10AI开发 = {
    "AutoShape 3": "AI 开发 · Skills 沉淀与全流程赋能",
    "AutoShape 7": "Skills 沉淀",
    "AutoShape 8": [
        "5 个技能 JSON（skills/）：开场 / 追问 / 评分 / 报告 / 超时。",
        "热加载、按面试阶段可插拔——换 Prompt 不用改代码。",
        "同一套 Skills 可复用到其它语音问答场景。",
    ],
    "AutoShape 11": "AI 赋能开发全流程",
    "AutoShape 12": [
        "AI 结对开发：需求 → 方案 → 代码 → 验证全流程留痕（AI Coding 日志归档）。",
        "真实脏输出驱动迭代：输出净化规则来自线上抓到的推演泄漏样本。",
        "4000+ 行工程台账：每个坑的现象 / 根因 / 修复都可回溯。",
    ],
    "AutoShape 15": "工程质量",
    "AutoShape 16": [
        "396 项单元测试，每次改动全量回归。",
        "PC 文字演练：不打板子也能验证整条对话链路。",
        "提示词与评分口径版本化，可回滚",
    ],
    "AutoShape 17": "AI 不只是被用在产品里，也贯穿我们的开发方式。",
}

P11商业 = {
    "AutoShape 3": "商业潜力 · 场景真实，模式清晰",
    "AutoShape 9": "市场与需求",
    "AutoShape 10": "校招 / 转岗求职与院校就业辅导是高频刚需；高校 AI 面试舱 4~19.5 万/间、AI 就业学习机销量翻倍——需求已验证，价格仍是门槛。",
    "AutoShape 11": "商业路径",
    "AutoShape 12": "消费级硬件成本 + 云端练习服务订阅；院校 / 机构批量采购。规模化：一套云服务多设备、题库岗位可扩展、外壳可批量打印。",
    "AutoShape 13": "",
}

P12总结 = {
    "AutoShape 3": "总结",
    "AutoShape 7": "总结",
    "AutoShape 9": [
        "软硬一体的 AI 模拟面试官：openvela 深度适配 + 云端 AI 引擎。",
        "技术有深度：驱动扩展、系统架构、AI 框架三层都经真机打磨。",
        "交付完整：可运行 Demo、文档、测试、跨设备协同。",
        "把一次面试，变成看得见的成长。",
    ],
    "AutoShape 12": "展望",
    "AutoShape 14": [
        "结构化面试笔记与异步记忆、报告逐题流式、评分校准。",
        "更多岗位与场景；院校与个人两条销售路径。",
        "把 Skills 体系复用到更多语音交互场景。",
    ],
}

# 精简版：技术难度合并为一页（四个象限）
P4合并 = {
    "AutoShape 3": "技术难度 · openvela 适配、驱动与系统架构",
    "AutoShape 7": "底层驱动攻坚",
    "AutoShape 8": "数字麦通路全零 → 实测定位 DMIC；Wi-Fi 驱动 mallinfo 崩溃两层修复；LVGL 屏 / 触摸接入。",
    "AutoShape 11": "板级适配",
    "AutoShape 12": "GPIO 电平极性与误触修正；rcS 自启 + 修复无限递归 / NETINIT 断网两坑。",
    "AutoShape 15": "端侧架构",
    "AutoShape 16": "主线程 + 工作线程流水线、五态状态机、单实例信号量、串口逃逸。",
    "AutoShape 19": "断网兜底",
    "AutoShape 20": "屏幕提示 → 回答自动补送不丢 → 固定话术本地缓存，断网也出声。",
    "AutoShape 21": "全部问题上板暴露、逐一定位修复——细节在 4000+ 行工程台账。",
}

THANKS = {
    "AutoShape 7": "预面 Preview · AI 模拟面试官",
    "AutoShape 8": "把一次面试，变成看得见的成长。",
}

# 口播备注（写进 PPT 备注页，放映者视图可见）
NOTE_P1 = "【0:05】各位评委老师好，我们的作品是「预面」——一台可以陪你练面试的 AI 硬件设备。"
NOTE_P2 = "【0:30】练面试没人陪、没人给专业反馈。面试舱一间四到十九万五、AI 就业学习机销量翻倍——需求真实，但要么太贵要么封闭。我们用一块 openvela 开发板加云端 AI 做同一件事。"
NOTE_P3 = "【0:40】架构一句话：手感在端、智能在云。板端管录音/播放/按键/屏幕，云端管识别、出题、评分、报告；手机扫码认领，网页看报告和成长——三端联动。端云是文档化协议，云端怎么改固件都不用重烧。"
NOTE_P4 = "【0:55】技术难度第一层：把新芯片真正用起来。麦克风一度采回全是零——不猜，换设备逐个实测，定位到数字麦，驱动还没有增益控件，软件补；更狠的是 Wi-Fi 驱动里一个不带锁的堆遍历，跟界面一并发就崩；屏幕、按键、自启这几个坑全部上板才暴露，每个都定位到根因修掉。"
NOTE_P5 = "【0:50】第二层是架构：主线程守交互节奏，工作线程跑三段流水线，阻塞调用卡不住按键；单实例、串口逃逸、断网三层兜底都做了。云端单服务、协议文档化、skills 热加载、近四百项测试——端侧改坏了也伤不到云端。"
NOTE_P6 = "【0:55】第三层是 AI 框架的深度使用：MIMO 三个模型接成完整链路——识别、出题评分、合成语音。中间还有三层自己的东西：空识别短路，没人说话一点八秒回一句，不惊动大模型；导演环按上一答质量决定深入还是换角度；证据逐字核对，评语必须能指回你的原话。"
NOTE_P7 = "【0:40】创新点两处：交互上，按键即面试——语音实体交互，练的是开口说和被追问的真实压力，不是网页点选；硬件上，官方没有机械数据，我们实测标定、参数化建模、3D 打印外壳，已经装进成品。"
NOTE_P8 = "【0:40】完整度：真机全链路可跑，文档、协议、四千行台账齐全，近四百项测试，三端协同——板端、云端、手机、网页，扫码绑定、记录同步、报告导出。"
NOTE_P9 = "【0:40】单场报告只是孤岛，我们做成成长系统：跨场曲线、维度对比、薄弱点按 1/3/7/14 天提醒复习。副语言是面试官第一印象的来源，行业都做、开源都不能用，我们自研。"
NOTE_P10 = "【0:40】AI 开发这一项是我们扎实的地方：五个技能 JSON 沉淀为可复用 Skills，热加载、可插拔；整个开发流程 AI 结对、日志归档、四千行台账；净化规则来自线上抓到的真实脏输出——AI 既在产品里，也在开发方式里。"
NOTE_P11 = "【0:35】商业潜力：求职练习是高频刚需，面试舱的定价验证了支付意愿，但门槛太高。我们用消费级硬件成本做同件事，设备加练习服务，院校和个人两条路径，题库岗位和外壳都能扩展。"
NOTE_P12 = "【0:20】总结：一台按键就开始的设备，一层层经真机打磨的技术，一条从报告到成长的闭环。把一次面试，变成看得见的成长。谢谢各位老师。"
NOTE_P13 = "欢迎提问与交流。"

# 精简版：技术难度合并页口播；商业化页后接演示视频
NOTE_P4_LITE = ("【0:50】技术难度一页讲完：驱动层——数字麦通路、Wi-Fi 驱动崩溃、屏幕按键自启，全部上板实测修复；"
                "架构层——主线程守交互、工作线程跑流水线，断网三层兜底；云端单服务近四百项测试。"
                "每个坑的现象、根因、修复都在四千行台账里。")
NOTE_P11_LITE_VIDEO = (NOTE_P11 +
                       "\n\n【▶ 随后播放 1:30~2:00 实机演示视频：按键开始 → 语音问答 2~3 轮 → "
                       "报告生成 → 网页成长页。过场词：下面用一段实机演示，把刚才讲的整条链路跑一遍。】")

# ---------------------------------------------------------------------------
# 字号（2026-11-02 第二轮：用户定口径「文字要占框的 70%~80%」）
# 按【模板页码 -> 形状名 -> pt】显式指定；配合 fix_geometry 一起把框加大。
# ---------------------------------------------------------------------------
FONT_PT = {
    1:  {"Text 3": 40},
    19: {"AutoShape 2": 22, "AutoShape 17": 27,
         "AutoShape 6": 72, "AutoShape 8": 72, "AutoShape 10": 72,
         "AutoShape 11": 34, "AutoShape 13": 34, "AutoShape 15": 34,
         "AutoShape 12": 26, "AutoShape 14": 26, "AutoShape 16": 26},
    16: {"AutoShape 2": 22, "AutoShape 29": 27,
         "AutoShape 11": 34, "AutoShape 12": 26,
         "AutoShape 15": 30, "AutoShape 19": 30, "AutoShape 23": 30, "AutoShape 27": 30,
         "AutoShape 16": 25, "AutoShape 20": 25, "AutoShape 24": 25, "AutoShape 28": 25},
    20: {"AutoShape 2": 22, "AutoShape 21": 27,
         "AutoShape 6": 58, "AutoShape 8": 58, "AutoShape 10": 58, "AutoShape 12": 58,
         "AutoShape 13": 32, "AutoShape 15": 32, "AutoShape 17": 32, "AutoShape 19": 32,
         "AutoShape 14": 25, "AutoShape 16": 25, "AutoShape 18": 25, "AutoShape 20": 25},
    15: {"AutoShape 2": 22,
         "AutoShape 8": 32, "AutoShape 13": 32, "AutoShape 18": 32,
         "AutoShape 23": 32, "AutoShape 28": 32, "AutoShape 33": 32,
         "AutoShape 9": 27, "AutoShape 14": 27, "AutoShape 19": 27,
         "AutoShape 24": 27, "AutoShape 29": 27, "AutoShape 34": 27},
    13: {"AutoShape 2": 22, "AutoShape 28": 27,
         "AutoShape 7": 56, "AutoShape 12": 56, "AutoShape 17": 56, "AutoShape 22": 56,
         "AutoShape 8": 32, "AutoShape 13": 32, "AutoShape 18": 32, "AutoShape 23": 32,
         "AutoShape 9": 27, "AutoShape 14": 27, "AutoShape 19": 27, "AutoShape 24": 27},
    21: {"AutoShape 2": 22,
         "AutoShape 7": 34, "AutoShape 11": 34,
         "AutoShape 8": 30, "AutoShape 12": 30},
    18: {"AutoShape 2": 22,
         "AutoShape 6": 72, "AutoShape 8": 72,
         "AutoShape 9": 34, "AutoShape 11": 34,
         "AutoShape 10": 27, "AutoShape 12": 27},
    12: {"AutoShape 2": 22,
         "AutoShape 6": 40, "AutoShape 10": 40,
         "AutoShape 8": 30, "AutoShape 12": 30},
    23: {"AutoShape 2": 22, "AutoShape 21": 27,
         "AutoShape 7": 32, "AutoShape 11": 32,
         "AutoShape 15": 32, "AutoShape 19": 32,
         "AutoShape 8": 27, "AutoShape 12": 27, "AutoShape 16": 27, "AutoShape 20": 27},
    22: {"AutoShape 2": 22, "AutoShape 17": 27,
         "AutoShape 7": 32, "AutoShape 11": 32, "AutoShape 15": 32,
         "AutoShape 8": 28, "AutoShape 12": 28, "AutoShape 16": 28},
    6:  {"AutoShape 2": 22,
         "AutoShape 7": 40, "AutoShape 12": 40,
         "AutoShape 9": 30, "AutoShape 14": 30},
    31: {"AutoShape 6": 36, "AutoShape 7": 28, "AutoShape 8": 22},
}


def apply_fonts(slide, font_map):
    if not font_map:
        return
    from pptx.util import Pt
    by_name = {sh.name: sh for sh in slide.shapes}
    for name, pt in font_map.items():
        sh = by_name.get(name)
        if sh is None or not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(pt)


def center_numbers(slide, pairs, nudge=0.03):
    """把圆内数字框与圆心对齐（模板原样差 0.1~0.16 英寸，肉眼可见地偏）。
    nudge 向上微调一点：MIDDLE 锚点带下行空间，字面看着会略偏下。"""
    from pptx.util import Inches
    by = {sh.name: sh for sh in slide.shapes}
    for circle_name, num_name in pairs:
        c, n = by.get(circle_name), by.get(num_name)
        if c is None or n is None:
            continue
        cy = c.top.inches + c.height.inches / 2
        n.top = Inches(cy - n.height.inches / 2 - nudge)


def fix_geometry(slide, page):
    """文字加大后把框一起加大（框不是固定的），并修对齐/贴边问题。"""
    from pptx.util import Inches
    from pptx.enum.text import MSO_ANCHOR

    if page == 13:
        # 流程卡拉高到 4.55（下方空间大）——27pt 三行正文也收在卡内。
        # 这页的 01~04 在卡片顶部（不在圆里），别动它的位置。
        for sh in slide.shapes:
            if sh.name in ("AutoShape 5", "AutoShape 10", "AutoShape 15", "AutoShape 20"):
                sh.height = Inches(4.55)
            elif sh.name in ("AutoShape 9", "AutoShape 14", "AutoShape 19", "AutoShape 24"):
                sh.top = Inches(7.55)
                sh.height = Inches(1.9)
    elif page == 16:
        # 分支卡加高（上排到 6.72、下排到 12.55，脚注在 12.7）；正文框放大
        for sh in slide.shapes:
            if sh.name in ("AutoShape 13", "AutoShape 17",
                           "AutoShape 21", "AutoShape 25"):
                sh.height = Inches(2.55)
            elif sh.name in ("AutoShape 16", "AutoShape 20"):
                sh.top = Inches(5.25)
                sh.height = Inches(1.2)
            elif sh.name in ("AutoShape 24", "AutoShape 28"):
                sh.top = Inches(11.15)
                sh.height = Inches(1.2)
    elif page == 19:
        # 圆内数字与圆心对齐；正文框顶对齐 + 加高（原来 0.6 英寸居中，往上顶字）
        for sh in slide.shapes:
            if sh.name in ("AutoShape 12", "AutoShape 14", "AutoShape 16"):
                sh.height = Inches(1.6)
                sh.text_frame.vertical_anchor = MSO_ANCHOR.TOP
        center_numbers(slide, [("AutoShape 5", "AutoShape 6"),
                               ("AutoShape 7", "AutoShape 8"),
                               ("AutoShape 9", "AutoShape 10")])
    elif page == 20:
        # 圆内数字对齐；正文框顶对齐 + 加高（0.8 英寸居中框装不下三行，会顶到小标题）
        for sh in slide.shapes:
            if sh.name in ("AutoShape 14", "AutoShape 16",
                           "AutoShape 18", "AutoShape 20"):
                sh.top = Inches(9.15)
                sh.height = Inches(1.5)
                sh.text_frame.vertical_anchor = MSO_ANCHOR.TOP
        center_numbers(slide, [("AutoShape 5", "AutoShape 6"),
                               ("AutoShape 7", "AutoShape 8"),
                               ("AutoShape 9", "AutoShape 10"),
                               ("AutoShape 11", "AutoShape 12")])
    elif page == 18:
        # 圆内数字与圆心对齐；正文挪到小标题下方 + 加高
        for sh in slide.shapes:
            if sh.name in ("AutoShape 10", "AutoShape 12"):
                sh.top = Inches(9.9)
                sh.height = Inches(2.2)
                sh.text_frame.vertical_anchor = MSO_ANCHOR.TOP
        center_numbers(slide, [("AutoShape 5", "AutoShape 6"),
                               ("AutoShape 7", "AutoShape 8")])
    elif page == 15:
        # 六宫格卡片加高（正文 27pt 三行会碰到底边）；下排整体下移一点保持间距
        for sh in slide.shapes:
            if sh.name in ("AutoShape 5", "AutoShape 10", "AutoShape 15"):
                sh.height = Inches(3.85)
            elif sh.name in ("AutoShape 20", "AutoShape 25", "AutoShape 30"):
                sh.top = Inches(8.35)
                sh.height = Inches(3.85)
            elif sh.name in ("AutoShape 9", "AutoShape 14", "AutoShape 19"):
                sh.height = Inches(1.85)
            elif sh.name in ("AutoShape 24", "AutoShape 29", "AutoShape 34"):
                sh.top = Inches(10.15)
                sh.height = Inches(1.85)
    elif page == 23:
        for sh in slide.shapes:
            if sh.name in ("AutoShape 8", "AutoShape 12",
                           "AutoShape 16", "AutoShape 20"):
                sh.height = Inches(2.1)


# ---------------------------------------------------------------------------
# 通用替换
# ---------------------------------------------------------------------------

def set_shape_text(shape, content):
    """把形状文本框改成 content（str = 一段；list = 多段）。

    保留每个段落第一个 run 的字体格式（模板的样式都挂在 run 上）；
    模板段落多于内容时删除多余段落，少于时复用最后一个段落的格式补建。
    """
    from copy import deepcopy

    if isinstance(content, str):
        content = [content]

    tf = shape.text_frame
    txBody = tf._txBody
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    paras = txBody.findall(ns + "p")

    # 数量对齐：多删少补（补的段落复制最后一个段落的 XML，格式自然继承）
    while len(paras) > len(content):
        txBody.remove(paras[-1])
        paras = paras[:-1]
    while len(paras) < len(content):
        new_p = deepcopy(paras[-1])
        paras[-1].addnext(new_p)
        paras.append(new_p)

    for p, text in zip(paras, content):
        runs = p.findall(ns + "r")
        if not runs:
            # 空段落：造一个 run（极少发生）
            from pptx.oxml.ns import qn
            r = p.makeelement(qn("a:r"), {})
            t = p.makeelement(qn("a:t"), {})
            r.append(t)
            p.append(r)
            runs = [r]
        # 第一个 run 承载全部文本，其余 run 删除（它们只是占位重复）
        runs[0].find(ns + "t").text = text
        for extra in runs[1:]:
            p.remove(extra)


def fill_slide(slide_no, slide, content):
    by_name = {}
    for sh in slide.shapes:
        by_name[sh.name] = sh
    for name, text in content.items():
        sh = by_name.get(name)
        if sh is None:
            print(f"  ⚠ slide {slide_no}: 找不到形状 {name!r}，跳过")
            continue
        if not sh.has_text_frame:
            print(f"  ⚠ slide {slide_no}: 形状 {name!r} 没有文本框，跳过")
            continue
        set_shape_text(sh, text)


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def reorder_and_prune(prs, keep_order):
    """把幻灯片整理成 keep_order（模板页码列表），其余删除。"""
    sldIdLst = prs.slides._sldIdLst
    sldIds = list(sldIdLst)

    # 模板页码 -> sldId 元素（当前顺序即模板顺序）
    by_page = {i + 1: sldIds[i] for i in range(len(sldIds))}

    keep = set(keep_order)
    for page, sldId in by_page.items():
        if page not in keep:
            rId = sldId.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            prs.part.drop_rel(rId)
            sldIdLst.remove(sldId)

    for page in keep_order:
        sldIdLst.append(by_page[page])   # append 会把它挪到末尾（按序）


# ---------------------------------------------------------------------------
# 两个版本：(模板页码, 屏上内容, 口播备注)
# ---------------------------------------------------------------------------

FULL_ORDER = [
    (1, COVER, NOTE_P1),
    (19, P2定位, NOTE_P2),
    (16, P3架构, NOTE_P3),
    (23, P4驱动, NOTE_P4),
    (21, P5架构, NOTE_P5),
    (13, P6框架, NOTE_P6),
    (20, P7创新, NOTE_P7),
    (15, P8完整度, NOTE_P8),
    (12, P9产品化, NOTE_P9),
    (22, P10AI开发, NOTE_P10),
    (18, P11商业, NOTE_P11),
    (6, P12总结, NOTE_P12),
    (31, THANKS, NOTE_P13),
]

LITE_ORDER = [
    (1, COVER, NOTE_P1),
    (19, P2定位, NOTE_P2),
    (16, P3架构, NOTE_P3),
    (23, P4合并, NOTE_P4_LITE),
    (13, P6框架, NOTE_P6),
    (20, P7创新, NOTE_P7),
    (15, P8完整度, NOTE_P8),
    (12, P9产品化, NOTE_P9),
    (22, P10AI开发, NOTE_P10),
    (18, P11商业, NOTE_P11_LITE_VIDEO),
    (6, P12总结, NOTE_P12),
    (31, THANKS, NOTE_P13),
]


def build(template, out_dir, order, filename):
    prs = Presentation(template)
    pages = [p for p, _, _ in order]
    reorder_and_prune(prs, pages)

    # 重排后 prs.slides 的顺序即 order
    for (page, content, note), slide in zip(order, prs.slides):
        fill_slide(page, slide, content)
        apply_fonts(slide, FONT_PT.get(page))
        fix_geometry(slide, page)
        if page == 1:
            # 封面项目名 17 字 @144pt 会折行压住团队行 —— 缩到 100pt 保单行
            from pptx.util import Pt
            for sh in slide.shapes:
                if sh.name == "文本框 9":
                    for p in sh.text_frame.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(100)
        if note:
            set_notes(slide, note)

    out = os.path.join(out_dir, filename)
    try:
        prs.save(out)
        print(f"✅ 生成 {out}（{len(pages)} 页）")
    except PermissionError:
        # 原文件正被 PowerPoint/WPS 打开着 —— 存成 _v2，关掉后可手动替换
        base, ext = os.path.splitext(filename)
        out2 = os.path.join(out_dir, base + "_v2" + ext)
        prs.save(out2)
        print(f"⚠ {filename} 正被占用（WPS/PowerPoint 开着？），已改存 {out2}（{len(pages)} 页）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    template = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(template)

    print("== 完整版 ==")
    build(template, out_dir, FULL_ORDER, "预面答辩_完整版.pptx")
    print("== 精简版 ==")
    build(template, out_dir, LITE_ORDER, "预面答辩_精简版.pptx")


if __name__ == "__main__":
    main()
