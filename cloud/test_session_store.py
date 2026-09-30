#!/usr/bin/env python3
"""session_store 单元测试 —— 不联网、不需要 key：`python3 test_session_store.py`。

全部在本进程的临时目录里跑（setUp 把 `session_store.DATA_DIR` 指过去），
绝不碰 `cloud/data/`，也不依赖任何外部状态。

两组重点：
* **路径穿越**：session_id 直接来自请求体，这里是它唯一被当文件名用的地方；
* **save() 永不抛异常**：落盘在面试主链路上，磁盘出任何问题都只能记日志。
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import session_store


def snapshot(session_id, **extra):
    """一份形状与 `session_manager.snapshot()` 一致的样本。"""
    snap = {
        "session_id": session_id,
        "role": "AI 应用开发",
        "question_count": 2,
        "is_finished": False,
        "created_at": 1759000000.0,
        "updated_at": 1759000060.0,
        "messages": [
            {"role": "user", "content": "我负责的是检索模块。"},
            {"role": "assistant", "content": "能具体说说召回是怎么评估的吗？"},
        ],
    }
    snap.update(extra)
    return snap


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_dir = session_store.DATA_DIR
        self.tmp = tempfile.mkdtemp(prefix="session_store_test_")
        # 每个用例一个干净的目录；目录本身**不预先创建** ——
        # "目录还不存在"是首次运行时的真实状态，必须能自己建出来。
        session_store.DATA_DIR = os.path.join(self.tmp, "sessions")

    def tearDown(self):
        session_store.DATA_DIR = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def files(self):
        try:
            return sorted(os.listdir(session_store.DATA_DIR))
        except OSError:
            return []


class TestRoundTrip(StoreTestCase):
    def test_save_then_load(self):
        snap = snapshot("abc-123")
        self.assertTrue(session_store.save(snap))
        self.assertEqual(session_store.load("abc-123"), snap)

    def test_creates_directory_on_first_save(self):
        self.assertFalse(os.path.isdir(session_store.DATA_DIR))
        session_store.save(snapshot("abc-123"))
        self.assertTrue(os.path.isdir(session_store.DATA_DIR))

    def test_chinese_is_not_escaped(self):
        """中文必须原样落盘（ensure_ascii=False）—— 打开文件要能直接读懂。"""
        session_store.save(snapshot("abc-123"))
        path = os.path.join(session_store.DATA_DIR, "abc-123.json")
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        self.assertIn("我负责的是检索模块。", raw)
        self.assertNotIn("\\u", raw)

    def test_second_save_overwrites(self):
        session_store.save(snapshot("abc-123"))
        session_store.save(snapshot("abc-123", question_count=9))
        self.assertEqual(session_store.load("abc-123")["question_count"], 9)

    def test_no_temp_file_left_behind(self):
        session_store.save(snapshot("abc-123"))
        self.assertEqual(self.files(), ["abc-123.json"])


class TestPathTraversal(StoreTestCase):
    """session_id 来自请求体（app.py:59），这里是它唯一被当文件名用的地方。"""

    BAD_IDS = (
        "../../etc/passwd",     # 经典穿越
        "../evil",
        "a/b",
        "a\\b",
        "..",
        ".",
        "",
        None,
        "a b",
        "abc.json",             # 带扩展名想覆盖已有文件
        "a" * 65,               # 超长
        "会话一",                # 非 ASCII（我们自己只生成 uuid）
        "abc\x00def",           # 空字节
    )

    def test_bad_ids_are_rejected(self):
        for bad in self.BAD_IDS:
            with self.subTest(session_id=bad):
                self.assertFalse(session_store.is_valid_id(bad))
                self.assertFalse(session_store.save(snapshot(bad)))
                self.assertIsNone(session_store.load(bad))

    def test_traversal_writes_nothing_outside(self):
        outside = os.path.join(self.tmp, "pwned")
        parent_outside = os.path.join(os.path.dirname(self.tmp), "pwned")
        session_store.save(snapshot("../pwned"))
        self.assertFalse(os.path.exists(outside))
        self.assertFalse(os.path.exists(parent_outside))
        self.assertEqual(self.files(), [])

    def test_valid_ids(self):
        for good in ("abc-123", "a", "A" * 64, "0f8fad5b-d9cb-469f-a165-70867728950e"):
            with self.subTest(session_id=good):
                self.assertTrue(session_store.is_valid_id(good))


class TestLoadFailures(StoreTestCase):
    def test_missing_file(self):
        self.assertIsNone(session_store.load("nope"))

    def test_corrupt_json(self):
        os.makedirs(session_store.DATA_DIR, exist_ok=True)
        with open(os.path.join(session_store.DATA_DIR, "broken.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")
        self.assertIsNone(session_store.load("broken"))

    def test_content_mismatch_is_rejected(self):
        """文件名与内容对不上（只可能是手工改过）→ 当损坏处理，别当成另一场返回。"""
        os.makedirs(session_store.DATA_DIR, exist_ok=True)
        other = snapshot("someone-else")
        with open(os.path.join(session_store.DATA_DIR, "abc-123.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(other, fh, ensure_ascii=False)
        self.assertIsNone(session_store.load("abc-123"))

    def test_json_array_is_rejected(self):
        os.makedirs(session_store.DATA_DIR, exist_ok=True)
        with open(os.path.join(session_store.DATA_DIR, "arr.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("[1, 2, 3]")
        self.assertIsNone(session_store.load("arr"))


class TestSaveNeverRaises(StoreTestCase):
    """落盘在面试主链路上 —— 它坏了只能记日志，绝不能把一次面试变成 500。"""

    def test_unwritable_directory(self):
        # 把一个**文件**当目录用：makedirs 必然失败
        blocker = os.path.join(self.tmp, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        session_store.DATA_DIR = os.path.join(blocker, "sessions")
        self.assertFalse(session_store.save(snapshot("abc-123")))

    def test_failed_replace_cleans_temp_file(self):
        with mock.patch.object(session_store.os, "replace",
                               side_effect=OSError("boom")):
            self.assertFalse(session_store.save(snapshot("abc-123")))
        self.assertEqual(self.files(), [])      # 半截临时文件不许留下

    def test_bad_snapshot_shapes(self):
        for bad in (None, {}, [], "字符串", 42):
            with self.subTest(snapshot=bad):
                self.assertFalse(session_store.save(bad))

    def test_non_serializable_value(self):
        self.assertFalse(session_store.save(snapshot("abc-123", weird=object())))


class TestLoadLatest(StoreTestCase):
    def test_no_directory(self):
        self.assertIsNone(session_store.load_latest())

    def test_empty_directory(self):
        os.makedirs(session_store.DATA_DIR, exist_ok=True)
        self.assertIsNone(session_store.load_latest())

    def test_picks_newest_by_mtime(self):
        session_store.save(snapshot("old", question_count=1))
        session_store.save(snapshot("new", question_count=2))
        os.utime(os.path.join(session_store.DATA_DIR, "old.json"), (1, 1))
        os.utime(os.path.join(session_store.DATA_DIR, "new.json"), (2, 2))
        self.assertEqual(session_store.load_latest()["session_id"], "new")

    def test_ignores_stray_files(self):
        """目录里的杂物（编辑器备份、上传中的临时文件）不能被当成会话。"""
        session_store.save(snapshot("real"))
        for name in ("notes.txt", "real.json.bak", ".hidden.json", "x.tmp"):
            with open(os.path.join(session_store.DATA_DIR, name), "w",
                      encoding="utf-8") as fh:
                fh.write("{}")
        self.assertEqual(session_store.load_latest()["session_id"], "real")


class TestSummary(unittest.TestCase):
    """`summary_of()` —— 列表页只该拿到它要的那几个字段。"""

    def test_shape_and_values(self):
        snap = snapshot("abc-123", score={"total": 78, "dimensions": []})
        summary = session_store.summary_of(snap, mtime=123.0)

        self.assertEqual(summary["session_id"], "abc-123")
        self.assertEqual(summary["role"], "AI 应用开发")
        self.assertEqual(summary["rounds"], 1)            # 样本里有一条 user 消息
        self.assertFalse(summary["is_finished"])
        self.assertEqual(summary["score_total"], 78)
        self.assertEqual(summary["mtime"], 123.0)
        self.assertIn("我负责的是检索模块", summary["first_answer"])

    def test_no_score_gives_none_not_zero(self):
        """没评过分 ≠ 0 分 —— 页面上前者不显示、后者会显示"0 分"。"""
        self.assertIsNone(session_store.summary_of(snapshot("abc-123"))["score_total"])

    def test_first_answer_is_the_candidate_not_the_interviewer(self):
        snap = snapshot("abc-123")
        snap["messages"] = [
            {"role": "assistant", "content": "请介绍一下你自己。"},
            {"role": "user", "content": "我是候选人说的第一句。"},
            {"role": "user", "content": "第二句。"},
        ]
        self.assertEqual(session_store.summary_of(snap)["first_answer"], "我是候选人说的第一句。")

    def test_first_answer_is_truncated(self):
        long = "很长的一段回答" * 20
        snap = snapshot("abc-123")
        snap["messages"] = [{"role": "user", "content": long}]
        first = session_store.summary_of(snap)["first_answer"]
        self.assertEqual(len(first), 41)                  # 40 字 + 省略号
        self.assertTrue(first.endswith("…"))

    def test_no_messages(self):
        snap = snapshot("abc-123")
        snap["messages"] = []
        summary = session_store.summary_of(snap)
        self.assertEqual(summary["first_answer"], "")
        self.assertEqual(summary["rounds"], 0)

    def test_bad_shapes_do_not_raise(self):
        for bad in (None, {}, [], "字符串", {"messages": "不是列表"},
                    {"messages": [None, 42, {"role": "user"}]}):
            with self.subTest(snapshot=bad):
                self.assertIsInstance(session_store.summary_of(bad), dict)


class TestListSummaries(StoreTestCase):
    def test_empty_directory(self):
        self.assertEqual(session_store.list_summaries(), [])

    def test_sorted_by_mtime_desc(self):
        session_store.save(snapshot("old", question_count=1))
        session_store.save(snapshot("mid", question_count=2))
        session_store.save(snapshot("new", question_count=3))
        for name, stamp in (("old", 1), ("mid", 2), ("new", 3)):
            os.utime(os.path.join(session_store.DATA_DIR, name + ".json"), (stamp, stamp))

        self.assertEqual([s["session_id"] for s in session_store.list_summaries()],
                         ["new", "mid", "old"])

    def test_respects_limit(self):
        for name in ("a", "b", "c"):
            session_store.save(snapshot(name))
        self.assertEqual(len(session_store.list_summaries(limit=2)), 2)
        self.assertEqual(len(session_store.list_summaries(limit=0)), 0)

    def test_corrupt_file_does_not_break_the_list(self):
        """⚠️ 一个半截文件不能把整个列表页拖成 500 —— 少一条记录远好过打不开。"""
        session_store.save(snapshot("good-one"))
        os.makedirs(session_store.DATA_DIR, exist_ok=True)
        with open(os.path.join(session_store.DATA_DIR, "broken.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")

        ids = [s["session_id"] for s in session_store.list_summaries()]
        self.assertEqual(ids, ["good-one"])

    def test_ignores_stray_files_and_bad_names(self):
        session_store.save(snapshot("real"))
        for name in ("notes.txt", ".hidden.json", "x.tmp", "带 空格.json"):
            with open(os.path.join(session_store.DATA_DIR, name), "w",
                      encoding="utf-8") as fh:
                fh.write("{}")
        self.assertEqual([s["session_id"] for s in session_store.list_summaries()], ["real"])

    def test_summaries_do_not_leak_the_transcript(self):
        """列表项里**不该有整场对话** —— 20 条 × 几十 KB 就白传了。"""
        session_store.save(snapshot("abc-123"))
        item = session_store.list_summaries()[0]
        self.assertNotIn("messages", item)


if __name__ == "__main__":
    unittest.main(verbosity=2)
