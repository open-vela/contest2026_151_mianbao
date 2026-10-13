"""相邻两问的相似度 —— 给「原样重问」量一把尺子。

来历（2026-10-01，台账 §11.43）：一次完整排练里，第 9 轮把第 8 轮的问题重说了
一遍（相似度 0.76）—— 候选人刚答完就被问一模一样的题，听起来像没在听。
根子在 next_question 硬性要求第 5 条「答非所问就再问一次」没约束换说法：
模型严格照做，于是重灌了一遍。

修了提示词之外，排练补了这条判据 —— 不然它下次再犯，没有人看得见
（「测不到的路径等于没有这道防线」，§11.21）。

为什么单独一个模块：判据是**纯函数**（不联网、不依赖第三方包），单测按
run_tests.sh「纯单测」那一档的纪律独立跑；rehearsal.py 带 requests 依赖，
判据不该跟着它一起要装依赖才能验。
"""

# 相似度上限。2026-10-01 实测两簇：同一题的两种问法 0.76（就是上面那对），
# 不同的题 0.00~0.13 —— 0.5 落在中间的空白带里，两边都留足了余量。
MAX_QUESTION_SIMILARITY = 0.5


def question_similarity(previous, current) -> float:
    """相邻两问的相似度：字符二元组的 containment（交集 ÷ 较小集合）。

    用二元组而不是单字：单字会把「怎么 / 有没有」这类高频词算成相似。
    除以较小的集合而不是并集：原样重问往往是「上一问 + 一点新词」，
    并集会被新词稀释，containment 不会。

    只认汉字、字母与数字（`str.isalnum()`），标点与空白先丢掉 ——
    「，」「？」在两句里都出现，不该算进相似度。
    """
    def bigrams(text):
        # 非字符串一律当空：判据会被喂进各种形状，别在 None 上炸
        # （同 report_guard 对坏输入的取舍）。
        if not isinstance(text, str):
            return set()
        cleaned = "".join(ch for ch in text if ch.isalnum())
        return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}

    first, second = bigrams(previous), bigrams(current)
    if not first or not second:
        return 0.0
    return len(first & second) / min(len(first), len(second))


# 首轮生成的问题与上一问几乎一样时，追加给模型的纠偏指令（机制同 report_guard.RETRY_HINT：
# 把原回复作为 assistant 消息带上、这条作为下一条 user 消息，只重试一次）。
#
# 来历（2026-10-13）：五个岗位各跑一轮排练，Data Analyst 那跑的第 9 问把第 8 问
# 重说了一遍（相似度 0.84，候选人刚答非所问）—— §11.43 的提示词修复**减少但没根除**
# 这个行为。同 §11.21/§11.30 的结论：提示词是"劝"，拦不住的要在代码里拦。
#
# ⚠️ 指令必须给出**两条出路**（换问法 / 换话题）。只说"不要重复"没有给出路，
#    模型会在原地打转 —— 同 report_guard 把"摘关键词连起来"那个逃生口再指一次的取舍。
RETRY_HINT = (
    "你刚写的这一问和上一轮几乎一样，候选人刚答完就被问同一道题，听起来像没在听。"
    "请重写这一问：\n"
    "⚠️ 两条路选一条 —— ① 换一种问法（更具体、给个例子、缩小范围）；"
    "② 直接换下一个话题。\n"
    "只输出你要对候选人说的那句话（1~3 句，以一个问题结尾）。"
)


def is_repeat(previous, current) -> bool:
    """`current` 是不是在几乎原样重问 `previous` —— 闸门的硬判据。

    阈值与排练判据共用 `MAX_QUESTION_SIMILARITY`：**闸门放行的，排练才认**；
    两边各定一套，就会出现"拦了但排练说没问题"或反过来的漂移。
    """
    return question_similarity(previous, current) > MAX_QUESTION_SIMILARITY
