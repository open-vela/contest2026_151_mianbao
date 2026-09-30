#!/usr/bin/env python3
"""score_guard 单元测试 —— 不联网、不需要 key：`python3 test_score_guard.py`。

样本按"模型实际会怎么写"来编：带 ``` 围栏、带前后解释、把分数写成字符串、
打成 12 分、漏掉一个维度、自己算的总分是错的 —— 这些都不是假想，是评分这类
任务里最常见的五种走样。
"""
import unittest

from score_guard import (
    DIMENSIONS,
    MAX_SCORE,
    NOT_MENTIONED,
    evidence_supported,
    extract_json,
    is_usable,
    normalize,
    verify_evidence,
)

# 一份"形状正确"的原始输出：4 维，分数 8/6/7/7（均值 7.0 → 总分应为 70）
# 但模型自己写的 total 是 999 —— normalize 必须丢掉它。
GOOD_RAW = {
    "dimensions": [
        {"name": "表达与逻辑", "score": 8, "evidence": "我负责的是检索模块",
         "comment": "先结论后细节，条理清晰"},
        {"name": "专业深度", "score": 6, "evidence": "用的是 Faiss",
         "comment": "能说清选型，但没展开召回评估"},
        {"name": "项目经验", "score": 7, "evidence": "线上 QPS 大概两百",
         "comment": "有真实数据，规模偏小"},
        {"name": "岗位匹配", "score": 7, "evidence": "我做的是 RAG 检索",
         "comment": "方向对口"},
    ],
    "total": 999,
    "summary": "基础扎实，建议把召回评估的细节补齐。",
}

HISTORY = [
    {"role": "assistant", "content": "你在项目里负责什么？"},
    {"role": "user", "content": "我负责的是检索模块，用的是 Faiss。"},
    {"role": "user", "content": "线上 QPS 大概两百，我做的是 RAG 检索。"},
]


