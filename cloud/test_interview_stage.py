#!/usr/bin/env python3
"""面试节奏（第几轮走哪一段）—— 纯标准库、不联网、不花钱。

为什么这块值得单测：它是整场面试的**骨架**，而骨架出错是**静默**的 ——
轮次算错一轮，表现只是"某一段少问了一个问题"，不报错、不失败、没人发现。
所以把段表钉死在这里。

另外做一条**代码 ↔ 提示词的双向核对**：代码里的段名必须在
`skills/next_question.json` 的 `stages` 里有对应文本（对不上时提示词只会静默退化成
"没有阶段"，面试照跑、节奏没了）；反过来，提示词里写了而代码用不到的段，也是漂移。
"""
import json
import os
import re
import unittest

import interview_stage


class TestStagePlan(unittest.TestCase):
    def test_每一轮都有确定的段(self):
        """1~10 轮逐轮钉死。改了段表就要同步改这里 —— 那是故意的。"""
        expected = {
            1: "opening",
            2: "background", 3: "background",
            4: "technical", 5: "technical", 6: "technical",
            7: "technical", 8: "technical", 9: "technical",
            10: "ask_back",
        }
        for round_number, key in expected.items():
            with self.subTest(round=round_number):
                self.assertEqual(interview_stage.stage_key(round_number), key)

    def test_第11轮没有段(self):
        """第 11 轮的回复是**报告** —— 结束判据在那之前就把它分流了，
        `next_question` 根本不会被调用。所以这里查不到是正常的，不是漏了。"""
        self.assertIsNone(interview_stage.stage_key(11))
        self.assertIsNone(interview_stage.stage_key(20))

    def test_段表连续无空洞无重叠(self):
        """段表必须严丝合缝覆盖 1~10 —— 中间漏一轮，那一轮就会静默地没有阶段。"""
        covered = []
        for _, first, last in interview_stage.STAGE_PLAN:
            self.assertLessEqual(first, last)
            covered.extend(range(first, last + 1))
        self.assertEqual(sorted(covered), list(range(1, interview_stage.TOTAL_ROUNDS)))

    def test_轮数与结束判据对得上(self):
        """⚠️ 这两个数字是绑在一起的：`HISTORY_FINISH_THRESHOLD` 是 20 条消息
        = 10 个问答对，所以第 11 轮才是报告。改一个不改另一个，面试要么在还差一段时
        被掐掉，要么多问一轮"没有阶段"的问题。

        这里**直接读源码取那个常量**，而不是 `import llm_service` —— 那会把 openai
        拖进来，把本文件从"零依赖"那一档赶到"装依赖才跑"那一档。
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_service.py")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        found = re.search(r"^HISTORY_FINISH_THRESHOLD\s*=\s*(\d+)", source, re.M)
        self.assertIsNotNone(found, "llm_service.py 里没找到 HISTORY_FINISH_THRESHOLD")
        self.assertEqual(int(found.group(1)),
                         2 * (interview_stage.TOTAL_ROUNDS - 1))

    def test_坏输入不炸(self):
        """它跑在面试主链路上 —— 一个坏的轮次不该让整场面试变成 500。"""
        for bad in (0, -1, None, "2", 1.5, True, [], {}):
            with self.subTest(round=bad):
                self.assertIsNone(interview_stage.stage_key(bad))


class TestQuestionBankUsage(unittest.TestCase):
    def test_只有技术问答那一段用题库(self):
        """背景深挖问的是他自己的项目，题库帮不上忙；注进去只会把话题从他自己的
        经历上拽走（顺带每轮省下两百多字提示词）。"""
        for key, _, _ in interview_stage.STAGE_PLAN:
            with self.subTest(stage=key):
                self.assertEqual(interview_stage.uses_question_bank(key),
                                 key == "technical")

    def test_未知段名不用题库(self):
        for bad in (None, "", "不存在", 42):
            with self.subTest(stage=bad):
                self.assertFalse(interview_stage.uses_question_bank(bad))


class TestPlanMatchesThePrompt(unittest.TestCase):
    """代码里的段名 ↔ 提示词里的段文本，必须一一对上。"""

    def setUp(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "skills", "next_question.json")
        with open(path, encoding="utf-8") as fh:
            self.skill = json.load(fh)

    def test_每一段在提示词里都有文本(self):
        stages = self.skill.get("stages") or {}
        for key, _, _ in interview_stage.STAGE_PLAN:
            with self.subTest(stage=key):
                self.assertIn(key, stages, f"skills/next_question.json 里缺 {key} 这一段")
                self.assertTrue(stages[key].get("name", "").strip(), f"{key} 缺中文段名")
                self.assertTrue(stages[key].get("instruction", "").strip(),
                                f"{key} 缺 instruction —— 提示词会静默退化成没有阶段")

    def test_每一段都有_brief(self):
        """`brief` 是追加在**本轮 user 消息最后**的那一句（离"下一句要写什么"最近的位置）。

        ⚠️ 只写在 system prompt 中段挡不住历史势头 —— 2026-10-01 的排练里，模型在
        技术段和反问段都继续追项目细节。brief 存在的全部理由就是占住那个位置。
        """
        stages = self.skill.get("stages") or {}
        for key, _, _ in interview_stage.STAGE_PLAN:
            with self.subTest(stage=key):
                self.assertTrue(stages.get(key, {}).get("brief", "").strip(),
                                f"{key} 缺 brief —— 阶段提示就只剩 system prompt 里那句了")

    def test_提示词里没有多余的段(self):
        stages = set((self.skill.get("stages") or {}).keys())
        self.assertEqual(stages, {key for key, _, _ in interview_stage.STAGE_PLAN})

    def test_硬性要求仍在提示词末尾(self):
        """⚠️ §11.20 的修复靠的就是这一段留在结尾（recency）。加阶段时很容易
        顺手把它挤走 —— 挤走了话痨会复发，而且是"下一次长会话才发作"的那种。"""
        prompt = self.skill["system_prompt"]
        self.assertIn("{stage_block}", prompt, "占位符不在，阶段注入不进去")
        self.assertIn("{reference_block}", prompt)
        self.assertTrue(prompt.rstrip().endswith("正确示例：您提到的这个项目挺有意思，"
                                                "能具体说说您在其中的角色，以及遇到的最大挑战吗？"),
                        "【硬性要求】那段不在结尾了 —— 见台账 §11.20")
        self.assertLess(prompt.index("【面试纪律】"), prompt.index("{stage_block}"),
                        "阶段块应当排在【面试纪律】之后")


class TestAskBackGuard(unittest.TestCase):
    """反问环节的代码兜底 —— 判据故意宽，见 `interview_stage.is_ask_back`。"""

    def test_认出常见的反问说法(self):
        for text in ("您有什么想问我的吗？",
                     "有没有想问我的？",
                     "我的问题问完了，你还有什么想问的吗？"):
            with self.subTest(text=text):
                self.assertTrue(interview_stage.is_ask_back(text))

    def test_不是请对方提问的(self):
        for text in ("", None, [], "那你们线上有没有做监控？", "能具体说说缓存失效吗？"):
            with self.subTest(text=text):
                self.assertFalse(interview_stage.is_ask_back(text))

    def test_兜底问句自己得能过判据(self):
        """不然就是逻辑自相矛盾：替换完仍然"不合格"。"""
        self.assertTrue(interview_stage.is_ask_back(interview_stage.ASK_BACK_FALLBACK))


if __name__ == "__main__":
    unittest.main(verbosity=2)
