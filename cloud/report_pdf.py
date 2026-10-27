"""把一场面试渲染成 PDF（2026-10-27 加）。

为什么服务端生成，而不是"浏览器打印另存为"
------------------------------------------
用户要的是**一个文件**：发给导师、存档、打印出来看。网页上再点一次"另存为"
多一道手续，而且不同的浏览器出来的版式不一样。这里直接给 `.pdf`。

输入与 Markdown/JSON 导出**同源**（同一份 snapshot），三处不会漂。

字体
----
优先嵌入系统中文字体（见 `_FONT_CANDIDATES`），PDF 自带字形 —— 换电脑打开
不会变豆腐块。一个都找不到时退回 reportlab 内置的 CID 字体 STSong-Light：
能显示，但不嵌入（少数极简 PDF 阅读器可能替换字体）。**宁可字体不完美，
也不让导出直接失败** —— 同 report_export 对坏数据的取舍。
"""
import io
import logging
import os
import re

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)
    _AVAILABLE = True
except Exception:          # noqa: BLE001 —— 没装 reportlab 时让上层给可读错误
    _AVAILABLE = False

# (路径, ttc 子字体索引)；跨平台按顺序找第一个存在的
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc", 0),          # 微软雅黑
    (r"C:\Windows\Fonts\simhei.ttf", None),     # 黑体
    (r"C:\Windows\Fonts\simsun.ttc", 0),        # 宋体
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
]
_BOLD_CANDIDATES = [
    (r"C:\Windows\Fonts\msyhbd.ttc", 0),
    (r"C:\Windows\Fonts\simhei.ttf", None),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
]

_FONTS = {}          # {"regular": name, "bold": name}


def available() -> bool:
    """reportlab 是否可用（没装时路由返回可读的 503，而不是 500）。"""
    return _AVAILABLE


def _try_register(name, path, index):
    if not os.path.exists(path):
        return False
    try:
        if index is None:
            pdfmetrics.registerFont(TTFont(name, path))
        else:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=index))
        return True
    except Exception as error:      # noqa: BLE001 —— 换下一个候选
        logger.info(f"[PDF] 字体 {path} 注册失败，换下一个：{error}")
        return False


def _fonts():
    """返回 (regular, bold) 字体名；只注册一次。"""
    if _FONTS:
        return _FONTS["regular"], _FONTS["bold"]

    regular = bold = None
    for path, index in _FONT_CANDIDATES:
        if _try_register("ReportCJK", path, index):
            regular = "ReportCJK"
            break
    for path, index in _BOLD_CANDIDATES:
        if _try_register("ReportCJK-Bold", path, index):
            bold = "ReportCJK-Bold"
            break
    if regular is None:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        regular = bold = "STSong-Light"
    bold = bold or regular
    _FONTS["regular"], _FONTS["bold"] = regular, bold
    return regular, bold


def _esc(value) -> str:
    """Paragraph 是 XML 片段：只转义三个必要字符。"""
    return (str(value if value is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _plain(text) -> str:
    """去掉 Markdown 标记（报告正文偶尔带 ** 与 #），保留换行。"""
    text = str(text or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _fmt_time(value) -> str:
    try:
        import time
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(value)))
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _num(value, suffix=""):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def _table(rows, widths, regular, bold, header=True):
    """统一样式的小表格：浅色表头 + 细网格；单元格内容自动转 Paragraph。"""
    body_style = ParagraphStyle("cell", fontName=regular, fontSize=9, leading=13,
                                wordWrap="CJK")
    head_style = ParagraphStyle("head", fontName=bold, fontSize=9, leading=13,
                                wordWrap="CJK", textColor=colors.HexColor("#1F3B73"))
    data = []
    for i, row in enumerate(rows):
        style = head_style if (header and i == 0) else body_style
        data.append([Paragraph(_esc(cell), style) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8DFEA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0),
                         colors.HexColor("#EEF3FC")))
    table.setStyle(TableStyle(commands))
    return table


