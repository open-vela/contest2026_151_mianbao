#!/usr/bin/env python3
"""question_similarity 单元测试 —— 不联网、不需要 key：`python3 test_question_similarity.py`。

样本逐字抄自 2026-10-01 那次排练的实录（台账 §11.43），不是手编的：

* `REPEAT_*` 是第 8→9 轮那对**原样重问**（实测 0.76）—— 判据就是为它加的，
  必须拦得住；
* `NORMAL_PAIRS` 是同一次排练里正常推进的三对（实测 0.00~0.13）—— 必须一个
  都不误伤。只测「拦得住」不测「不误伤」，阈值往后就会悄悄开始乱报。
"""
import unittest

import question_similarity as qs

# ---- 第 8→9 轮：原样重问（2026-10-01 排练实录）----
REPEAT_A = "这三百条金标集里，命中率的判定标准是什么？是人工标注的精确匹配，还是允许模型判断相关性？"
REPEAT_B = "那这三百条金标集的命中率判定标准是什么？是人工标注精确匹配，还是让模型来判断相关性？"

# ---- 同一次排练里正常推进的相邻两问（第 1→2、2→3、6→7 轮实录）----
NORMAL_PAIRS = [
    ("您提到的智能客服和知识库问答这两个方向都挺贴近实际业务的，能挑其中一个，"
     "具体讲讲您在里头负责哪部分、当时遇到的最大挑战是什么吗？",
     "混合召回这块，向量和关键词的权重是怎么定的？上线后有没有数据能说明它比纯向量检索效果好？"),
    ("混合召回这块，向量和关键词的权重是怎么定的？上线后有没有数据能说明它比纯向量检索效果好？",
     "选了按标题切之后，有没有量化过召回质量的变化？比如切块数量、平均块长，或者人工评测的准确率对比？"),
    ("语义缓存里相似度阈值是怎么定的？调高调低分别会带来什么问题，你们当时是怎么平衡命中率和答错的风险的？",
     "缓存里存的是检索到的上下文，还是直接存最终答案？如果只改了重排或者生成的prompt，缓存会跟着失效吗？"),
]


class TestQuestionSimilarity(unittest.TestCase):
    def test_repeat_exceeds_threshold(self):
        """原样重问必须超阈值 —— 判据就是为这一对加的。"""
        self.assertGreater(qs.question_similarity(REPEAT_A, REPEAT_B),
                           qs.MAX_QUESTION_SIMILARITY)

    def test_normal_pairs_below_threshold(self):
        """正常推进的相邻两问一个都不能误伤（只测「拦得住」，阈值就会悄悄收紧）。"""
        for first, second in NORMAL_PAIRS:
            with self.subTest(question=second[:16]):
                self.assertLess(qs.question_similarity(first, second),
                                qs.MAX_QUESTION_SIMILARITY)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(qs.question_similarity(REPEAT_A, REPEAT_B),
                               qs.question_similarity(REPEAT_B, REPEAT_A))

    def test_bad_shapes_do_not_crash(self):
        """判据会被喂进各种形状（None / 数字 / 空），别炸 —— 同 report_guard 的取舍。"""
        for bad in (None, "", 42, [], {}):
            with self.subTest(value=bad):
                self.assertEqual(qs.question_similarity(bad, REPEAT_A), 0.0)
                self.assertEqual(qs.question_similarity(REPEAT_A, bad), 0.0)

    def test_punctuation_only_is_zero(self):
        """只剩标点就没什么可比 —— 0.0，不是崩溃，也不是 1.0。"""
        self.assertEqual(qs.question_similarity("，。？", "？！，。"), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
