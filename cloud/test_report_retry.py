#!/usr/bin/env python3
"""`generate_feedback` 的「」引用兜底重试 —— **不联网、不花钱**。

`call_llm` 被打桩，所以这里既不碰小米 MIMO、也不需要 key。它验的是**接线**：
报告缺「」引用时会不会补一次纠偏重试、重试仍失败时会不会照发原文而不是丢弃。

为什么单独一个文件（而不是并进 `test_report_guard.py`）：guard 本身是纯标准库的
纯函数，属"零依赖"那一档；而这里要 import `llm_service`，它模块顶层就 `import
openai` —— 两档的判据不同（见 `run_tests.sh` 的分档说明），所以分开放。

⚠️ 需要 requirements.txt 里的 openai；没装时 run_tests.sh 会**大声跳过**这个文件。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import llm_service   # noqa: E402

# 逐字抄自 2026-09-30 真机那一轮（台账 §11.27）：候选人只说了几个字，
# 报告四个维度全"未涉及"，「」引用一个也没有 —— 这就是触发重试的输入。
NO_QUOTE = (
    "候选人整体表现极差，未能完成任何有效沟通。技术正确性未涉及。"
    "深度与原理未涉及。工程与场景思考未涉及。表达与结构未涉及。"
    "建议先补充有效回答。"
)
WITH_QUOTE = (
    "整体表达清晰。技术正确性上，你提到「结束面试」这几个字。"
    "专业深度未涉及。工程与场景思考未涉及。表达与结构未涉及。"
    "建议下次多讲几句。"
)

HISTORY = [
    {"role": "assistant", "content": "请介绍一下你自己。"},
    {"role": "user", "content": "你好。"},
    {"role": "assistant", "content": "能具体说说吗？"},
    {"role": "user", "content": "结束面试。"},
]


class RetryTestCase(unittest.TestCase):
    def run_feedback(self, replies):
        """跑一次 generate_feedback，返回 (返回值, 每次调用的 kwargs 列表)。"""
        calls = []

        def fake_call_llm(**kwargs):
            calls.append(kwargs)
            return replies[min(len(calls) - 1, len(replies) - 1)]

        with mock.patch.object(llm_service, "call_llm", side_effect=fake_call_llm):
            out = llm_service.generate_feedback("AI 应用开发", list(HISTORY))
        return out, calls


class TestQuoteRetry(RetryTestCase):
    def test_retries_once_when_quote_missing(self):
        out, calls = self.run_feedback([NO_QUOTE, WITH_QUOTE])
        self.assertEqual(len(calls), 2, "缺「」引用时必须补一次重试")
        self.assertEqual(out["text"], WITH_QUOTE, "应当采用重试后那份")
        self.assertEqual(out["next_action"], "finish")

    def test_no_retry_when_quote_present(self):
        """正常轮次零成本 —— 这条是"只在缺的时候才多花一次调用"的守卫。"""
        out, calls = self.run_feedback([WITH_QUOTE])
        self.assertEqual(len(calls), 1, "已经有了「」引用，不该重试")
        self.assertEqual(out["text"], WITH_QUOTE)

    def test_retry_hint_is_actually_sent(self):
        """重试那一轮必须把原回复和纠偏指令一起带上，否则模型不知道要改什么。"""
        _, calls = self.run_feedback([NO_QUOTE, WITH_QUOTE])
        retry_messages = calls[1]["messages"]
        self.assertEqual(retry_messages[0]["content"], calls[0]["messages"][0]["content"])
        self.assertEqual(retry_messages[-2], {"role": "assistant", "content": NO_QUOTE})
        self.assertEqual(retry_messages[-1]["content"], llm_service.report_guard.RETRY_HINT)

    def test_keeps_original_when_retry_also_fails(self):
        """重试仍不合格 → **照发原文**，不丢弃、也不机械拼一句引用上去。"""
        out, calls = self.run_feedback([NO_QUOTE])
        self.assertEqual(len(calls), 2, "只重试一次，不无限重试")
        self.assertEqual(out["text"], NO_QUOTE, "宁可缺引用，也不要把好内容丢掉")
        self.assertEqual(out["next_action"], "finish")

    def test_empty_llm_result_returns_fallback(self):
        """两次都空（LLM 调不通）→ 走原有的兜底文案。"""
        out, _ = self.run_feedback([""])
        self.assertEqual(out["text"], "生成报告失败")
        self.assertEqual(out["next_action"], "finish")


class TestSystemPromptIsUsed(RetryTestCase):
    def test_prompt_comes_from_skill_file(self):
        """用的是 skills/generate_feedback.json 里的提示词，不是硬编码。"""
        out, calls = self.run_feedback([WITH_QUOTE])
        skill = llm_service.load_skill("generate_feedback")
        self.assertTrue(skill.get("system_prompt"), "读不到提示词（skills/ 是否随代码拷过来了）")
        self.assertEqual(calls[0]["system_prompt"],
                         skill["system_prompt"].replace("{role}", "AI 应用开发"))

    def test_prompt_covers_the_degenerate_case(self):
        """提示词里必须留着那条专门覆盖退化情形的说明 —— 它正是这次修复的根因所在：
        四个维度全「未涉及」时，"评价要落到他说过的话上"与"未涉及"自相矛盾，
        模型于是把引用一起丢了。删掉这句，问题会回来。"""
        prompt = llm_service.load_skill("generate_feedback")["system_prompt"]
        self.assertIn("未涉及", prompt)
        self.assertIn("照样要引用", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