def render(snapshot) -> bytes:
    """返回 PDF 字节。没有 reportlab 时抛 RuntimeError（路由据此给可读错误）。"""
    if not _AVAILABLE:
        raise RuntimeError("reportlab 未安装，无法生成 PDF")
    snapshot = snapshot or {}
    regular, bold = _fonts()

    title = ParagraphStyle("title", fontName=bold, fontSize=17, leading=23,
                           spaceAfter=2)
    subtitle = ParagraphStyle("subtitle", fontName=regular, fontSize=9.5,
                              leading=14, textColor=colors.HexColor("#6B7688"),
                              spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=18,
                        textColor=colors.HexColor("#1F3B73"),
                        spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", fontName=regular, fontSize=9.8, leading=15.5,
                          wordWrap="CJK", spaceAfter=3)
    dim = ParagraphStyle("dim", fontName=regular, fontSize=8.8, leading=13,
                         textColor=colors.HexColor("#6B7688"), wordWrap="CJK")
    quote = ParagraphStyle("quote", parent=body, leftIndent=8,
                           textColor=colors.HexColor("#334155"))
    footer = ParagraphStyle("footer", fontName=regular, fontSize=8, leading=11,
                            textColor=colors.HexColor("#94A3B8"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="AI 模拟面试官 · 面试报告", author="openvela 大赛 2026 · 151 队 mianbao",
    )

    def _on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        canvas.drawString(18 * mm, 9 * mm, "AI 模拟面试官 · 预面 Preview")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, "第 %d 页" % doc_.page)
        canvas.restoreState()

    story = [Paragraph("AI 模拟面试官 · 面试报告", title)]
    meta_bits = []
    if snapshot.get("role"):
        meta_bits.append("岗位：%s" % snapshot["role"])
    if snapshot.get("pressure"):
        meta_bits.append("压力档：%s" % snapshot["pressure"])
    started = _fmt_time(snapshot.get("created_at"))
    if started:
        meta_bits.append("开始：%s" % started)
    if snapshot.get("question_count") is not None:
        meta_bits.append("问答轮次：%s" % snapshot.get("question_count", 0))
    meta_bits.append("状态：%s" % ("已结束" if snapshot.get("is_finished") else "进行中"))
    story.append(Paragraph(_esc("　·　".join(meta_bits)), subtitle))

    # ---- 总评 ----
    report = _plain(snapshot.get("report") or "")
    if not report and snapshot.get("is_finished"):
        for message in reversed(snapshot.get("messages") or []):
            if message.get("role") == "assistant" and message.get("content"):
                report = _plain(message["content"])
                break
    story.append(Paragraph("总评", h2))
    story.append(Paragraph(_esc(report or "（本次面试还没有生成报告）").replace("\n", "<br/>"), body))

    # ---- 评分 ----
    score = snapshot.get("score") if isinstance(snapshot.get("score"), dict) else {}
    dimensions = score.get("dimensions") or []
    if dimensions:
        story.append(Paragraph("评分", h2))
        if isinstance(score.get("total"), int):
            story.append(Paragraph("总分：<b>%d / 100</b>" % score["total"], body))
        rows = [["维度", "得分", "评语"]]
        for d in dimensions:
            if not isinstance(d, dict):
                continue
            rows.append([d.get("name", "?"),
                         "%s / %s" % (d.get("score", "?"), d.get("max", 10)),
                         d.get("comment") or "—"])
        story.append(_table(rows, [30 * mm, 20 * mm, 105 * mm], regular, bold))
        for d in dimensions:
            if isinstance(d, dict) and d.get("evidence"):
                story.append(Paragraph("依据 · %s：%s" % (
                    _esc(d.get("name", "")), _esc(d["evidence"])), quote))
        if score.get("summary"):
            story.append(Paragraph("一句话总评：%s" % _esc(score["summary"]), body))

        # 下次练习重点：**从本场最低分维度派生**，不另编建议 —— 分数与评语
        # 都是模型已经给出的，这里只做排序和摘取（同 growth.weak_points 的口径：
        # 给方向，不贴标签）。
        ranked = sorted(
            [d for d in dimensions if isinstance(d, dict)
             and isinstance(d.get("score"), (int, float))],
            key=lambda d: d["score"])
        focus = [d for d in ranked if d["score"] < d.get("max", 10)][:2]
        if focus:
            story.append(Paragraph("下次练习重点", h2))
            for i, d in enumerate(focus, 1):
                story.append(Paragraph("%d. <b>%s</b>（%s / %s）：%s" % (
                    i, _esc(d.get("name", "")), _num(d.get("score")),
                    _num(d.get("max", 10)), _esc(d.get("comment") or "本场失分最多")), body))

    # ---- 表达状态 ----
    expression = [e for e in (snapshot.get("expression") or []) if isinstance(e, dict)]
    if expression:
        story.append(Paragraph("表达状态", h2))
        speeds = [e["chars_per_min"] for e in expression
                  if isinstance(e.get("chars_per_min"), (int, float))]
        durations = [e["duration_sec"] for e in expression
                     if isinstance(e.get("duration_sec"), (int, float))]
        fillers = sum(int(e.get("fillers") or 0) for e in expression)
        chars = sum(int(e.get("chars") or 0) for e in expression)
        summary = []
        if speeds:
            summary.append("平均语速 %d 字/分钟（参考 200~260）"
                           % round(sum(speeds) / len(speeds)))
        else:
            summary.append("本次为文字演练，无语速/停顿数据")
        summary.append("口头语共 %d 次 / %d 字" % (fillers, chars))
        if durations:
            summary.append("平均每轮回答 %.1f 秒" % (sum(durations) / len(durations)))
        story.append(Paragraph(_esc("；".join(summary)) + "。", body))
        rows = [["轮次", "字数", "语速(字/分)", "口头语", "停顿(次/最长)", "时长"]]
        for e in expression:
            pauses = e.get("pauses")
            longest = e.get("longest_pause_sec")
            rows.append([
                e.get("round", "?"),
                e.get("chars", "—"),
                _num(e.get("chars_per_min")),
                e.get("fillers", 0),
                ("%s/%.1fs" % (pauses, longest)) if isinstance(pauses, int)
                and isinstance(longest, (int, float)) else "—",
                _num(e.get("duration_sec"), "s"),
            ])
        story.append(_table(rows, [16 * mm, 18 * mm, 30 * mm, 22 * mm,
                                   38 * mm, 22 * mm], regular, bold))

    # ---- 逐题复盘 ----
    per_question = score.get("per_question") or []
    if per_question:
        story.append(Paragraph("逐题复盘", h2))
        for item in per_question:
            if not isinstance(item, dict):
                continue
            story.append(Paragraph("<b>第 %s 题</b>：%s" % (
                _esc(item.get("index", "?")), _esc(item.get("question") or "（开场）")), body))
            if item.get("evidence"):
                story.append(Paragraph("你的原话：%s" % _esc(item["evidence"]), quote))
            if item.get("suggestion"):
                story.append(Paragraph("更好的答法：%s" % _esc(item["suggestion"]), quote))

    # ---- 对话记录 ----
    messages = snapshot.get("messages") or []
    story.append(Paragraph("对话记录", h2))
    if not messages:
        story.append(Paragraph("（没有对话内容）", dim))
    for message in messages:
        speaker = "面试官" if message.get("role") == "assistant" else "候选人"
        story.append(Paragraph("<b>%s</b>：%s" % (
            speaker, _esc(message.get("content", "")).replace("\n", "<br/>")), body))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "由 AI 模拟面试官生成（openvela 大赛 2026 · 151 号队 mianbao）", footer))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
