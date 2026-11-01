#!/usr/bin/env python3
"""导演环的纯规则测试 —— 不联网、不需要 key。"""
import unittest

import director

THIN = "我负责优化一下。"
EMPTY = ""
SUBSTANTIVE = (
    "我在检索链路里用 Faiss 做向量召回，线上 QPS 大概两百，缓存命中率 85%，"
    "把首屏延迟从 320ms 降到 180ms；主要代价是冷启动和内存占用，"
    "所以又加了一层预热和降级。"
)


class TestSignal(unittest.TestCase):
    def test_empty_and_thin(self):
        self.assertEqual(director.signal(EMPTY), "empty")
        self.assertEqual(director.signal(THIN), "thin")
        self.assertEqual(director.signal("嗯嗯，好的。"), "thin")

    def test_substantive(self):
        self.assertEqual(director.signal(SUBSTANTIVE), "substantive")


class TestDecide(unittest.TestCase):
    def test_opening_and_ask_back_do_not_intervene(self):
        self.assertEqual(director.decide("opening", "标准", SUBSTANTIVE),
                         (None, ""))
        self.assertEqual(director.decide("ask_back", "标准", SUBSTANTIVE),
                         (None, ""))

    def test_empty_answer_switches_angle(self):
        action, _ = director.decide("technical", "标准", EMPTY, [SUBSTANTIVE])
        self.assertEqual(action, "angle")

    def test_two_thin_answers_switch_topic(self):
        action, _ = director.decide("background", "标准", THIN, [THIN])
        self.assertEqual(action, "switch_topic")

    def test_one_thin_answer_switches_angle(self):
        action, _ = director.decide("technical", "标准", THIN, [SUBSTANTIVE])
        self.assertEqual(action, "angle")

    def test_substantive_answer_goes_deeper(self):
        action, _ = director.decide("technical", "标准", SUBSTANTIVE, [THIN])
        self.assertEqual(action, "deeper")

    def test_depth_cap_switches_topic(self):
        # 标准档上限 2：连续两条 substantive 就该换主题
        action, _ = director.decide("technical", "标准", SUBSTANTIVE,
                                    [SUBSTANTIVE])
        self.assertEqual(action, "switch_topic")
        # 温和档上限 1：一条 substantive 之后就不再追
        action, _ = director.decide("technical", "温和", SUBSTANTIVE,
                                    [SUBSTANTIVE])
        self.assertEqual(action, "switch_topic")

    def test_hint_is_readable(self):
        hint = director.hint("technical", "标准", THIN, [SUBSTANTIVE])
        self.assertIn("【导演】", hint)
        self.assertIn("同层换角度", hint)


if __name__ == "__main__":
    unittest.main()
