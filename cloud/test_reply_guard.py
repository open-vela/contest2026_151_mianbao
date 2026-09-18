#!/usr/bin/env python3
"""reply_guard 单元测试 —— 不联网、不需要 key：`python3 test_reply_guard.py`。

样本全部来自**真实跑出来的脏输出**（9/18 A/B 的 P 组，输入是 §11.20 那条被污染的
历史），不是手编的理想样例 —— 手编的样例测不出"模型实际会写成什么样"。
"""
import unittest

from reply_guard import FALLBACK_QUESTION, clean_history, strip_meta

# ---- 真实脏输出（9/18 A/B `--group P` 抓到的，逐字抄自输出文件）----

# 214 字那条：判断 + 分隔线 + 理由 + 分隔线 + 追问
DIRTY_FULL = (
    "判断：追问细节\n\n---\n\n理由：\n\n候选人的回答过于简略，只给出了一个概括性的"
    "回答，没有具体说明负责的产品线和取得的成果。\n\n---\n\n追问：您在企业服务公司"
    "这五年，主要负责哪条产品线？能举一个您主导的产品例子吗？"
)

# 51 字那条：只有一个"追问细节："引子
DIRTY_LABEL_ONLY = "追问细节：\n\n您提到在企业服务公司做了五年产品经理，能具体说说您负责的产品是什么吗？"

# 全是元叙述、一个问题都没有
DIRTY_NO_QUESTION = "判断：追问细节\n\n---\n\n理由：\n\n候选人的回答非常简短且缺乏细节。"

# 211 字那条（2026-09-18 从真实链路抓的原始输出，逐字录入）：
# 判断块 + 理由块 + 「新问题：」+ Markdown 引用块 + 「下一步：」。
# 它同时考验标签剥离、引用块去壳，以及"两句相关问话要一起留下"。
DIRTY_WITH_NEXT_STEP = (
    "判断：追问细节\n\n---\n\n理由：\n\n候选人的回答非常简短，只提到了\"做产品经理五年\""
    "和\"企业服务公司\"，但没有提供任何具体信息。我需要追问，让他补充更多细节。\n\n---\n\n"
    "新问题：\n\n> 您提到在企业服务公司做了五年产品经理，能具体说说您负责的是什么产品吗？"
    "在这个过程中，您主导过哪些比较有挑战性的项目？\n\n---\n\n下一步：\n\n"
    "等待候选人回复后，根据其回答深度决定是继续追问还是进入下一个话题。"
)

DIRTY_WITH_NEXT_STEP_EXPECTED = (
    "您提到在企业服务公司做了五年产品经理，能具体说说您负责的是什么产品吗？"
    "在这个过程中，您主导过哪些比较有挑战性的项目？"
)


class TestCleanTextIsUntouched(unittest.TestCase):
    """干净文本零改动 —— 这条最关键：闸门不能去动正常回复的语气。"""

    def test_single_question(self):
        text = "您提到的这个项目挺有意思，能具体说说您在其中的角色，以及遇到的最大挑战吗？"
        self.assertEqual(strip_meta(text), text)

    def test_multi_sentence_with_lead_in(self):
        text = "好的，那我们换个话题。你刚才提到向量检索，能说说召回效果是怎么评估的吗？"
        self.assertEqual(strip_meta(text), text)

    def test_no_question_mark(self):
        text = "请简单介绍一下你自己。"
        self.assertEqual(strip_meta(text), text)

    def test_english_question(self):
        text = "Can you walk me through your RAG pipeline?"
        self.assertEqual(strip_meta(text), text)


