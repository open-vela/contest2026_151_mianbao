#!/usr/bin/env python3
"""`next_question` 的两道新闸（2026-10-13，台账 §11.45）—— 不联网、不花钱。

`call_llm` 被打桩，验的是**接线**：

1. **岗位关注角度**：技术追问段注入、背景深挖不注入、未知岗位优雅退化；
   且它出现在**本轮 user 消息**里 —— 要求与材料同处（§11.42 的位置纪律）。
2. **重问闸**：与上一问几乎一样时补一次纠偏重试；重试仍一样（或为空）就照发，
   不卡主链路；第一轮没有上一问，零成本。

为什么单独一个文件（而不并进 `test_question_similarity.py`）：这里要 import
`llm_service`，它模块顶层就 `import openai` —— 属 run_tests.sh「装了依赖才跑」
那一档（同 test_report_retry.py 的分档理由）。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import llm_service  # noqa: E402
import question_similarity  # noqa: E402

# 上一问 / 「原样重问」样本逐字抄自 2026-10-13 的 Data Analyst 排练（台账 §11.45）
# —— 就是触发这道闸的那一对（剥过元叙述后实测相似度 0.86）。
PREVIOUS = ("三百条金标集覆盖了商品咨询、退款、物流这几类，那线上真实提问的分布跟这个"
            "评测集对得上吗？有没有哪类问题在线上占比很高但评测集里样本很少的？")
REPEAT = ("你们评测集是三百条覆盖了商品咨询、退款、物流三类，那线上真实提问的分布跟这个"
          "评测集对得上吗？有没有哪类问题线上占比很高、但评测集里样本很少的？")
FRESH = "缓存的失效策略之外，你们有没有做过缓存预热？上线时怎么避免冷启动那一下的延迟尖峰？"


def history_for_round(round_number, previous=None):
    """造一条第 N 轮的历史：长度 2N-2（next_question 收到的**不含**本轮回答）。

    末尾固定是面试官消息 —— 重问闸要找的"上一问"就是它。
    """
    history = []
    for i in range(1, round_number):
        history.append({"role": "user", "content": f"第 {i} 轮候选人的回答"})
        history.append({"role": "assistant", "content": f"第 {i} 轮面试官的问题"})
    if previous and history:
        history[-1] = {"role": "assistant", "content": previous}
    return history


class NextQuestionTestCase(unittest.TestCase):
    def run_next(self, role, round_number, replies, previous=None):
        """跑一次 next_question，返回 (返回值, 每次调用的 kwargs 列表)。"""
        calls = []

        def fake_call_llm(**kwargs):
            calls.append(kwargs)
            return replies[min(len(calls) - 1, len(replies) - 1)]

        history = history_for_round(round_number, previous)
        with mock.patch.object(llm_service, "call_llm", side_effect=fake_call_llm):
            out = llm_service.next_question(role, history, "他这轮的回答")
        return out, calls


class TestRoleFocus(NextQuestionTestCase):
    def test_技术追问段带上岗位角度(self):
        """换岗位必须真的改变追问方向 —— 否则多岗位演示就是"换汤不换药"（§11.45）。"""
        _, calls = self.run_next("Data Analyst", 5, [FRESH])
        focus = llm_service.load_skill("next_question")["role_focus"]["Data Analyst"]
        user_message = calls[0]["messages"][-1]["content"]
        self.assertIn(focus, user_message, "技术追问段必须带上本岗位的关注角度")
        self.assertNotIn(focus, calls[0]["system_prompt"],
                         "角度是'要求'：要跟 brief 同处本轮 user 消息（§11.42 的位置纪律）")

    def test_背景深挖段不注入(self):
        """背景深挖问的是他的基本功，加岗位角度只会把话题拽窄。"""
        _, calls = self.run_next("Data Analyst", 2, [FRESH])
        focus = llm_service.load_skill("next_question")["role_focus"]["Data Analyst"]
        self.assertNotIn(focus, calls[0]["messages"][-1]["content"])

    def test_未知岗位优雅退化(self):
        """对不上就不注入、不报错 —— 同参考块的优雅退化。"""
        _, calls = self.run_next("不存在的岗位", 5, [FRESH])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("【本岗位关注的角度】", calls[0]["messages"][-1]["content"])


class TestRepeatGuard(NextQuestionTestCase):
    def test_原样重问触发一次重试(self):
        out, calls = self.run_next("AI 应用开发", 9, [REPEAT, FRESH], previous=PREVIOUS)
        self.assertEqual(len(calls), 2, "与上一问几乎一样时必须补一次纠偏重试")
        self.assertEqual(out["text"], FRESH, "应当采用重试后那一问")

    def test_正常轮次零成本(self):
        out, calls = self.run_next("AI 应用开发", 9, [FRESH], previous=PREVIOUS)
        self.assertEqual(len(calls), 1, "不重复就不该多花一次调用")
        self.assertEqual(out["text"], FRESH)

    def test_重试请求带着原问题与纠偏指令(self):
        """重试那一轮必须把原问题和纠偏指令一起带上，否则模型不知道要改什么
        —— 同 test_report_retry 的同名判据。"""
        _, calls = self.run_next("AI 应用开发", 9, [REPEAT, FRESH], previous=PREVIOUS)
        retry_messages = calls[1]["messages"]
        self.assertEqual(retry_messages[0]["content"], calls[0]["messages"][0]["content"],
                         "重试的上下文必须与原请求一致（同一历史），只多出尾部两条")
        self.assertEqual(retry_messages[-2], {"role": "assistant", "content": REPEAT})
        self.assertEqual(retry_messages[-1]["content"], question_similarity.RETRY_HINT)
        self.assertEqual(calls[1]["system_prompt"], calls[0]["system_prompt"])

    def test_重试仍重问就照发(self):
        """宁可要一句稍重的追问，也不要让这一轮空掉（同 report_guard 的取舍）。"""
        out, calls = self.run_next("AI 应用开发", 9, [REPEAT, REPEAT], previous=PREVIOUS)
        self.assertEqual(len(calls), 2, "只重试一次，不无限重试")
        self.assertEqual(out["text"], REPEAT)

    def test_重试返回空也用原问(self):
        out, calls = self.run_next("AI 应用开发", 9, [REPEAT, ""], previous=PREVIOUS)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out["text"], REPEAT)

    def test_第一轮没有上一问不触发(self):
        out, calls = self.run_next("AI 应用开发", 1, [FRESH])
        self.assertEqual(len(calls), 1)
        self.assertEqual(out["text"], FRESH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
