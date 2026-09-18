"""剥掉模型回复里的「元叙述」，只留下要对候选人说的话。

为什么需要它（台账 §11.20 / §11.21）
------------------------------------
`next_question` 走的是**语音**链路：模型写下的每个字都会被 TTS 逐字念给候选人听。
而模型在被污染的会话历史下会开始输出「判断：…／理由：…／追问：…」这类分析腔
（9/18 实测 216~229 字），念出来就是灾难。

§11.20 记过这个故障的一个致命性质：**它会自我强化、不会自愈** —— 模型的输出被原样
存进 history，下一轮又成了它自己的范例。

提示词层面的约束（禁 Markdown、禁判断/理由、硬性要求放结尾）能挡住绝大多数轮次，
但 9/18 的 A/B 证明**光靠提示词挡不住被污染的历史**：删掉提示词里的「错误示例」
之后，模型改从历史里学那个格式，照样输出 `理由：候选人的回答非常简短…`。
提示词是"劝"，这里补一道确定性的"闸"：

  1. **出去的字**先过 `strip_meta()` —— 念出来的永远只是个问题；
  2. **读进来的历史**也过一遍 —— 已经脏掉的会话能**自愈**，不必重启云端重开一场
     （这正是 §11.20 当时唯一的恢复手段）。

设计上的两条自我约束
--------------------
* **干净文本零改动**：只有检测到元叙述痕迹才动手。正常回复原样通过，不做"顺手
  美化"—— 否则每改一次这个函数都等于在动正常的语气。
* **纯函数、确定性、无随机、只用标准库**：同样输入永远同样输出，可单测。
  判据见 `cloud/test_reply_guard.py`。
"""
import re

# 兜底问句：脏回复被剥空之后用它顶上。
#
# 必须是**中性、不带评价、还能把面试推下去**的一句 —— 它会在候选人答得让模型"跑偏"
# 时出现，绝不能带任何判断或点评（那正是要避免的东西）。
FALLBACK_QUESTION = "好的，能就刚才提到的这点再具体说说吗？"

# 整行都是元叙述的：`判断：追问细节`、`理由：…`。
# 注意 `追问：`／`新问题：` 不在这里 —— 它们是**问题本身的引子**，要留内容、只去标签。
_META_LINE_RE = re.compile(
    r"^\s*(?:[#>*\-•·]\s*)*"
    r"(?:判断|理由|分析|说明|备注|设计意图|设计思路|考察点|"
    r"追问理由|追问细节|追问方向|问题设计说明|下一步)"
    r"\s*[:：]"
)

# 问题引子标签：去掉标签、留下问句本身。
_LABEL_PREFIX_RE = re.compile(r"^\s*(?:追问|新问题|问题|提问)\s*[:：]\s*")

# 分隔线与表格行：Markdown 里用来分块的东西，语音里毫无意义。
_SEPARATOR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,}|={3,})\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")

# 行首的装饰性 Markdown（`# `、`> `、`- `、`**`），以及残留的加粗标记。
_DECOR_RE = re.compile(r"(?:^\s*(?:[#>\-*•·]\s+)+)|(?:\*\*)")

# 分块：空行，以及 `---` / `***` / `___` / `===` 这类分隔线。
# 脏回复几乎都是"一块一块"的（判断块 / 理由块 / 追问块），按块取舍比按行干净。
_BLOCK_RE = re.compile(
    r"(?:\n\s*\n)|(?:^[ \t]*(?:-{3,}|\*{3,}|_{3,}|={3,})[ \t]*$)",
    re.MULTILINE,
)


def _is_dirty(text: str) -> bool:
    """有没有元叙述痕迹。没有就别动它（干净文本零改动）。"""
    for line in text.splitlines():
        if _SEPARATOR_RE.match(line) or _TABLE_ROW_RE.match(line):
            return True
        if _META_LINE_RE.match(line):
            return True
        if "**" in line:
            return True
    return False


def strip_meta(text: str) -> str:
    """返回可以安全念给候选人听的那段话；剥不出东西时返回 `""`。

    只在检测到元叙述痕迹时才动手，干净文本原样返回 —— 这条保证是**幂等**的：
    `strip_meta(strip_meta(x)) == strip_meta(x)`。

    脏文本的取舍规则是**按块**而不是按句：不含问句的块一律不念（"判断"块、
    "理由"块、表格、分析啰嗦），含问句的块去掉标签后整块留下。
    刻意**不做句子级截断** —— 那会把"您提到按标题切分，那跨章节的内容怎么办？
    做过对比实验吗？"砍成后半句"做过对比实验吗？"，反而更没法听。
    """
    if not text or not text.strip():
        return ""
    if not _is_dirty(text):
        return text.strip()

    kept = []
    for block in _BLOCK_RE.split(text):
        block = block.strip()
        if not block:
            continue
        # 不含问句的块：不念。脏回复里的这些块只会是判断/理由/分析。
        if "？" not in block and "?" not in block:
            continue
        lines = []
        for line in block.splitlines():
            if _TABLE_ROW_RE.match(line):
                continue
            line = _DECOR_RE.sub("", line)
            line = _LABEL_PREFIX_RE.sub("", line)
            # 「判断：需要追问 你刚提到…？」这种把标签和问句写在一行的：去标签、留问句
            line = _META_LINE_RE.sub("", line)
            if line.strip():
                lines.append(line.strip())
        if lines:
            kept.append(" ".join(lines))

    return " ".join(kept).strip()


def clean_history(history: list) -> list:
    """把历史里的 assistant 消息过一遍闸（user 消息不碰）。

    用途：让**已经脏掉的会话自愈** —— 模型看到的是它自己"干净版"的历史，
    不再从污染里继续学。干净会话经过这里是逐条 no-op。
    """
    cleaned = []
    for message in history or []:
        if isinstance(message, dict) and message.get("role") == "assistant":
            text = strip_meta(message.get("content", ""))
            if not text:
                # 整条都是元叙述，没有任何可用内容 —— 从历史里摘掉，
                # 留着只会继续当"范例"。注意别把这条变成空串消息（有些
                # API 不接受空 content）。
                continue
            message = {**message, "content": text}
        cleaned.append(message)
    return cleaned
