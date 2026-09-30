"""结构化评分的"闸"：把模型吐回来的 JSON 收拾成可信的形状。

为什么需要它
------------
报告目前只有一段 200 字的文本（`skills/generate_feedback.json` 里 `max_tokens`
是 600，200 字是团队锁定的上限，不能靠加长文本来塞分项）。想看"哪一项弱、
弱在哪句话上"，就得让模型额外给一份结构化评分。

但**模型给出的分数不能直接信**：

* 它会写 `json` 之外的解释文字、包 ``` 围栏、加 `以下是我的评分：` 前缀；
* 它会把某个维度打成 12 分（满分 10）、"良好"（不是数字）、漏掉一个维度；
* 它算不对算术 —— 所以**总分由我们算**，永远不采信模型自己算的 total。

这个模块的职责就是把上面这些全部挡掉：`extract_json` 负责"从一坨文本里挖出
那个 JSON"，`normalize` 负责"把残缺/越界的字段收拾干净或丢弃"，`is_usable`
负责"这份评分到底能不能用"。全部是纯函数，可单测（同 `reply_guard` 的纪律）。

维度是**代码里定死的**（`DIMENSIONS`）
--------------------------------------
单人自练的场景下，固定维度才有意义 —— 不固定就没法纵向比较"上个月这项 6 分，
这个月 7 分"。这个元组是唯一事实来源：P2 的提示词由它生成，`normalize` 也用它
校验，因此不存在"提示词里写了 5 个维度、代码只认 4 个"这种漂移。
"""
import json
import re

# 评分维度：唯一事实来源。改这里就等于改提示词（P2 会把它拼进 prompt）。
DIMENSIONS = ("表达与逻辑", "专业深度", "项目经验", "岗位匹配")

# 单维度满分。用 0~10 的整数：模型对 10 分制最稳，而且前端画条形图够用。
MAX_SCORE = 10

# 「这个维度没有可引用的原话」的占位符（见 skills/score_report.json 的要求）。
# `verify_evidence()` 要跳过它 —— 它是诚实的"没有依据"，不是编造的依据。
NOT_MENTIONED = "未提及"

# 各字段的长度上限 —— 这是**语音**产品，评分是给人看的短评，不是小作文。
EVIDENCE_MAX = 60
COMMENT_MAX = 80
SUMMARY_MAX = 160

_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.DOTALL)

# 与 finish_guard._PUNCT_RE 同一套字符集（刻意不跨模块 import：两个 guard
# 各自独立可读、可单测，比省下这一行更重要）。
_PUNCT_RE = re.compile(
    r"[\s　。，、！？!?,;；:：…~～·\"'“”‘’（）()\[\]【】《》<>-]+"
)


