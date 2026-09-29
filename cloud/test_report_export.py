#!/usr/bin/env python3
"""report_export 单元测试 —— 不联网、不需要 key：`python3 test_report_export.py`。

输入样本就是 `session_manager.snapshot()` 的形状（落盘存的也是它），所以这里
顺带锁住了"导出与内存/磁盘三处字段一致"这件事。
"""
import json
import re
import unittest

from report_export import (
    SUPPORTED,
    export,
    filename,
    report_text,
    to_json,
    to_markdown,
)

FINISHED = {
    "session_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
    "role": "AI 应用开发",
    "question_count": 11,
    "is_finished": True,
    "created_at": 1759000000.0,
    "updated_at": 1759001200.0,
    "messages": [
        {"role": "assistant", "content": "请简单介绍一下你自己。"},
        {"role": "user", "content": "我负责的是检索模块，用的是 Faiss。"},
        {"role": "assistant", "content": "建议把召回评估的细节补齐，整体基础扎实。"},
    ],
    "report": "建议把召回评估的细节补齐，整体基础扎实。",
    "score": {
        "dimensions": [
            {"name": "表达与逻辑", "score": 8, "max": 10,
             "evidence": "我负责的是检索模块", "comment": "条理清晰"},
            {"name": "专业深度", "score": 6, "max": 10,
             "evidence": "用的是 Faiss", "comment": "选型说得清，评估没展开"},
        ],
        "missing": ["项目经验", "岗位匹配"],
        "total": 70,
        "summary": "基础扎实，建议补齐评估细节。",
        "status": "ok",
    },
}

RUNNING = {
    "session_id": "abc-123",
    "role": "AI 应用开发",
    "question_count": 2,
    "is_finished": False,
    "created_at": 1759000000.0,
    "updated_at": 1759000060.0,
    "messages": [
        {"role": "assistant", "content": "请简单介绍一下你自己。"},
        {"role": "user", "content": "我负责的是检索模块。"},
    ],
}


class TestMarkdown(unittest.TestCase):
    def test_has_all_sections(self):
        md = to_markdown(FINISHED)
        for token in ("# AI 模拟面试官 · 面试报告", "## 总评", "## 评分", "## 对话记录"):
            self.assertIn(token, md)

    def test_header_fields(self):
        md = to_markdown(FINISHED)
        self.assertIn("**岗位**：AI 应用开发", md)
        self.assertIn(FINISHED["session_id"], md)
        self.assertIn("**问答轮次**：11", md)
        self.assertIn("**状态**：已结束", md)

    def test_report_text_is_the_last_assistant_message(self):
        md = to_markdown(FINISHED)
        self.assertIn("建议把召回评估的细节补齐，整体基础扎实。", md)
        self.assertNotIn("（本次面试还没有生成报告）", md)

    def test_scores_are_rendered(self):
        md = to_markdown(FINISHED)
        self.assertIn("**总分：70 / 100**", md)
        self.assertIn("| 表达与逻辑 | 8 / 10 | 条理清晰 |", md)
        self.assertIn("依据：我负责的是检索模块", md)
        self.assertIn("本次未评的维度：项目经验、岗位匹配", md)

    def test_transcript_labels_both_speakers(self):
        md = to_markdown(FINISHED)
        self.assertIn("**面试官**：请简单介绍一下你自己。", md)
        self.assertIn("**候选人**：我负责的是检索模块，用的是 Faiss。", md)

    def test_running_session_without_report_or_score(self):
        md = to_markdown(RUNNING)
        self.assertIn("（本次面试还没有生成报告）", md)
        self.assertIn("**状态**：进行中", md)
        self.assertNotIn("## 评分", md)      # 没有评分就不该出现空表格

    def test_pipe_in_comment_does_not_break_table(self):
        """评语里带 | 会把 Markdown 表格切碎，必须转义。"""
        snap = json.loads(json.dumps(FINISHED))
        snap["score"]["dimensions"][0]["comment"] = "条理清晰 | 但语速快"
        md = to_markdown(snap)
        self.assertIn("条理清晰 \\| 但语速快", md)

    def test_empty_and_none_are_safe(self):
        for snap in (None, {}, {"waiting": True}):
            with self.subTest(snapshot=snap):
                md = to_markdown(snap)
                self.assertIn("面试报告", md)


class TestReportText(unittest.TestCase):
    def test_prefers_report_field(self):
        self.assertEqual(report_text(FINISHED), FINISHED["report"])

    def test_falls_back_to_last_assistant_when_finished(self):
        """没有 report 字段但已结束 → 复用最后一条 assistant 消息，不另存一份。"""
        snap = dict(FINISHED)
        snap.pop("report")
        self.assertEqual(report_text(snap),
                         "建议把召回评估的细节补齐，整体基础扎实。")

    def test_no_report_while_running(self):
        self.assertEqual(report_text(RUNNING), "")

    def test_blank_report_field_falls_through(self):
        snap = dict(FINISHED, report="   ")
        self.assertEqual(report_text(snap),
                         "建议把召回评估的细节补齐，整体基础扎实。")

    def test_bad_input(self):
        for snap in (None, {}, [], "文字"):
            with self.subTest(snapshot=snap):
                self.assertEqual(report_text(snap), "")


class TestExport(unittest.TestCase):
    def test_markdown(self):
        body, mime, name = export(FINISHED, "md")
        self.assertTrue(body.startswith("# AI 模拟面试官"))
        self.assertIn("markdown", mime)
        self.assertTrue(name.endswith(".md"))

    def test_json(self):
        body, mime, name = export(FINISHED, "json")
        self.assertEqual(json.loads(body)["session_id"], FINISHED["session_id"])
        self.assertIn("json", mime)
        self.assertTrue(name.endswith(".json"))

    def test_default_is_markdown(self):
        self.assertTrue(export(FINISHED)[0].startswith("# AI 模拟面试官"))

    def test_blank_format_falls_back_to_markdown(self):
        """空/缺省按 md 处理 —— 前端不带参数直接点导出时走的就是这条路。"""
        for fmt in ("", None):
            with self.subTest(fmt=fmt):
                self.assertTrue(export(FINISHED, fmt)[0].startswith("# AI 模拟面试官"))

    def test_unsupported_format(self):
        for fmt in ("pdf", "docx", "mdx", "markdown"):
            with self.subTest(fmt=fmt):
                self.assertIsNone(export(FINISHED, fmt))

    def test_json_round_trips_everything(self):
        self.assertEqual(json.loads(to_json(FINISHED)), FINISHED)

    def test_filename_is_ascii_with_session_prefix(self):
        """文件名必须纯 ASCII —— 中文名要走 RFC 5987，各版本 Werkzeug 行为不一致。"""
        name = filename(FINISHED, "md")
        name.encode("ascii")        # 抛异常就是失败
        self.assertRegex(name, r"^interview_report_0f8fad5b_\d{8}-\d{4}\.md$")

    def test_filename_survives_bad_session_id(self):
        for bad in (None, "", "会话一", "../../etc/passwd"):
            with self.subTest(session_id=bad):
                name = filename({"session_id": bad}, "json")
                name.encode("ascii")
                self.assertRegex(name, r"^interview_report_(session|\w+)_\d{8}-\d{4}\.json$")

    def test_supported_list(self):
        self.assertEqual(set(SUPPORTED), {"md", "json"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
