#!/usr/bin/env python3
"""P2 结构化评分的接线测试 —— **不联网、不花钱**（LLM 与三个 service 全被打桩）。

验三件事：

1. `llm_service.score_interview()` 的取舍 —— 模型输出走样时返回 `{}` 而不是崩；
2. `app._start_scoring()` 的接线 —— 评到分会写进会话**并落盘**；失败静默；
3. **端侧协议不变** —— `/api/interview` 的响应字段一个不多、一个不少。
   这是本轮最要紧的一条：评分只该进网页与导出，**绝不能混进板子那条链路**
   （板子只解析 5 个字段、缓冲 8MB，多塞东西没有任何好处）。

⚠️ 需要 Flask / openai（app.py 会 import 它们），归 `run_tests.sh` 里"装依赖才跑"
那一档；没装时它会**大声跳过**。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

# app.py 在**导入期**就校验 MIMO_API_KEY，空则 SystemExit —— 塞个假的（它只判非空）。
os.environ.setdefault("MIMO_API_KEY", "dummy-for-tests-never-used")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as cloud_app        # noqa: E402
import llm_service             # noqa: E402
import session_store           # noqa: E402
import score_guard             # noqa: E402

SID = "0f8fad5b-d9cb-469f-a165-70867728950e"
HISTORY = [
    {"role": "assistant", "content": "请介绍一下你自己。"},
    {"role": "user", "content": "我用向量数据库做检索，召回率提升到 92%。"},
]

# 一份闸门收拾得出来的模型输出（总分由 normalize 自己算：均值 7.0 → 70）
GOOD_JSON = json.dumps({
    "dimensions": [
        {"name": "技术正确性", "score": 8, "evidence": "召回率提升到 92%", "comment": "有数字"},
        {"name": "深度与原理", "score": 6, "evidence": "用向量数据库做检索", "comment": "点到为止"},
        {"name": "工程与场景思考", "score": 7, "evidence": "未提及", "comment": "说得少"},
        {"name": "表达与结构", "score": 7, "evidence": "未提及", "comment": "尚可"},
    ],
    "summary": "整体尚可。",
    "total": 999,          # 模型自己算的，必须被丢掉
}, ensure_ascii=False)


class ScoringTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_dir = session_store.DATA_DIR
        self.tmp = tempfile.mkdtemp(prefix="scoring_test_")
        session_store.DATA_DIR = os.path.join(self.tmp, "sessions")
        cloud_app.session_manager.sessions.clear()

    def tearDown(self):
        cloud_app.session_manager.sessions.clear()
        session_store.DATA_DIR = self._orig_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_session(self, sid=SID):
        session = cloud_app.session_manager.get_or_create_session(sid, "AI 应用开发")
        for message in HISTORY:
            if message["role"] == "user":
                session.add_user_message(message["content"])
            else:
                session.add_ai_message(message["content"])
        return session


class TestScoreInterview(unittest.TestCase):
    """`score_interview` 的取舍：能收拾就收拾，收拾不了就返回 {}（不崩）。"""

    def call(self, reply):
        with mock.patch.object(llm_service, "call_llm", return_value=reply) as patched:
            return llm_service.score_interview("AI 应用开发", list(HISTORY)), patched

    def test_happy_path(self):
        score, _ = self.call(GOOD_JSON)
        self.assertTrue(score_guard.is_usable(score))
        self.assertEqual(len(score["dimensions"]), 4)
        self.assertEqual(score["total"], 70, "总分必须是自己算的，不是模型给的 999")

    def test_prompt_has_every_dimension_injected(self):
        """维度**只有 DIMENSIONS 一个来源** —— 提示词模板里不写死，
        就不会出现"提示词要 5 个维度、代码只认 4 个"的漂移。"""
        _, patched = self.call(GOOD_JSON)
        prompt = patched.call_args.kwargs["system_prompt"]
        for name in score_guard.DIMENSIONS:
            self.assertIn(name, prompt, f"提示词里缺维度 {name}")
        self.assertNotIn("{dimensions}", prompt)
        self.assertNotIn("{role}", prompt)

    def test_prompt_comes_from_the_skill_file(self):
        skill = llm_service.load_skill("score_report")
        self.assertTrue(skill.get("system_prompt"), "读不到 skills/score_report.json")
        _, patched = self.call(GOOD_JSON)
        self.assertEqual(patched.call_args.kwargs["temperature"], skill["temperature"],
                         "温度应当取自 skill 文件（评分要稳定，不该用报告那个 0.7）")

    def test_various_bad_outputs_return_empty(self):
        for bad in ("", "对不起我做不到", "{}", '{"dimensions": []}',
                    '{"dimensions": [{"name": "不认识的维度", "score": 5}]}',
                    '{"dimensions": [{"name": "技术正确性", "score": "优秀"}]}'):
            with self.subTest(reply=bad):
                score, _ = self.call(bad)
                self.assertEqual(score, {}, f"这份输出应当收拾不出来：{bad!r}")

    def test_missing_skill_returns_empty(self):
        with mock.patch.object(llm_service, "load_skill", return_value={}):
            self.assertEqual(llm_service.score_interview("AI 应用开发", list(HISTORY)), {})


class TestStartScoring(ScoringTestCase):
    """`_start_scoring` 的接线：线程里评完要写进会话、并落一份带评分的存档。"""

    def setUp(self):
        super().setUp()
        self.session = self.make_session()
        self.session.finish()

    def test_score_is_attached_and_persisted(self):
        fake = score_guard.normalize(json.loads(GOOD_JSON))
        with mock.patch.object(cloud_app, "score_interview", return_value=fake):
            thread = cloud_app._start_scoring(SID)
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive(), "评分线程没在超时内结束")
        self.assertEqual(self.session.score, fake)

        # 落盘那份也要带上评分 —— 否则重启之后网页上的分数就没了
        saved = session_store.load(SID)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["score"], fake)

    def test_empty_score_leaves_session_untouched(self):
        with mock.patch.object(cloud_app, "score_interview", return_value={}):
            cloud_app._start_scoring(SID).join(timeout=10)
        self.assertIsNone(self.session.score)
        self.assertIsNone(session_store.load(SID), "没评出分就不该多写一份存档")

    def test_exception_is_swallowed(self):
        """评分是锦上添花 —— 它炸了不能影响一场已经完成的面试。"""
        with mock.patch.object(cloud_app, "score_interview",
                               side_effect=RuntimeError("模型挂了")):
            cloud_app._start_scoring(SID).join(timeout=10)      # 不该抛出来
        self.assertIsNone(self.session.score)

    def test_unknown_session_is_noop(self):
        cloud_app._start_scoring("no-such-session").join(timeout=10)


class TestDeviceProtocolUnchanged(ScoringTestCase):
    """⚠️ 本轮最要紧的一条：**评分绝不能混进端侧那条链路**。

    做法是把三个 service 与评分函数全打桩，然后看 `/api/interview` 到底返回了哪些
    字段 —— 只要多出一个（比如 score），板子那条路就不再是"只加不改"的了。
    """

    DEVICE_FIELDS = {"type", "text", "tts_audio", "session_id", "next_action", "user_text"}

    def post_once(self, next_action):
        llm_reply = {"text": "这是一句回复。", "next_action": next_action}
        with mock.patch.object(cloud_app, "asr_audio_to_text", return_value="候选人说的话"), \
             mock.patch.object(cloud_app, "llm_interview", return_value=llm_reply), \
             mock.patch.object(cloud_app, "tts_text_to_audio", return_value="ZmFrZQ=="), \
             mock.patch.object(cloud_app, "_start_scoring") as scoring:
            response = cloud_app.app.test_client().post("/api/interview", json={
                "session_id": SID, "role": "AI 应用开发",
                "state": "recording_finished", "audio": "ZmFrZQ==", "audio_format": "wav",
            })
        return response, scoring

    def test_response_fields_are_exactly_the_agreed_six(self):
        response, _ = self.post_once("continue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.get_json().keys()), self.DEVICE_FIELDS)

    def test_report_round_still_returns_the_same_six(self):
        """收官那一轮也一样 —— 它多了一个"起线程评分"的动作，但响应体不许变。"""
        response, _ = self.post_once("finish")
        self.assertEqual(set(response.get_json().keys()), self.DEVICE_FIELDS)

    def test_scoring_starts_only_on_the_report_round(self):
        _, scoring = self.post_once("continue")
        self.assertEqual(scoring.call_count, 0, "没结束的轮次不该去评分（白花钱）")

        cloud_app.session_manager.sessions.clear()
        _, scoring = self.post_once("finish")
        self.assertEqual(scoring.call_count, 1, "报告轮必须发起一次评分")


if __name__ == "__main__":
    unittest.main(verbosity=2)