def extract_json(text):
    """从模型输出里挖出第一个 JSON 对象；挖不到返回 None。

    依次尝试：``` 围栏里的内容 → 整段文本。取对象用**花括号配对**而不是
    `rfind("}")`：模型常在 JSON 后面再补一句"希望对您有帮助"，`rfind` 会把
    那句话里的 `}`（如果有）连进来，配对计数不会。
    """
    if not text:
        return None

    candidates = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        blob = _first_object(candidate)
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _first_object(text: str) -> str:
    """返回第一个花括号配对完整的子串；找不到返回 `""`。

    计数时要跳过字符串**内部**的括号（`{"comment": "他写了 {" }` 这种），
    否则会提前截断。
    """
    start = text.find("{")
    if start < 0:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _clean_str(value, limit: int) -> str:
    """取出一个可展示的短字符串：非字符串当空，压掉换行，超长截断。"""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _as_score(value):
    """把模型给的分数收拾成 0~MAX_SCORE 的整数；给不出数字则返回 None。

    接受数字字符串（模型有时会写成 `"7"`），拒绝布尔值（`True` 在 Python 里
    是 int 的子类，不特判就会变成 1 分）。
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip().rstrip("分"))
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    # 越界一律夹到边界，而不是丢弃 —— 模型打成 12 分说明它认为"很好"，
    # 丢掉这一维反而会让评分缺一块。
    return int(max(0, min(MAX_SCORE, round(value))))


def normalize(raw):
    """把模型给的原始结构收拾成规范评分；无法收拾时返回 `{}`。

    规范形状：

        {"dimensions": [{"name", "score", "max", "evidence", "comment"}, ...],
         "missing":    ["岗位匹配", ...],     # 模型漏掉的维度，如实记录
         "total":      75,                    # 0~100，**我们算的**
         "summary":    "一句话总评",
         "status":     "ok"}

    刻意**丢掉**模型自己算的 total：它算不对，而总分是给人看的第一眼数字，
    错一位就会被当成评分不可信。缺失的维度也不补零 —— 补零等于凭空扣分，
    如实列在 `missing` 里让前端显示"未评"才是诚实的。
    """
    if not isinstance(raw, dict):
        return {}

    items = raw.get("dimensions")
    if not isinstance(items, list):
        return {}

    dims = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"), 16)
        if name not in DIMENSIONS or name in seen:
            continue          # 不认识的维度直接丢，不让它污染固定的四维
        score = _as_score(item.get("score"))
        if score is None:
            continue
        seen.add(name)
        dims.append({
            "name": name,
            "score": score,
            "max": MAX_SCORE,
            "evidence": _clean_str(item.get("evidence"), EVIDENCE_MAX),
            "comment": _clean_str(item.get("comment"), COMMENT_MAX),
        })

    if not dims:
        return {}

    # 固定顺序：前端表格与纵向对比都依赖它，不能随模型输出的顺序飘。
    dims.sort(key=lambda d: DIMENSIONS.index(d["name"]))

    return {
        "dimensions": dims,
        "missing": [d for d in DIMENSIONS if d not in seen],
        "total": round(sum(d["score"] for d in dims) / len(dims) * 10),
        "summary": _clean_str(raw.get("summary"), SUMMARY_MAX),
        "status": "ok",
    }


def is_usable(score) -> bool:
    """这份评分能不能展示给用户（结构完整、分数都在合法区间内）。"""
    if not isinstance(score, dict):
        return False
    dims = score.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return False
    for dim in dims:
        if not isinstance(dim, dict):
            return False
        value = dim.get("score")
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if not 0 <= value <= MAX_SCORE:
            return False
    return isinstance(score.get("total"), int)


def evidence_supported(quote, history) -> bool:
    """这句"证据"是不是真的出自候选人的原话。

    用途是**核对**而不是拦截：模型经常把原话压缩或改一两个字（"我负责检索模块"
    → "负责检索模块"），严格判定会大面积误报。所以这里只回答"能不能在候选人的
    发言里找到"，由调用方决定是记日志还是打标记，不用它否掉整份评分。

    比对前把标点和空白全部压掉 —— 语音转写出来的标点本来就不可信。
    """
    target = _squash(quote)
    if not target:
        return False
    for message in history or []:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        if target in _squash(message.get("content", "")):
            return True
    return False


def verify_evidence(score, history) -> list:
    """逐维度核对证据，返回**没能对上原话**的维度名列表（对上则为空列表）。

    ⚠️ 写 `NOT_MENTIONED` 的维度**跳过不查** —— 那不是"编造的依据"，而是模型
    诚实地说"这个维度没什么可引用的"。不跳过的话，一场候选人没怎么说话的面试
    会在日志里刷出四个"对不上"，把真正的信号淹掉。
    """
    bad = []
    for dim in (score or {}).get("dimensions", []) or []:
        if not isinstance(dim, dict):
            continue
        evidence = dim.get("evidence", "")
        if not evidence or _squash(evidence) == _squash(NOT_MENTIONED):
            continue
        if not evidence_supported(evidence, history):
            bad.append(dim.get("name", "?"))
    return bad


def _squash(text) -> str:
    """压掉空白与标点，用于"这句原话在不在历史里"的子串比对。"""
    if not text:
        return ""
    return _PUNCT_RE.sub("", str(text)).lower()
