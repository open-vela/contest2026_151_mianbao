#!/usr/bin/env python3
"""finish_guard 单元测试 —— 不联网、不需要 key：`python3 test_finish_guard.py`。

分两类样本，**第二类才是重点**：

* 「该结束的」—— 真实会说的收尾话，包括带礼貌外壳的；
* 「不该结束的」—— 技术回答里合法出现的「结束/没问题/没了」。误判的代价是
  面试被莫名打断，所以这一类的每一条都是按"候选人在回答技术问题"的场景写的，
  不是随手编的反例。
"""
import unittest

from finish_guard import (
    MAX_LEN,
    _FINISH_PHRASES,
    is_finish_request,
    match_reason,
    normalize,
)


class TestWhitelistIsNormalized(unittest.TestCase):
    """白名单里的条目必须**已经是归一化形式** —— 否则是永远匹配不上的死条目。

    这不是假想的风险：初版就把英文写成了 `I'm done`，而 `normalize()` 会把空格
    和撇号全部剥掉（变成 `imdone`），于是那条永远不可能命中 —— 而且没有任何
    测试会失败，功能只是"某天有人说了却没用"。
    """

    def test_every_phrase_is_already_normalized(self):
        for phrase in _FINISH_PHRASES:
            self.assertEqual(normalize(phrase), phrase,
                             f"白名单条目 {phrase!r} 不是归一化形式，永远匹配不上")

    def test_no_phrase_exceeds_length_gate(self):
        """长度闸不能把合法条目挡死：白名单里最长的一条也得 ≤ MAX_LEN。"""
        longest = max(len(p) for p in _FINISH_PHRASES)
        self.assertLessEqual(longest, MAX_LEN,
                             f"最长白名单条目 {longest} 字 > MAX_LEN={MAX_LEN}，该条已失效")

    def test_phrases_are_lowercase(self):
        for phrase in _FINISH_PHRASES:
            self.assertEqual(phrase, phrase.lower(), f"{phrase!r} 含大写字母")


class TestShouldFinish(unittest.TestCase):
    def test_direct(self):
        for text in ("结束", "结束吧", "结束了", "结束面试", "到此为止",
                     "就到这儿吧", "没有别的问题了", "我问完了"):
            with self.subTest(text=text):
                self.assertTrue(is_finish_request(text), f"{text!r} 应当判定为结束")

    def test_with_polite_shell(self):
        """真实收尾话几乎都带礼貌外壳 —— 剥壳是必须的，不是锦上添花。"""
        for text in (
            "好的，我没什么问题了，谢谢老师",
            "嗯，那结束吧",
            "那结束吧",
            "谢谢老师，我没有其他问题了。",
            "好的，结束吧，谢谢您",
            # 英文致谢走的是同一套剥壳规则，同样必须是归一化形式
            "That's all, thank you.",
            "结束吧，thanks",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_finish_request(text), f"{text!r} 应当判定为结束")

    def test_full_width_and_case(self):
        for text in ("结束吧！", "结束吧。", "That's all.", "I'm done", "STOP"):
            with self.subTest(text=text):
                self.assertTrue(is_finish_request(text), f"{text!r} 应当判定为结束")

    def test_keeps_we_not_supported(self):
        """`那我们就到这儿吧` **不**判定为结束：剥壳只剥语气词，不剥"我们"。

        如实记录这个已知的漏判 —— 它属于"宁可漏判"那一侧：候选人多按一次 K1
        就好，而为了多认出这一句去放宽剥壳规则，会把"我们就到这里吧，这个问题
        先跳过"之类的话也算成结束。要支持它就往白名单加一条精确条目。
        """
        self.assertFalse(is_finish_request("那我们就到这儿吧"))

    def test_match_reason_returns_hit_phrase(self):
        """命中时要能说出命中了哪条 —— 误判排查全靠它。"""
        self.assertEqual(match_reason("结束吧"), "结束吧")
        self.assertEqual(match_reason("我们要结束吧"), "")   # 不精确，不命中


class TestShouldNotFinish(unittest.TestCase):
    """真正重要的那一类：技术回答里的"结束""没问题""没了" **不能**结束面试。"""

    def test_technical_answer_containing_finish_word(self):
        for text in (
            "循环结束的时候会释放资源",
            "这个模块的结束条件我写在析构函数里了",
            "我们在会话结束时把状态落盘",
            "结束时间是晚上六点",
            "我上一份工作结束是因为公司裁员",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_finish_request(text), f"{text!r} 不该判定为结束")

    def test_ambiguous_short_answers(self):
        """含义模糊的一律不判 —— 这几条都能是合法回答，见模块文档。"""
        for text in ("没问题", "可以了", "就这样吧", "没了", "没有了", "行", "好"):
            with self.subTest(text=text):
                self.assertFalse(is_finish_request(text), f"{text!r} 含义模糊，不该判结束")

    def test_question_is_not_a_request(self):
        """带问号的是提问 —— 闸 3。特别是"结束了吗"。"""
        for text in ("结束了吗？", "我们结束了吗？", "结束吧？", "Is it done?"):
            with self.subTest(text=text):
                self.assertFalse(is_finish_request(text), f"{text!r} 是问句，不该判结束")

    def test_negated_or_qualified(self):
        for text in (
            "先别结束，我还想补充一点",
            "我不想结束这个项目",
            "结束之前我想说明一下背景",
            "不好意思我还没说完",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_finish_request(text), f"{text!r} 不该判定为结束")

    def test_long_answer_containing_whitelist_phrase(self):
        """整句精确匹配的意义：含白名单短语的长回答必须落空。"""
        text = "这个流程我认为没有问题了我的意思是它已经跑通了所以可以进入下一阶段"
        self.assertFalse(is_finish_request(text))


class TestGatesAndSafety(unittest.TestCase):
    def test_length_gate_boundary(self):
        """21 字以上一律不看 —— 需要铺垫一长串的都不是"说完了"。"""
        self.assertGreater(MAX_LEN, 0)
        long_text = "结束" + "啊" * (MAX_LEN + 5)
        self.assertFalse(is_finish_request(long_text))

    def test_empty_and_none(self):
        for text in (None, "", "   ", "\n", "，。！"):
            with self.subTest(text=text):
                self.assertFalse(is_finish_request(text))
                self.assertEqual(match_reason(text), "")

    def test_deterministic(self):
        outs = {is_finish_request("好的，我没什么问题了，谢谢老师") for _ in range(20)}
        self.assertEqual(outs, {True})

    def test_normalize_strips_punctuation_and_whitespace(self):
        self.assertEqual(normalize(" 结束 吧 。"), "结束吧")
        self.assertEqual(normalize(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
