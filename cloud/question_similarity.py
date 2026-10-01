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
