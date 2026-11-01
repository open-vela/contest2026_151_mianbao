"""growth 单元测试 —— 纯函数，不碰 Flask/磁盘。

守三件事：
1. 老数据（无 score / 无 expression）不能炸，也不能编造；
2. 维度对比只比"最近两场都有评分"的场次；
3. 薄弱点必须"反复失分"，单场低分不贴标签。
"""
import unittest
from datetime import date

import growth


def snap(sid, created, total=None, dims=None, expression=None, role="AI 应用开发",
         version=None):
    score = None
    if total is not None or dims:
        score = {"total": total, "dimensions": [
            {"name": name, "score": value} for name, value in (dims or {}).items()
        ]}
        if version is not None:
            score["scoring_version"] = version
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

    def test_version_mixed_is_flagged(self):
        """v1（均分）和 v2（加权）混在一起时必须提示不可直接比。"""
        result = growth.build_growth([
            snap("a", 100, 60, {"技术正确性": 6}),            # 老场次：无 version → v1
            snap("b", 200, 70, {"技术正确性": 7}, version=2),  # 新场次：v2
        ])
        self.assertTrue(result["version_mixed"])
        self.assertEqual(result["scoring_versions"], [1, 2])

    def test_same_version_is_not_mixed(self):
        result = growth.build_growth([
            snap("a", 100, 60, {"技术正确性": 6}, version=2),
            snap("b", 200, 70, {"技术正确性": 7}, version=2),
        ])
        self.assertFalse(result["version_mixed"])
        self.assertEqual(result["scoring_versions"], [2])


class TestWeakLifecycle(unittest.TestCase):
    def _points(self, *rows):
        return growth.points_of([
            snap(sid, when, total, {"深度与原理": score}) for sid, when, total, score in rows
        ])

    def test_repeated_low_scores_become_a_lifecycle(self):
        points = self._points(
            ("a", "2026-10-01", 50, 5),
            ("b", "2026-10-03", 55, 4),
        )
        items = growth.weak_lifecycle(points, today=date(2026, 10, 4))
        item = next(i for i in items if i["dimension"] == "深度与原理")
        self.assertEqual(item["times_seen"], 2)
        self.assertFalse(item["improved"])
        self.assertEqual(item["first_seen"], "2026-10-01")
        self.assertEqual(item["last_seen"], "2026-10-03")
        self.assertEqual(item["interval_days"], 1)
        self.assertEqual(item["next_review"], "2026-10-04")
        self.assertTrue(item["due"])

    def test_two_good_assessments_improve_and_three_archive(self):
        points = self._points(
            ("a", "2026-10-01", 50, 5),
            ("b", "2026-10-03", 55, 5),
            ("c", "2026-10-05", 70, 7),
            ("d", "2026-10-07", 80, 8),
            ("e", "2026-10-09", 85, 9),
        )
        item = growth.weak_lifecycle(points, today=date(2026, 10, 10))[0]
        self.assertEqual(item["times_seen"], 2)
        self.assertTrue(item["improved"])
        self.assertTrue(item["archived"])
        self.assertIsNone(item["next_review"])
        self.assertFalse(item["due"])

    def test_missing_dimension_does_not_count_as_improvement(self):
        """模型漏评该维度 ≠ 改善：中间那场没评它，不该中断低分链。"""
        points = growth.points_of([
            snap("a", "2026-10-01", 50, {"深度与原理": 5}),
            snap("b", "2026-10-03", 60, {"技术正确性": 8}),   # 这一场没评"深度与原理"
            snap("c", "2026-10-05", 70, {"深度与原理": 7}),
        ])
        item = growth.weak_lifecycle(points, today=date(2026, 10, 6))[0]
        self.assertEqual(item["times_seen"], 1)
        self.assertEqual(item["good_streak"], 1)
        self.assertFalse(item["improved"])

    def test_review_interval_grows_1_3_7(self):
        points = self._points(
            ("a", "2026-10-01", 50, 5),
            ("b", "2026-10-03", 60, 6),   # 质量 3 → 间隔 1
            ("c", "2026-10-05", 70, 7),   # 质量 4 → 间隔 3
        )
        item = growth.weak_lifecycle(points, today=date(2026, 10, 6))[0]
        self.assertEqual(item["interval_days"], 3)
        self.assertEqual(item["next_review"], "2026-10-08")
        self.assertTrue(item["due"] is False)


if __name__ == "__main__":
    unittest.main()
