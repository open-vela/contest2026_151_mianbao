"""report_pdf 单元测试。

reportlab 是可选依赖：**没装时大声跳过**（同 run_tests.sh 对路由测试的做法），
不是静默跳过 —— 静默跳过正是 §11.25 记下的教训。
"""
import unittest

import report_pdf


def sample_snapshot():
    return {
        "session_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "role": "AI 应用开发",
        "pressure": "标准",
        "question_count": 2,
        "is_finished": True,
        "created_at": 1759000000.0,
        "updated_at": 1759000060.0,
        "messages": [
            {"role": "assistant", "content": "请介绍一下你自己。"},
            {"role": "user", "content": "我用向量数据库做检索，召回率提升到 92%。"},
            {"role": "assistant", "content": "**面试评估报告**\n总体评价：表达清楚，但深度不足。"},
        ],
        "score": {
            "total": 70,
            "dimensions": [
                {"name": "深度与原理", "score": 6, "max": 10,
                 "comment": "能说结论，原理展开不够。",
                 "evidence": "召回率提升到 92%"},
                {"name": "表达与结构", "score": 8, "max": 10, "comment": "条理清楚。"},
            ],
            "summary": "基础扎实，补原理。",
            "per_question": [
                {"index": 1, "question": "介绍自己",
                 "evidence": "我用向量数据库", "suggestion": "先说岗位匹配点。"},
            ],
        },
        "expression": [
            {"round": 1, "chars": 30, "fillers": 2, "filler_detail": {"嗯": 2},
             "duration_sec": 12.5, "chars_per_min": 210, "pauses": 1,
             "longest_pause_sec": 0.8, "speech_ratio": 0.75},
        ],
    }


@unittest.skipUnless(report_pdf.available(), "未安装 reportlab（pip install reportlab）")
class TestReportPdf(unittest.TestCase):
    def test_renders_valid_pdf(self):
        body = report_pdf.render(sample_snapshot())
        self.assertTrue(body.startswith(b"%PDF"), "应是一份真正的 PDF")
        self.assertGreater(len(body), 2000, "内容不应为空壳")

    def test_empty_snapshot_does_not_raise(self):
        body = report_pdf.render({})
        self.assertTrue(body.startswith(b"%PDF"))

    def test_partial_snapshot_without_score_or_expression(self):
        snap = sample_snapshot()
        snap.pop("score")
        snap.pop("expression")
        body = report_pdf.render(snap)
        self.assertTrue(body.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
