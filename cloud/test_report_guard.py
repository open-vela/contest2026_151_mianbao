#!/usr/bin/env python3
"""report_guard 单元测试 —— 不联网、不需要 key：`python3 test_report_guard.py`。

样本取法沿用 `test_reply_guard.py` 的规矩：**报告样本逐字抄自真实输出**，
不是手编的。

* `REAL_NO_QUOTE` 是 2026-09-30 真机那一轮的报告原文（台账 §11.27）——
  候选人三句只说了 6/2/5 个字，报告四个维度全"未涉及"，「」引用一个也没有。
  这就是这道闸要拦的东西。
* `REAL_WITH_QUOTE` 是按提示词要求写的一份对照样本（含「」引用且引用真实存在）。
"""
import ast
import os
import unittest

import report_guard as rg

# ---- 逐字抄自 2026-09-30 真机那一轮（台账 §11.27）----
REAL_NO_QUOTE = (
    "候选人整体表现极差，未能完成任何有效沟通。技术正确性未涉及。"
    "深度与原理未涉及。工程与场景思考未涉及。表达与结构未涉及。"
    "建议先补充有效回答。"
)

# ---- 对照样本：同样六句结构，但按提示词要求引用了原话 ----
REAL_WITH_QUOTE = (
    "整体表达清晰。技术正确性上，你提到「召回率提升到92%」有具体数字。"
    "深度与原理未涉及。工程与场景思考未涉及。表达与结构尚可。"
    "建议补充更多量化细节。"
)

# 真机那一轮的候选人发言（history 里的 user 消息）
HISTORY = [
    {"role": "assistant", "content": "请介绍一下你自己。"},
    {"role": "user", "content": "你好。"},
    {"role": "assistant", "content": "能具体说说吗？"},
    {"role": "user", "content": "嗯。"},
    {"role": "assistant", "content": "那我们换个问题。"},
    {"role": "user", "content": "结束面试。"},
]

HISTORY_WITH_NUMBERS = [
    {"role": "user", "content": "我用向量数据库做检索，召回率提升到 92%。"},
]


class TestQuotedSpans(unittest.TestCase):
    def test_none_and_empty(self):
        """闸门会被喂进各种形状，别在 None 上炸。"""
        for bad in (None, "", 42, [], {}):
            with self.subTest(value=bad):
                self.assertEqual(rg.quoted_spans(bad), [])

    def test_single(self):
        self.assertEqual(rg.quoted_spans("你提到「召回率提升到92%」，不错。"),
                         ["召回率提升到92%"])

    def test_multiple_keeps_order(self):
        self.assertEqual(rg.quoted_spans("先说「甲」，再说「乙」。"), ["甲", "乙"])

    def test_empty_quote_is_not_a_quote(self):
        """`「」` 是空引用，不能算数 —— 否则模型写一对空括号就能骗过闸门。"""
        self.assertEqual(rg.quoted_spans("他说了「」，等于没说。"), [])
        self.assertFalse(rg.has_quote("他说了「」，等于没说。"))

    def test_only_existing_pairs(self):
        """落单的「 不该把后面的整段都吞进去。"""
        self.assertEqual(rg.quoted_spans("他说「这个没有闭合"), [])
        self.assertTrue(rg.has_quote("他说「闭合了」。"))

    def test_too_long_is_not_matched(self):
        """超过 40 字的引号内容不当作「引用」—— 闸门只回答"有没有"，长度是提示词的事。"""
        self.assertEqual(rg.quoted_spans("「" + "字" * 41 + "」"), [])
        self.assertTrue(rg.has_quote("「" + "字" * 40 + "」"))


class TestHasQuoteOnRealSamples(unittest.TestCase):
    def test_the_real_failing_report(self):
        """真机那份报告 —— 这道闸存在的唯一理由。"""
        self.assertFalse(rg.has_quote(REAL_NO_QUOTE),
                         "这份报告里确实没有「」引用，闸门必须判为不合格")

    def test_the_conforming_report(self):
        self.assertTrue(rg.has_quote(REAL_WITH_QUOTE))


