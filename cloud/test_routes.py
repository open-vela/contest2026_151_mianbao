#!/usr/bin/env python3
"""HTTP 路由的单元测试 —— 不联网、不需要真 key、不需要开发板。

为什么要有它
------------
赛后第一批迭代新增了会话落盘、`/api/export`、网页报告卡片，但合并前只做过
**静态验证**（语法编译 + 各模块单测）。单测照不到"接线"那一层：路由有没有注册上、
`send_file` 的参数对不对、内存优先/磁盘兜底的顺序对不对、快照能不能 JSON 序列化
出去。这些地方错了，表现是"接口 404/500"，而不是某个函数的返回值不对。

所以这里用 Flask 自带的 test client 走**真实的 HTTP 往返**（进程内完成，不起服务、
不占端口）。**刻意不碰 ASR / LLM / TTS**：那三个会真打 API、要花钱，而本文件的
目的是验路由与落盘，不是验模型。

三条隔离
--------
* **磁盘**：`session_store.DATA_DIR` 在 setUp 里被指到临时目录 —— 绝不碰
  `cloud/data/`（那里可能是你真实练过的面试记录）。
* **内存**：`app.session_manager.sessions` 每个用例前清空，用例之间不串味。
* **密钥**：导入 app 之前塞一个**假 key**。app.py 在**导入期**就校验它、空则
  SystemExit（见 app.py 顶部那段注释），不塞就 import 不进来。这里刻意用 `[]=`
  而不是 `setdefault`：即使你本机有真 key 也会被这份假值顶掉 —— 这样才算证明了
  "这些测试与 key 无关"。值**刻意不带 `sk-` 前缀**，免得被 tools/redact_secrets.sh
  当成泄露的密钥拦下来。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

# app.py 在导入期就要 key，所以这两行必须在 `import app` 之前。
os.environ["MIMO_API_KEY"] = "dummy-key-for-tests-never-used"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as cloud_app          # noqa: E402
import session_store             # noqa: E402

# 合法的会话 id（形状同 uuid4；会话白名单要求 1~64 位 [A-Za-z0-9_-]）
SID = "0f8fad5b-d9cb-469f-a165-70867728950e"
REPORT = "整体回答逻辑清晰，尤其在「召回率提升到 92%」这句上给了具体数字。"


def snapshot(session_id, **extra):
    """一份形状与 `session_manager.snapshot()` 一致的样本（含一份已结束的对话）。"""
    snap = {
        "session_id": session_id,
        "role": "AI 应用开发",
        "question_count": 2,
        "is_finished": True,
        "created_at": 1759000000.0,
        "updated_at": 1759000060.0,
        "messages": [
            {"role": "assistant", "content": "请介绍一下你自己。"},
            {"role": "user", "content": "我用向量数据库做检索，召回率提升到 92%。"},
            {"role": "assistant", "content": "能说说你是怎么评估召回率的吗？"},
            {"role": "user", "content": "用离线标注集算的，取了五百条。"},
            {"role": "assistant", "content": REPORT},
        ],
    }
    snap.update(extra)
    return snap


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.client = cloud_app.app.test_client()

        # 磁盘隔离：指到临时目录，绝不碰仓库里的 cloud/data/
        self._orig_dir = session_store.DATA_DIR
        self.tmp = tempfile.mkdtemp(prefix="routes_test_")
        session_store.DATA_DIR = os.path.join(self.tmp, "sessions")

        # 内存隔离：不带上一个用例留下的会话
        cloud_app.session_manager.sessions.clear()

    def tearDown(self):
        cloud_app.session_manager.sessions.clear()
        session_store.DATA_DIR = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def disk_files(self):
        try:
            return sorted(os.listdir(session_store.DATA_DIR))
        except OSError:
            return []


class TestBasicRoutes(RouteTestCase):
    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json().get("status"), "ok")

    def test_index_serves_display_page(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        page = r.data.decode("utf-8")
        self.assertIn("AI 模拟面试官", page)
        # 报告卡片容器（2026-09-29 新增）：漏了这一块，面试结束后网页不会变化
        self.assertIn('id="report"', page)

    def test_history_empty(self):
        """一场都没有时必须给 waiting=True，前端据此显示"等待面试开始"。"""
        r = self.client.get("/api/history")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json().get("waiting"))

    def test_history_unknown_session_is_waiting(self):
        """指定了一个不存在的 session_id → 目前也返回 waiting=True。

        ⚠️ 这是**现状**而不是理想行为：调用方分不清"这个 id 不存在"和"一场都没有"。
        记在这里是为了将来真要给网页做深链接时，能一眼看到这里得先改。
        """
        r = self.client.get("/api/history?session_id=no-such-session")
        self.assertTrue(r.get_json().get("waiting"))


class TestHistoryFromMemory(RouteTestCase):
    def test_reads_live_session(self):
        sess = cloud_app.session_manager.get_or_create_session(SID, "AI 应用开发")
        sess.add_user_message("我用向量数据库做检索。")
        sess.add_ai_message("能说说召回是怎么评估的吗？")

        data = self.client.get(f"/api/history?session_id={SID}").get_json()
        self.assertEqual(data["session_id"], SID)
        self.assertEqual(len(data["messages"]), 2)
        self.assertFalse(data["is_finished"])

    def test_finished_flag_is_real(self):
        """`is_finished` 曾经恒为 False（finish() 零调用者）—— 网页的报告卡片靠它。"""
        sess = cloud_app.session_manager.get_or_create_session(SID, "AI 应用开发")
        sess.add_ai_message(REPORT)
        sess.finish()
        data = self.client.get(f"/api/history?session_id={SID}").get_json()
        self.assertTrue(data["is_finished"])


class TestDiskFallback(RouteTestCase):
    """会话每轮落盘 —— 重启之后网页与导出仍应能取到上一场。"""

    def test_survives_memory_loss(self):
        self.assertTrue(session_store.save(snapshot(SID)))

        cloud_app.session_manager.sessions.clear()      # 模拟"Flask 重启了"

        data = self.client.get(f"/api/history?session_id={SID}").get_json()
        self.assertEqual(data["session_id"], SID)
        self.assertEqual(len(data["messages"]), 5)
        self.assertTrue(data["is_finished"])

    def test_latest_without_parameter(self):
        session_store.save(snapshot(SID))
        data = self.client.get("/api/history").get_json()
        self.assertEqual(data["session_id"], SID)

    def test_memory_wins_over_disk(self):
        """内存与磁盘都有时以内存为准（内存是活的，磁盘是上一轮的存档）。"""
        session_store.save(snapshot(SID, question_count=99))
        sess = cloud_app.session_manager.get_or_create_session(SID, "AI 应用开发")
        sess.add_user_message("现场这一轮")
        data = self.client.get(f"/api/history?session_id={SID}").get_json()
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["question_count"], 0)


class TestExport(RouteTestCase):
    def setUp(self):
        super().setUp()
        session_store.save(snapshot(SID))

    def test_markdown(self):
        r = self.client.get(f"/api/export/{SID}?format=md")
        self.assertEqual(r.status_code, 200)
        self.assertIn("markdown", r.headers.get("Content-Type", ""))
        body = r.data.decode("utf-8")
        self.assertIn("AI 应用开发", body)          # 岗位
        self.assertIn(REPORT, body)                 # 报告正文
        self.assertIn("## 对话记录", body)

    def test_json_is_parseable(self):
        r = self.client.get(f"/api/export/{SID}?format=json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("json", r.headers.get("Content-Type", ""))
        blob = json.loads(r.data.decode("utf-8"))
        self.assertEqual(blob["session_id"], SID)
        self.assertTrue(blob["is_finished"])
        self.assertEqual(len(blob["messages"]), 5)

    def test_default_format_is_markdown(self):
        r = self.client.get(f"/api/export/{SID}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("markdown", r.headers.get("Content-Type", ""))

    def test_unsupported_format(self):
        """⚠️ 这条必须用**存在**的会话：路由是先找会话、再判格式。

        会话不存在时无论 format 是什么都返回 404 —— 用不存在的 id 测格式，
        测到的是"找不到会话"，会得到一个假的失败结论。
        """
        r = self.client.get(f"/api/export/{SID}?format=xml")
        self.assertEqual(r.status_code, 400)

    def test_missing_session_is_404(self):
        r = self.client.get("/api/export/no-such-session?format=md")
        self.assertEqual(r.status_code, 404)

    def test_filename_is_ascii_and_attachment(self):
        """文件名走 Content-Disposition —— 非 ASCII 会引出 RFC 5987 编码的坑，
        所以实现里刻意只用会话 id 与时间（中文标题写在正文里）。"""
        r = self.client.get(f"/api/export/{SID}?format=md")
        disposition = r.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertTrue(disposition.isascii(), f"文件名含非 ASCII：{disposition!r}")
        self.assertIn(".md", disposition)

    def test_export_is_read_only(self):
        """导出只读：不改会话、不落新文件（对板子那条链路不能有任何影响）。"""
        before = self.disk_files()
        self.client.get(f"/api/export/{SID}?format=md")
        self.client.get(f"/api/export/{SID}?format=json")
        self.assertEqual(self.disk_files(), before)
        self.assertEqual(cloud_app.session_manager.sessions, {})


class TestExportPathTraversal(RouteTestCase):
    """session_id 会变成文件名（`session_store._path`），这里从 HTTP 这一层再验一道。"""

    BAD_IDS = ("..%2F..%2Fetc%2Fpasswd", "..", "a%2Fb", "%2e%2e", "x" * 65)

    def test_rejected(self):
        for bad in self.BAD_IDS:
            with self.subTest(session_id=bad):
                r = self.client.get(f"/api/export/{bad}?format=md")
                self.assertIn(r.status_code, (400, 404), f"非法 id 竟被接受：{bad}")
        self.assertEqual(self.disk_files(), [])

    def test_nothing_written_outside(self):
        self.client.get("/api/export/..%2F..%2Fpwned?format=md")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pwned")))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.tmp), "pwned")))


class TestSessionsList(RouteTestCase):
    """`GET /api/sessions` —— 公共设备上"我刚面完的那场"就是从这里认出来的。"""

    SID2 = "11112222-3333-4444-5555-666677778888"

    def test_empty(self):
        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["sessions"], [])
        self.assertEqual(body["limit"], 20)

    def test_newest_first(self):
        for session_id, stamp in ((SID, 1), (self.SID2, 2)):
            session_store.save(snapshot(session_id))
            os.utime(os.path.join(session_store.DATA_DIR, session_id + ".json"),
                     (stamp, stamp))

        ids = [s["session_id"] for s in self.client.get("/api/sessions").get_json()["sessions"]]
        self.assertEqual(ids, [self.SID2, SID])

    def test_item_fields_are_enough_to_recognise_a_session(self):
        session_store.save(snapshot(SID))
        item = self.client.get("/api/sessions").get_json()["sessions"][0]

        self.assertEqual(item["session_id"], SID)
        self.assertEqual(item["role"], "AI 应用开发")
        self.assertTrue(item["is_finished"])
        self.assertEqual(item["rounds"], 2)
        # ★ 认领靠的是这句，不是编号
        self.assertIn("向量数据库", item["first_answer"])
        # 列表项不该带整场对话
        self.assertNotIn("messages", item)

    def test_limit_is_clamped(self):
        for query, expect in (("?limit=999", 100), ("?limit=abc", 20),
                              ("?limit=0", 1), ("?limit=-5", 1)):
            with self.subTest(query=query):
                self.assertEqual(
                    self.client.get("/api/sessions" + query).get_json()["limit"], expect)

    def test_corrupt_file_does_not_break_the_endpoint(self):
        session_store.save(snapshot(SID))
        with open(os.path.join(session_store.DATA_DIR, "broken.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{ 半截")

        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([s["session_id"] for s in r.get_json()["sessions"]], [SID])

    def test_list_does_not_touch_memory_sessions(self):
        """列表只读磁盘 —— 正在进行的会话不该被它搅动。"""
        cloud_app.session_manager.get_or_create_session(SID, "AI 应用开发")
        before = len(cloud_app.session_manager.sessions)
        self.client.get("/api/sessions")
        self.assertEqual(len(cloud_app.session_manager.sessions), before)


class TestHistoryPage(RouteTestCase):
    def test_serves_the_same_html_as_the_display_page(self):
        """列表页与展示页共用一个 HTML（前端按路径分支）—— 这个断言是那条约定的锁。"""
        listing = self.client.get("/history")
        display = self.client.get("/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, display.data)

        page = listing.data.decode("utf-8")
        self.assertIn('id="hist"', page, "列表容器不在")
        self.assertIn('id="report"', page, "展示页的容器不在")


if __name__ == "__main__":
    unittest.main(verbosity=2)
