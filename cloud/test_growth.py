"""growth 单元测试 —— 纯函数，不碰 Flask/磁盘。

守三件事：
1. 老数据（无 score / 无 expression）不能炸，也不能编造；
2. 维度对比只比"最近两场都有评分"的场次；
3. 薄弱点必须"反复失分"，单场低分不贴标签。
"""
import unittest

import growth


def snap(sid, created, total=None, dims=None, expression=None, role="AI 应用开发"):
    score = None
    if total is not None or dims:
        score = {"total": total, "dimensions": [
            {"name": name, "score": value} for name, value in (dims or {}).items()
        ]}
    return {
        "session_id": sid,
        "role": role,
        "created_at": created,
        "score": score,
        "expression": expression or [],
        "messages": [{"role": "user", "content": "答"}, {"role": "assistant", "content": "问"}],
    }


class TestPointOf(unittest.TestCase):
    def test_empty_snapshot_does_not_raise(self):
        point = growth.point_of({})
        self.assertIsNone(point["total"])
        self.assertEqual(point["dimensions"], {})
        self.assertEqual(point["expression"]["fillers"], None)

    def test_full_snapshot(self):
        point = growth.point_of(snap("s1", 100, 70, {"深度与原理": 6},
                                     [{"chars": 50, "chars_per_min": 220,
                                       "duration_sec": 15, "fillers": 3,
                                       "pauses": 2}]))
        self.assertEqual(point["total"], 70)
        self.assertEqual(point["dimensions"], {"深度与原理": 6})
        self.assertEqual(point["expression"]["avg_speed"], 220)
        self.assertEqual(point["expression"]["fillers"], 3)
        self.assertEqual(point["expression"]["pauses"], 2)
        self.assertEqual(point["expression"]["avg_answer_sec"], 15.0)


class TestOrdering(unittest.TestCase):
    def test_points_sorted_ascending(self):
        points = growth.points_of([snap("b", 200), snap("a", 100)])
        self.assertEqual([p["session_id"] for p in points], ["a", "b"])


class TestDeltas(unittest.TestCase):
    def test_none_with_single_scored_session(self):
        points = growth.points_of([snap("a", 100, 60, {"深度与原理": 5})])
        self.assertIsNone(growth.dimension_deltas(points))

    def test_compares_last_two_scored(self):
        points = growth.points_of([
            snap("a", 100, 60, {"深度与原理": 5, "技术正确性": 7}),
            snap("b", 200),                                   # 未评分：跳过
            snap("c", 300, 68, {"深度与原理": 7, "技术正确性": 7}),
        ])
        deltas = growth.dimension_deltas(points)
        self.assertEqual(deltas["previous"], "a")
        self.assertEqual(deltas["latest"], "c")
        self.assertEqual(deltas["total"], 8)
        by_name = {d["name"]: d for d in deltas["dimensions"]}
        self.assertEqual(by_name["深度与原理"]["delta"], 2)
        self.assertEqual(by_name["技术正确性"]["delta"], 0)


class TestWeakPoints(unittest.TestCase):
    def test_single_low_session_is_not_a_weak_point(self):
        points = growth.points_of([
            snap("a", 100, 60, {"深度与原理": 5}),
            snap("b", 200, 70, {"深度与原理": 8}),
        ])
        self.assertEqual(growth.weak_points(points), [])

    def test_repeated_low_sessions(self):
        points = growth.points_of([
            snap("a", 100, 60, {"深度与原理": 4, "技术正确性": 8}),
            snap("b", 200, 62, {"深度与原理": 5, "技术正确性": 8}),
            snap("c", 300, 64, {"深度与原理": 5, "技术正确性": 9}),
        ])
        weak = growth.weak_points(points)
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0]["name"], "深度与原理")
        self.assertEqual(weak[0]["low_sessions"], 3)
        self.assertEqual(weak[0]["average"], 4.7)


class TestBuildGrowth(unittest.TestCase):
    def test_shape(self):
        result = growth.build_growth([
            snap("a", 100, 60, {"深度与原理": 5}),
            snap("b", 200, 70, {"深度与原理": 7}),
        ])
        self.assertEqual(len(result["points"]), 2)
        self.assertIsNotNone(result["deltas"])
        self.assertIsInstance(result["weak_points"], list)


if __name__ == "__main__":
    unittest.main()