class TestDirtyOutputIsCleaned(unittest.TestCase):
    def test_full_meta_block_keeps_only_question(self):
        out = strip_meta(DIRTY_FULL)
        self.assertEqual(out, "您在企业服务公司这五年，主要负责哪条产品线？"
                              "能举一个您主导的产品例子吗？")
        self.assertTrue(out.endswith("？"))

    def test_reasoning_paragraph_without_label_is_dropped(self):
        """真实脏输出的"理由"正文是**独立一段**、没有标签，靠"不含问句的块不念"丢掉。"""
        out = strip_meta(DIRTY_FULL)
        self.assertNotIn("过于简略", out)
        self.assertNotIn("成果", out)

    def test_two_questions_are_not_truncated(self):
        """不做句子级截断：两句相关的问话要一起留下（砍掉前半句会失去所指）。"""
        dirty = "判断：追问细节\n\n---\n\n追问：您提到按标题切分，那跨章节的内容怎么办？做过对比实验吗？"
        out = strip_meta(dirty)
        self.assertEqual(out, "您提到按标题切分，那跨章节的内容怎么办？做过对比实验吗？")

    def test_label_only_prefix(self):
        out = strip_meta(DIRTY_LABEL_ONLY)
        self.assertEqual(out, "您提到在企业服务公司做了五年产品经理，能具体说说您负责的产品是什么吗？")

    def test_all_meta_yields_empty(self):
        self.assertEqual(strip_meta(DIRTY_NO_QUESTION), "")

    def test_real_output_with_next_step_section(self):
        """211 字的真实原始输出 → 58 字可念的问句（「下一步」「理由」那些全不念）。"""
        out = strip_meta(DIRTY_WITH_NEXT_STEP)
        self.assertEqual(out, DIRTY_WITH_NEXT_STEP_EXPECTED)
        self.assertLessEqual(len(out), 60)
        self.assertNotIn("下一步", out)
        self.assertNotIn("等待候选人回复", out)

    def test_no_markdown_survives(self):
        """脏输出清理后不许留下 Markdown 痕迹（它会被逐字念出来）。"""
        for dirty in (DIRTY_FULL, DIRTY_LABEL_ONLY, DIRTY_NO_QUESTION):
            out = strip_meta(dirty)
            for token in ("**", "---", "|", "#", ">"):
                self.assertNotIn(token, out, f"{token!r} 残留在 {out!r}")

    def test_bold_label_line(self):
        out = strip_meta("**总体评价**：候选人表现一般。\n\n**建议**：多准备项目细节。")
        self.assertNotIn("**", out)

    def test_markdown_table_is_dropped(self):
        dirty = "判断：提出新问题\n\n| 维度 | 评价 |\n| --- | --- |\n| 逻辑 | 一般 |\n\n新问题：能说说你的 RAG 方案吗？"
        out = strip_meta(dirty)
        self.assertNotIn("|", out)
        self.assertEqual(out, "能说说你的 RAG 方案吗？")

    def test_question_on_same_line_as_label(self):
        out = strip_meta("判断：需要追问 你刚才提到按标题切分，能说说跨章节的内容怎么办吗？")
        self.assertTrue(out.endswith("？"))
        self.assertNotIn("判断", out)


class TestInvariants(unittest.TestCase):
    """不变量：幂等、确定性、空输入安全。"""

    def test_idempotent(self):
        for text in (DIRTY_FULL, DIRTY_LABEL_ONLY, DIRTY_NO_QUESTION, "干净的问句？", ""):
            once = strip_meta(text)
            self.assertEqual(strip_meta(once), once)

    def test_deterministic(self):
        outs = {strip_meta(DIRTY_FULL) for _ in range(20)}
        self.assertEqual(len(outs), 1)

    def test_empty_and_whitespace(self):
        for text in ("", "   ", "\n\n", None):
            self.assertEqual(strip_meta(text or ""), "")

    def test_fallback_question_is_usable(self):
        self.assertTrue(FALLBACK_QUESTION.endswith("？"))
        self.assertEqual(strip_meta(FALLBACK_QUESTION), FALLBACK_QUESTION)
        self.assertLessEqual(len(FALLBACK_QUESTION), 40)


class TestCleanHistory(unittest.TestCase):
    def test_assistant_messages_cleaned_user_untouched(self):
        raw = [
            {"role": "user", "content": "喂喂，你好。"},
            {"role": "assistant", "content": DIRTY_FULL},
        ]
        out = clean_history(raw)
        self.assertEqual(out[0], raw[0])
        self.assertNotIn("判断", out[1]["content"])
        self.assertTrue(out[1]["content"].endswith("？"))

    def test_fully_meta_message_is_dropped(self):
        raw = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": DIRTY_NO_QUESTION},
            {"role": "user", "content": "我说完了"},
        ]
        out = clean_history(raw)
        self.assertEqual([m["role"] for m in out], ["user", "user"])

    def test_clean_history_is_unchanged(self):
        raw = [
            {"role": "assistant", "content": "能具体说说您在其中的角色吗？"},
            {"role": "user", "content": "我负责检索模块。"},
        ]
        self.assertEqual(clean_history(raw), raw)

    def test_empty_and_none(self):
        self.assertEqual(clean_history([]), [])
        self.assertEqual(clean_history(None), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
