"""把一场面试渲染成可下载的文件（Markdown / JSON）。

为什么需要它
------------
报告此前只存在于网页上（`cloud/static/index.html`）。网页适合当场看，不适合
"存下来过几个月再对比" —— 而单人自练最有价值的用法恰恰是回头看。所以给一个
**下载**出口：Markdown 给人读、也能直接贴进笔记软件，JSON 给以后做纵向分析用。

输入就是 `session_manager.snapshot()` 的那份字典（落盘存的也是它，见
`session_store.py`），因此"内存里、磁盘上、导出的文件"三者的字段永远一致。

两个刻意的选择
--------------
* **文件名用 ASCII**。`Content-Disposition` 里的非 ASCII 文件名要走 RFC 5987
  编码，Werkzeug 的 `send_file(download_name=...)` 版本间行为不完全一致。中文
  标题写在**文件正文**里，文件名只用会话 id 和时间 —— 少一个能出岔子的地方。
* **报告正文复用已有内容**，不另存一份。报告就是最后那条 assistant 消息
  （`llm_service.generate_feedback` 的产物），落盘时也不再复制一遍
  （见 `report_text` 的取值顺序）。
"""
import json
import re
import time

SUPPORTED = ("md", "json")

# 刻意不带 `; charset=utf-8`：send_file 会自己补一个，写了就变成
# `text/markdown; charset=utf-8; charset=utf-8`（不影响功能，但很难看）。
MIME = {"md": "text/markdown", "json": "application/json"}


def report_text(snapshot) -> str:
    """取这场面试的报告正文。

    取值顺序（P1 起）：优先用快照里的 `report` 字段；没有就看它是不是已结束，
    是的话取最后一条 assistant 消息 —— 报告本来就是模型那轮的输出，**不另存一份**
    （存两份就会有两份不一致的那一天）。
    """
    if not isinstance(snapshot, dict):
        return ""
    report = snapshot.get("report")
    if isinstance(report, str) and report.strip():
        return report.strip()
    if snapshot.get("is_finished"):
        for message in reversed(snapshot.get("messages") or []):
            if message.get("role") == "assistant" and message.get("content"):
                return str(message["content"]).strip()
    return ""


def _fmt_time(value) -> str:
    """时间戳转本地时间字符串；给不出就返回空串（不抛异常）。"""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(value)))
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _session_name(snapshot) -> str:
    """文件名用的会话短标识：只保留 id 的 ASCII 安全字符。"""
    raw = str((snapshot or {}).get("session_id", "") or "")
    safe = re.sub(r"[^A-Za-z0-9_-]", "", raw)[:8]
    return safe or "session"


def filename(snapshot, fmt: str = "md") -> str:
    """下载文件名：`interview_report_<id8>_<YYYYmmdd-HHMM>.md`。"""
    stamp = time.strftime("%Y%m%d-%H%M", time.localtime())
    return f"interview_report_{_session_name(snapshot)}_{stamp}.{fmt}"


def to_markdown(snapshot) -> str:
    """渲染 Markdown 报告：抬头 → 总评 → 评分 → 对话记录。"""
    snapshot = snapshot or {}
    lines = ["# AI 模拟面试官 · 面试报告", ""]

    role = snapshot.get("role") or "（未知岗位）"
    lines.append(f"- **岗位**：{role}")
    if snapshot.get("session_id"):
        lines.append(f"- **会话**：{snapshot['session_id']}")
    started = _fmt_time(snapshot.get("created_at"))
    if started:
        lines.append(f"- **开始**：{started}")
    ended = _fmt_time(snapshot.get("updated_at"))
    if ended:
        lines.append(f"- **最后更新**：{ended}")
    if snapshot.get("question_count") is not None:
        lines.append(f"- **问答轮次**：{snapshot.get('question_count', 0)}")
    lines.append(f"- **状态**：{'已结束' if snapshot.get('is_finished') else '进行中'}")
    lines.append("")

    text = report_text(snapshot)
    lines += ["## 总评", "", text or "（本次面试还没有生成报告）", ""]

    score = snapshot.get("score")
    dimensions = (score or {}).get("dimensions") if isinstance(score, dict) else None
    if dimensions:
        lines += ["## 评分", ""]
        if isinstance(score.get("total"), int):
            lines.append(f"**总分：{score['total']} / 100**")
            lines.append("")
        lines += ["| 维度 | 得分 | 评语 |", "| --- | --- | --- |"]
        for dim in dimensions:
            score_text = f"{dim.get('score', '?')} / {dim.get('max', 10)}"
            comment = str(dim.get("comment") or "—").replace("|", "\\|")
            lines.append(f"| {dim.get('name', '?')} | {score_text} | {comment} |")
        lines.append("")
        for dim in dimensions:
            if dim.get("evidence"):
                lines.append(f"> **{dim.get('name', '')}** 依据：{dim['evidence']}")
        lines.append("")
        missing = score.get("missing") or []
        if missing:
            lines.append(f"（本次未评的维度：{'、'.join(missing)}）")
            lines.append("")
        if score.get("summary"):
            lines += [f"**一句话总评**：{score['summary']}", ""]

    # 逐题复盘：每题「问题 / 他的原话 / 更好的答法」。
    # 这是这份报告里**最像"练习工具"**的一节 —— 总分和维度只说明现状，
    # 这一节才告诉他下一遍该怎么答。
    per_question = (score or {}).get("per_question") if isinstance(score, dict) else None
    if per_question:
        lines += ["## 逐题复盘", ""]
        for item in per_question:
            if not isinstance(item, dict):
                continue
            lines += [f"**第 {item.get('index', '?')} 题**：{item.get('question') or '（开场）'}", ""]
            if item.get("evidence"):
                lines.append(f"- 你的原话：{item['evidence']}")
            if item.get("suggestion"):
                lines.append(f"- 更好的答法：{item['suggestion']}")
            lines.append("")

    messages = snapshot.get("messages") or []
    lines += ["## 对话记录", ""]
    if not messages:
        lines.append("（没有对话内容）")
        lines.append("")
    for message in messages:
        speaker = "面试官" if message.get("role") == "assistant" else "候选人"
        lines.append(f"**{speaker}**：{message.get('content', '')}")
        lines.append("")

    lines += ["---", "由 AI 模拟面试官生成（openvela 大赛 2026 · 151 号队 mianbao）", ""]
    return "\n".join(lines)


def to_json(snapshot) -> str:
    """整份快照的 JSON（含评分与完整对话），给以后做纵向分析用。"""
    return json.dumps(snapshot or {}, ensure_ascii=False, indent=2)


def export(snapshot, fmt: str = "md"):
    """按格式渲染，返回 `(正文, MIME, 文件名)`；格式不支持时返回 None。

    返回 None 而不是抛异常：路由那边要据此回 400，用异常反而要多写一层 try。
    """
    fmt = (fmt or "md").lower()
    if fmt not in SUPPORTED:
        return None
    body = to_markdown(snapshot) if fmt == "md" else to_json(snapshot)
    return body, MIME[fmt], filename(snapshot, fmt)