class TestQuoteEvidence(unittest.TestCase):
    def test_good_quote_is_found(self):
        self.assertEqual(rg.check_quote_evidence(REAL_WITH_QUOTE, HISTORY_WITH_NUMBERS), [])

    def test_fabricated_quote_is_flagged(self):
        """模型编出来的"原话"要能被认出来（只记日志，不拦）。"""
        fake = REAL_WITH_QUOTE.replace("召回率提升到92%", "我负责了整个推荐系统")
        self.assertEqual(rg.check_quote_evidence(fake, HISTORY_WITH_NUMBERS),
                         ["我负责了整个推荐系统"])

    def test_punctuation_and_space_differences_do_not_matter(self):
        """语音转写的标点不可信：压掉标点后能对上就算对上。"""
        report = "你提到「召回率提升到 92%」，有数字。"
        self.assertEqual(rg.check_quote_evidence(report, HISTORY_WITH_NUMBERS), [])

    def test_keyword_concatenation_is_reported_as_unmatched(self):
        """⚠️ 已知行为，不是缺陷：提示词允许"摘关键词连起来"，那是**拼接**而非
        连续原文，这里会判成对不上。所以调用方只该记日志、不能拿它拦。"""
        report = "你提到「向量数据库 召回率」，说得挺具体。"
        self.assertEqual(rg.check_quote_evidence(report, HISTORY_WITH_NUMBERS),
                         ["向量数据库 召回率"])

    def test_no_quote_no_evidence_problem(self):
        self.assertEqual(rg.check_quote_evidence(REAL_NO_QUOTE, HISTORY), [])

    def test_empty_history_and_bad_history(self):
        for bad in (None, [], "字符串", [None, 42, {"no": "role"}]):
            with self.subTest(history=bad):
                self.assertEqual(rg.check_quote_evidence(REAL_WITH_QUOTE, bad),
                                 ["召回率提升到92%"])

    def test_only_user_messages_count(self):
        """面试官自己说过的话不算"候选人的原话"。"""
        history = [{"role": "assistant", "content": "召回率提升到92%"}]
        self.assertEqual(rg.check_quote_evidence(REAL_WITH_QUOTE, history),
                         ["召回率提升到92%"])


class TestPureFunctionProperties(unittest.TestCase):
    def test_deterministic(self):
        for _ in range(20):
            self.assertEqual(rg.quoted_spans(REAL_WITH_QUOTE), ["召回率提升到92%"])
            self.assertEqual(rg.check_quote_evidence(REAL_WITH_QUOTE, HISTORY_WITH_NUMBERS), [])

    def test_does_not_mutate_history(self):
        import copy
        before = copy.deepcopy(HISTORY_WITH_NUMBERS)
        rg.check_quote_evidence(REAL_WITH_QUOTE, HISTORY_WITH_NUMBERS)
        self.assertEqual(HISTORY_WITH_NUMBERS, before)


class TestStdlibOnly(unittest.TestCase):
    """同 test_question_bank.py 的护栏：这个模块要能脱网、不装依赖地单测。"""

    ALLOWED = {"re"}

    def test_imports_are_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_guard.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= self.ALLOWED,
                        f"report_guard 只该 import {self.ALLOWED}，实际 {imported}")


class TestProblems(unittest.TestCase):
    """报告合格判据。目前两项：有「」引用、不超长。"""

    def test_合格的报告没有问题(self):
        self.assertEqual(rg.problems(REAL_WITH_QUOTE), [])

    def test_缺引用(self):
        self.assertEqual(rg.problems(REAL_NO_QUOTE), ["no_quote"])

    def test_超长(self):
        long_report = "整体尚可。「好」，但" + "这里还有一句补充说明。" * 30
        self.assertIn("too_long", rg.problems(long_report))
        self.assertEqual(rg.problems(long_report), ["too_long"],
                         "这份样本有引用，只该判超长")

    def test_两种都不合格(self):
        long_no_quote = REAL_NO_QUOTE + "另外我还想补充几点。" * 30
        self.assertEqual(rg.problems(long_no_quote), ["no_quote", "too_long"])

    def test_刚好到上限不算超(self):
        """边界：**刚好到上限合格，多一个字就动手**。

        补白长度由前缀长度算出来，别写死 —— 我第一版手算错了 3 个字
        （`「引」` 是 3 个字不是 2 个），测试当场把我抓住。
        """
        prefix = "「引」"
        exact = prefix + "字" * (rg.MAX_CHARS - len(prefix))
        self.assertEqual(len(exact.strip()), rg.MAX_CHARS, "构造的样本长度不对")

        self.assertEqual(rg.problems(exact), [], "刚好到上限不该判超长")
        self.assertEqual(rg.problems(exact + "字"), ["too_long"], "多一个字就该动手")

    def test_空与None(self):
        for bad in ("", None, "   "):
            with self.subTest(report=bad):
                self.assertEqual(rg.problems(bad), ["no_quote"])


class TestRetryHint(unittest.TestCase):
    """按不合格的项拼纠偏指令 —— **一次重试里把所有问题一起说**，不叠加调用。"""

    def test_没有问题时不拼东西(self):
        self.assertEqual(rg.retry_hint([]), "")
        self.assertEqual(rg.retry_hint(None), "")

    def test_缺引用时给引用那条(self):
        self.assertEqual(rg.retry_hint(["no_quote"]), rg.RETRY_HINT)

    def test_超长时给长度那条(self):
        self.assertEqual(rg.retry_hint(["too_long"]), rg.RETRY_HINT_TOO_LONG)

    def test_两种都有时两条都给(self):
        hint = rg.retry_hint(["no_quote", "too_long"])
        self.assertIn("「」引用", hint)
        self.assertIn("太长", hint)

    def test_上限与rehearsal保持一致(self):
        """⚠️ 两处阈值必须一样，否则会出现"闸门觉得合格、排练判不及格"这种自相矛盾。"""
        import re
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rehearsal.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        found = re.search(r"^MAX_REPORT_CHARS\s*=\s*(\d+)", source, re.M)
        self.assertIsNotNone(found, "rehearsal.py 里没找到 MAX_REPORT_CHARS")
        self.assertEqual(rg.MAX_CHARS, int(found.group(1)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
