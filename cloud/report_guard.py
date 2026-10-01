"""报告端的闸：确保那份要念给候选人听的报告里，真的引用了他自己说过的话。

为什么需要它（台账 §11.27 / §11.30）
------------------------------------
`skills/generate_feedback.json` 把"至少引用一处候选人原话（用「」括起来）"
写成了硬性要求，还特意写明"这一条没有例外"。但 2026-09-30 的真机实测证明
**它在退化输入下会失效**：候选人三句只说了 6 / 2 / 5 个字，报告的四个维度
全写"未涉及"，而「」引用一个都没有。

那次的输入确实退化了（人几乎没说话），但这不是"可以不管"的理由：

1. 报告是这个产品**唯一的产出物**，也是唯一会被读出来给人听的成品；
2. 提示词在退化情形下**自相矛盾** —— 它说"评价必须落到他实际说过的话上"，
   可四个维度都"未涉及"时根本没有可落地的评价，模型于是把引用一起丢了。
   **矛盾没被解开，模型就自己找了个解释。**

所以这道闸分两个判据，一硬一软：

* `has_quote()` —— **硬判据**：有没有「」引用。缺了就由调用方**重试一次**，
  并补一句专门覆盖退化情形的提示。只在缺的时候才多花一次调用，正常轮次零成本。
* `check_quote_evidence()` —— **软判据**：引用的话是不是真出自候选人。**只记日志、
  不拦**。因为提示词明确允许"摘不出完整句子就摘关键词连起来"，那是合法的**拼接**
  而非连续的原文，严格的子串比对会大面积误报（同 `score_guard.evidence_supported`
  的取舍：它是核对用的，不是拦截用的）。

设计纪律同 `reply_guard` / `score_guard`：**纯函数、只用标准库、确定性、可单测**。
"""
import re

# 引用的一般形式。上限 40 字：提示词要求"不超过 12 个字"，这里放宽到 40 ——
# 闸门只回答"有没有"，不该因为模型多引了几个字就判成没有，那是提示词该管的事。
_QUOTE_RE = re.compile(r"「([^」]{1,40})」")

# 与 finish_guard / score_guard 同一套字符集（**刻意不跨模块 import**：
# 三个 guard 各自独立可读、可单测，比省下这一行更重要 —— 同 score_guard 的取舍）。
_PUNCT_RE = re.compile(
    r"[\s　。，、！？!?,;；:：…~～·\"'“”‘’（）()\[\]【】《》<>-]+"
)

# 首轮没引用时，追加给模型的纠偏指令。
#
# 两条要求原样重述（「」括起来 / 摘不出整句就摘关键词），是因为**退化输入下
# 模型放弃引用的理由恰恰是"没什么好引的"** —— 而提示词末尾本来就写了"摘不出
# 完整句子就摘他话里的关键词连起来"，它没照做。这里把那个逃生口再指一次。
RETRY_HINT = (
    "这份报告里没有任何「」引用，不符合要求。请重写一遍。\n"
    "⚠️ 无论候选人说了多少，都必须用「」引用至少一处他说过的话 —— "
    "哪怕他整场只说了几个字，也把那几个字原样摘出来。\n"
    "其余要求（六句话、200 字以内、不要 Markdown、不写标题）都不变。"
)

# 超长的纠偏指令（2026-10-01 加，见台账 §11.41）。
#
# 那天一次排练里报告写到 296 字（前几跑都是 80~207）—— 提示词写着"200 字以内"，
# 模型偶尔就是不听话。连带把 TTS 撑到 2.9MB、播了 27 秒，逼近端侧 8MB 响应上限。
# 这正是 §11.21-3 那条"报告端没有闸门"的又一个实例。
RETRY_HINT_TOO_LONG = (
    "这份报告太长了，不符合要求。请重写一遍，压到 200 字以内。\n"
    "⚠️ 六句话的结构不变（一句总评 + 四个维度各一句 + 一条改进建议），"
    "但每一句都要更短 —— 这份报告是被 TTS 念出来的，太长会播很久。\n"
    "其余要求（必须有一处「」引用、不要 Markdown、不写标题）都不变。"
)

# 报告长度上限。**与 rehearsal.py 的 MAX_REPORT_CHARS 保持一致**（250）。
# 提示词要求的是 200 字，这里留 50 字余量：超一点点不值得多花一次调用，超多了才动手。
MAX_CHARS = 250


def problems(report) -> list:
    """这份报告有哪些不合格的地方（空列表 = 合格）。

    返回**键名**而不是句子 —— 调用方据此拼纠偏指令，也能直接写进日志。
    """
    items = []
    if not has_quote(report):
        items.append("no_quote")
    if len((report or "").strip()) > MAX_CHARS:
        items.append("too_long")
    return items


def retry_hint(items) -> str:
    """按不合格的项拼一条纠偏指令 —— 一次重试里把所有问题一起说，不叠加调用。"""
    hints = []
    if "no_quote" in (items or []):
        hints.append(RETRY_HINT)
    if "too_long" in (items or []):
        hints.append(RETRY_HINT_TOO_LONG)
    return "\n\n".join(hints)


def quoted_spans(report) -> list:
    """把报告里所有「」引用摘出来，按出现顺序返回。没有则返回空列表。"""
    if not report or not isinstance(report, str):
        return []
    return [m.group(1).strip() for m in _QUOTE_RE.finditer(report) if m.group(1).strip()]


def has_quote(report) -> bool:
    """这份报告里有没有至少一处「」引用 —— 硬判据，缺了就重试。"""
    return len(quoted_spans(report)) > 0


def _squash(text) -> str:
    """压掉空白与标点，用于"这句原话在不在历史里"的比对。

    语音转写出来的标点本来就不可信，先压掉再比。
    """
    if not text:
        return ""
    return _PUNCT_RE.sub("", str(text)).lower()


def check_quote_evidence(report, history) -> list:
    """返回**没能在候选人发言里找到**的那几条引用（都对得上则为空列表）。

    ⚠️ 这是**核对**用的，不是拦截用的。提示词允许"摘关键词连起来"，那种引用
    本来就不是连续的原文，这里会判成"对不上" —— 所以调用方只应该记日志。
    """
    bad = []
    for quote in quoted_spans(report):
        target = _squash(quote)
        if not target:
            continue
        found = False
        for message in history or []:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            if target in _squash(message.get("content", "")):
                found = True
                break
        if not found:
            bad.append(quote)
    return bad