class TestExtractJson(unittest.TestCase):
    def test_bare_object(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        text = "以下是我的评分：\n```json\n{\"a\": 1}\n```\n希望有帮助"
        self.assertEqual(extract_json(text), {"a": 1})

    def test_fence_without_language_tag(self):
        self.assertEqual(extract_json("```\n{\"a\": 1}\n```"), {"a": 1})

    def test_trailing_prose_with_brace(self):
        """rfind 式截取的经典失败样例：JSON 后面还有一句带花括号的话。"""
        text = '{"a": 1}\n\n（说明：上面的 {\"a\"} 就是结果）'
        self.assertEqual(extract_json(text), {"a": 1})

    def test_braces_inside_string(self):
        text = '{"comment": "他写了 { 没闭合"}'
        self.assertEqual(extract_json(text), {"comment": "他写了 { 没闭合"})

    def test_escaped_quote_inside_string(self):
        text = '{"comment": "他说 \\"结束\\" 了"}'
        self.assertEqual(extract_json(text), {"comment": '他说 "结束" 了'})

    def test_first_object_wins(self):
        self.assertEqual(extract_json('前言 {"a": 1} 中间 {"b": 2}'), {"a": 1})

    def test_not_json(self):
        for text in ("", None, "模型今天不想输出 JSON", "{不是 JSON}", "[1, 2]"):
            with self.subTest(text=text):
                self.assertIsNone(extract_json(text))

    def test_array_is_not_accepted(self):
        """顶层是数组的不算 —— 规范结构是对象。"""
        self.assertIsNone(extract_json("[1, 2, 3]"))


class TestNormalize(unittest.TestCase):
    def test_good_input(self):
        out = normalize(GOOD_RAW)
        self.assertTrue(is_usable(out))
        self.assertEqual([d["name"] for d in out["dimensions"]], list(DIMENSIONS))
        self.assertEqual([d["score"] for d in out["dimensions"]], [8, 6, 7, 7])
        self.assertEqual(out["total"], 70)
        self.assertEqual(out["missing"], [])
        self.assertEqual(out["status"], "ok")

    def test_ignores_model_total(self):
        """总分**我们算**：模型写 999 也不采信。"""
        raw = dict(GOOD_RAW, total=999)
        self.assertEqual(normalize(raw)["total"], 70)

    def test_score_is_clamped(self):
        raw = {"dimensions": [
            {"name": "表达与逻辑", "score": 12},     # 越界上限
            {"name": "专业深度", "score": -3},       # 越界下限
        ]}
        out = normalize(raw)
        self.assertEqual([d["score"] for d in out["dimensions"]], [MAX_SCORE, 0])

    def test_numeric_string_is_accepted(self):
        raw = {"dimensions": [{"name": "表达与逻辑", "score": "7"}]}
        self.assertEqual(normalize(raw)["dimensions"][0]["score"], 7)

    def test_score_with_unit_suffix(self):
        raw = {"dimensions": [{"name": "表达与逻辑", "score": "7分"}]}
        self.assertEqual(normalize(raw)["dimensions"][0]["score"], 7)

    def test_boolean_score_is_dropped(self):
        """True 在 Python 里是 int 的子类 —— 不特判就会变成 1 分。"""
        raw = {"dimensions": [{"name": "表达与逻辑", "score": True}]}
        self.assertEqual(normalize(raw), {})

    def test_non_numeric_score_is_dropped(self):
        raw = {"dimensions": [{"name": "表达与逻辑", "score": "良好"}]}
        self.assertEqual(normalize(raw), {})

    def test_unknown_dimension_is_dropped(self):
        raw = {"dimensions": [
            {"name": "颜值", "score": 10},
            {"name": "表达与逻辑", "score": 8},
        ]}
        out = normalize(raw)
        self.assertEqual([d["name"] for d in out["dimensions"]], ["表达与逻辑"])

    def test_duplicate_dimension_keeps_first(self):
        raw = {"dimensions": [
            {"name": "表达与逻辑", "score": 8},
            {"name": "表达与逻辑", "score": 2},
        ]}
        out = normalize(raw)
        self.assertEqual(len(out["dimensions"]), 1)
        self.assertEqual(out["dimensions"][0]["score"], 8)

    def test_missing_dimension_is_recorded_not_zeroed(self):
        """缺的维度如实记进 missing，**不补零** —— 补零等于凭空扣分。"""
        raw = {"dimensions": [
            {"name": "表达与逻辑", "score": 8},
            {"name": "专业深度", "score": 6},
            {"name": "项目经验", "score": 7},
        ]}
        out = normalize(raw)
        self.assertEqual(out["missing"], ["岗位匹配"])
        self.assertEqual(out["total"], 70)      # 只按已评的三维取均值
        self.assertEqual(len(out["dimensions"]), 3)

    def test_order_is_fixed_regardless_of_input(self):
        raw = {"dimensions": [
            {"name": "岗位匹配", "score": 7},
            {"name": "表达与逻辑", "score": 8},
        ]}
        out = normalize(raw)
        self.assertEqual([d["name"] for d in out["dimensions"]],
                         ["表达与逻辑", "岗位匹配"])

    def test_long_text_is_truncated(self):
        raw = {"dimensions": [{"name": "表达与逻辑", "score": 8,
                               "comment": "很" * 500, "evidence": "细" * 500}],
               "summary": "总" * 500}
        out = normalize(raw)
        self.assertLessEqual(len(out["dimensions"][0]["comment"]), 81)
        self.assertLessEqual(len(out["dimensions"][0]["evidence"]), 61)
        self.assertLessEqual(len(out["summary"]), 161)

    def test_bad_shapes(self):
        for bad in (None, "文字", 42, [], {}, {"dimensions": "不是列表"},
                    {"dimensions": []}, {"dimensions": [{}]},
                    {"dimensions": [{"name": "表达与逻辑"}]}):
            with self.subTest(raw=bad):
                self.assertEqual(normalize(bad), {})


class TestIsUsable(unittest.TestCase):
    def test_good(self):
        self.assertTrue(is_usable(normalize(GOOD_RAW)))

    def test_rejects_empty_and_none(self):
        for bad in ({}, None, "x", []):
            with self.subTest(score=bad):
                self.assertFalse(is_usable(bad))

    def test_rejects_out_of_range(self):
        self.assertFalse(is_usable({
            "dimensions": [{"name": "表达与逻辑", "score": 99, "max": 10}],
            "total": 99,
        }))


class TestEvidence(unittest.TestCase):
    def test_found_in_user_message(self):
        self.assertTrue(evidence_supported("我负责的是检索模块", HISTORY))

    def test_punctuation_and_spacing_are_ignored(self):
        self.assertTrue(evidence_supported("我负责的是检索模块，", HISTORY))

    def test_not_found(self):
        self.assertFalse(evidence_supported("我用了 Milvus 做向量库", HISTORY))

    def test_assistant_message_does_not_count(self):
        """证据必须是**候选人**的原话，不能拿面试官的问题充当。"""
        self.assertFalse(evidence_supported("你在项目里负责什么", HISTORY))

    def test_empty_quote(self):
        self.assertFalse(evidence_supported("", HISTORY))
        self.assertFalse(evidence_supported(None, HISTORY))
        self.assertFalse(evidence_supported("我负责的是检索模块", []))

    def test_verify_evidence_all_supported(self):
        """GOOD_RAW 的四条证据都能在 HISTORY 里找到原话 → 没有维度被判失败。"""
        self.assertEqual(verify_evidence(normalize(GOOD_RAW), HISTORY), [])

    def test_verify_evidence_flags_fabricated_quote(self):
        """模型编的原话（历史里根本没有）要被点名 —— 这是复核的意义所在。"""
        raw = {"dimensions": [
            {"name": "表达与逻辑", "score": 8, "evidence": "我负责的是检索模块"},
            {"name": "专业深度", "score": 6, "evidence": "我调过 Milvus 的分片参数"},
        ]}
        self.assertEqual(verify_evidence(normalize(raw), HISTORY), ["专业深度"])

    def test_not_mentioned_is_not_a_fabrication(self):
        """⚠️ 写「未提及」的维度**不算编造**，必须跳过。

        提示词明确要求：某维度候选人完全没提到时，evidence 就写「未提及」
        （见 skills/score_report.json）。不跳过的话，一场候选人没怎么说话的面试
        会在日志里刷出四个"依据对不上"，把真正的信号淹掉 —— 这条是 P2 接线时
        才发现的（评分只在报告轮跑，而退化输入正是常见情形）。
        """
        raw = {"dimensions": [
            {"name": "表达与逻辑", "score": 3, "evidence": NOT_MENTIONED},
            {"name": "专业深度", "score": 3, "evidence": "未提及。"},   # 带标点也要认
            {"name": "项目经验", "score": 3, "evidence": ""},           # 压根没给，也不点名
        ]}
        self.assertEqual(verify_evidence(normalize(raw), HISTORY), [])

    def test_not_mentioned_constant_matches_the_prompt(self):
        """`NOT_MENTIONED` 与提示词里要求写的那句话必须一致 —— 改了这头忘了那头，
        上面那条跳过就会静默失效（评分照跑，日志刷屏如故）。"""
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "skills", "score_report.json")
        with open(path, encoding="utf-8") as fh:
            prompt = json.load(fh)["system_prompt"]
        self.assertIn(f"就写「{NOT_MENTIONED}」", prompt,
                      f"提示词里要求写的占位符与 score_guard.{NOT_MENTIONED!r} 对不上了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
