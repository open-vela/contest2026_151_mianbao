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
import interview_stage         # noqa: E402
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


class TestQaPairs(unittest.TestCase):
    """把对话历史配成编号问答 —— 逐题复盘的地基。"""

    def test_first_question_is_the_backfilled_opening(self):
        """⚠️ 设备上**并没有问过**第 1 题：候选人按 K1 直接开口，面试官才回应。
        回填一句标准开场白，复盘才读得通（见 score_guard.OPENING_QUESTION）。"""
        pairs = llm_service._qa_pairs([
            {"role": "user", "content": "我叫李浩。"},
            {"role": "assistant", "content": "能说说那个系统吗？"},
            {"role": "user", "content": "是个客服知识库。"},
        ])
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["question"], score_guard.OPENING_QUESTION)
        self.assertEqual(pairs[0]["answer"], "我叫李浩。")
        self.assertEqual(pairs[1]["question"], "能说说那个系统吗？")
        self.assertEqual(pairs[1]["answer"], "是个客服知识库。")

    def test_report_is_never_used_as_a_question(self):
        """报告是历史里最后一条 assistant 消息，但它不是"下一题"。"""
        pairs = llm_service._qa_pairs([
            {"role": "user", "content": "答案"},
            {"role": "assistant", "content": "候选人整体表现不佳…"},   # 报告
        ])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["question"], score_guard.OPENING_QUESTION)

    def test_ignores_malformed_and_empty(self):
        pairs = llm_service._qa_pairs([None, 42, {"role": "user", "content": "   "},
                                       {"role": "user", "content": "真的回答"}])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["answer"], "真的回答")

    def test_empty_or_bad_history(self):
        for bad in (None, [], "字符串"):
            with self.subTest(history=bad):
                self.assertEqual(llm_service._qa_pairs(bad), [])

    def test_block_contains_every_pair(self):
        pairs = llm_service._qa_pairs([
            {"role": "user", "content": "答案一"},
            {"role": "assistant", "content": "第二题？"},
            {"role": "user", "content": "答案二"},
        ])
        block = llm_service._qa_block(pairs)
        for text in ("第 1 题", "第 2 题", "答案一", "答案二", "第二题？"):
            self.assertIn(text, block)


class TestAttachQuestions(unittest.TestCase):
    def setUp(self):
        self.pairs = [{"index": 1, "question": "开场", "answer": "a"},
                      {"index": 2, "question": "第二题", "answer": "b"}]

    def test_attaches_the_question_text(self):
        got = llm_service._attach_questions(
            [{"index": 2, "evidence": "e", "suggestion": "s"}], self.pairs)
        self.assertEqual(got, [{"index": 2, "question": "第二题",
                                "evidence": "e", "suggestion": "s"}])

    def test_out_of_range_index_is_dropped(self):
        """闸门不知道这场有几题，范围只能在这里卡。"""
        self.assertEqual(
            llm_service._attach_questions([{"index": 99, "suggestion": "s"}], self.pairs), [])

    def test_bad_shapes(self):
        for bad in (None, [], "x", [None, 42, "字符串"]):
            with self.subTest(items=bad):
                self.assertEqual(llm_service._attach_questions(bad, self.pairs), [])


class TestScoreInterviewWithPerQuestion(ScoringTestCase):
    """端到端（打桩）：`score_interview` 要把逐题复盘配好、挂上题目、丢掉越界的。"""

    REPLY = json.dumps({
        "dimensions": [{"name": n, "score": 7, "evidence": "混合召回", "comment": "还行"}
                       for n in score_guard.DIMENSIONS],
        "summary": "整体尚可。",
        "per_question": [
            {"index": 1, "evidence": "我叫李浩", "suggestion": "补一句最近做的事"},
            {"index": 99, "evidence": "不存在", "suggestion": "越界，应被丢掉"},
            {"index": 2, "evidence": "重复", "suggestion": "重复题号，只留第一条"},
            {"index": 3, "evidence": "没给建议"},
        ],
    }, ensure_ascii=False)

    def test_questions_are_attached_and_bad_ones_dropped(self):
        with mock.patch.object(llm_service, "call_llm", return_value=self.REPLY) as patched:
            score = llm_service.score_interview("AI 应用开发", list(HISTORY))

        # HISTORY 里只有一条候选人发言 → 只有第 1 题；越界/重复/没建议的都该没了
        self.assertEqual([q["index"] for q in score["per_question"]], [1])
        # ⚠️ 这条 HISTORY 是**以面试官的话开头**的，所以配到的是那句真问题，
        #    而不是回填的开场白（回填只用在"候选人先开口"那条路上，见下一个用例）
        self.assertEqual(score["per_question"][0]["question"], "请介绍一下你自己。")
        self.assertEqual(score["per_question"][0]["suggestion"], "补一句最近做的事")

        # 喂给模型的是编号清单，而不是"整场对话原样"
        sent = patched.call_args.kwargs["messages"][0]["content"]
        self.assertIn("第 1 题", sent)
        self.assertIn("请介绍一下你自己。", sent)
        self.assertIn("向量数据库", sent)

    def test_opening_is_backfilled_when_the_candidate_spoke_first(self):
        """真实端侧的流程：候选人按 K1 直接开口，面试官才回应 —— 第 1 题没有前置问题，
        用回填的开场白补上（否则复盘第一行是空的）。"""
        with mock.patch.object(llm_service, "call_llm", return_value=self.REPLY):
            score = llm_service.score_interview(
                "AI 应用开发", [{"role": "user", "content": "我叫李浩。"}])
        self.assertEqual(score["per_question"][0]["question"], score_guard.OPENING_QUESTION)

    def test_no_candidate_speech_means_no_call(self):
        """历史里全是面试官的话（没有候选人发言）→ 没有可评的东西，别浪费一次调用。"""
        with mock.patch.object(llm_service, "call_llm") as patched:
            score = llm_service.score_interview(
                "AI 应用开发", [{"role": "assistant", "content": "请介绍一下你自己。"}])
        self.assertEqual(score, {})
        self.assertEqual(patched.call_count, 0)

    def test_report_is_not_fed_to_the_scorer(self):
        """报告在历史末尾 —— 但它**不该进评分输入**：评的是问答，不是自己的结论。"""
        with mock.patch.object(llm_service, "call_llm", return_value=self.REPLY) as patched:
            llm_service.score_interview("AI 应用开发", list(HISTORY) + [
                {"role": "assistant", "content": "这是报告正文，不该出现在评分输入里。"}])
        sent = patched.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("这是报告正文", sent)


class TestStageInjection(unittest.TestCase):
    """`next_question` 按轮次注入【当前阶段】，并且**只在技术段**给题库参考块。"""

    QUERY = "我用向量数据库做检索，召回率提升到 92%。"
    BLOCK_HEADER = "【本轮参考题"

    def ask_kwargs(self, round_number, reply="一句问话？"):
        """造一场到第 N 轮为止的历史，调一次 next_question，拿回 call_llm 的完整入参。"""
        history = []
        for r in range(1, round_number):
            history.append({"role": "user", "content": f"第 {r} 轮回答：{self.QUERY}"})
            history.append({"role": "assistant", "content": f"第 {r} 轮的追问？"})
        history.append({"role": "user", "content": self.QUERY})
        with mock.patch.object(llm_service, "call_llm", return_value=reply) as patched:
            llm_service.next_question("AI 应用开发", history[:-1], self.QUERY)
        return patched.call_args.kwargs

    def ask(self, round_number):
        return self.ask_kwargs(round_number)["system_prompt"]

    def test_每轮注入的是它那一段(self):
        for round_number, name in ((1, "开场"), (2, "背景深挖"),
                                   (3, "背景深挖"), (5, "技术问答"),
                                   (9, "技术问答"), (10, "反问环节")):
            with self.subTest(round=round_number):
                self.assertIn(f"【当前阶段：{name}】", self.ask(round_number))

    def test_参考块只在技术段出现(self):
        """背景深挖问的是他自己的项目，题库帮不上忙 —— 注进去只会把话题拽走。"""
        self.assertNotIn(self.BLOCK_HEADER, self.ask(1), "开场不该有参考题")
        self.assertNotIn(self.BLOCK_HEADER, self.ask(2), "背景深挖不该有参考题")
        self.assertIn(self.BLOCK_HEADER, self.ask(5), "技术问答段应当注入参考题")
        self.assertNotIn(self.BLOCK_HEADER, self.ask(10), "反问环节不该有参考题")

    def test_开场那一段明确说了不要再让他自我介绍(self):
        """真实数据里出现过：候选人一开口就自报家门，面试官却又让他"介绍一下自己"。
        这一段就是冲着那个来的。"""
        self.assertIn("不要再请他「介绍一下自己」", self.ask(1))

    def test_硬性要求仍在提示词末尾(self):
        """⚠️ §11.20 的修复靠它留在结尾（recency）。加了阶段块之后也得在。"""
        for round_number in (1, 5, 10):
            with self.subTest(round=round_number):
                self.assertTrue(self.ask(round_number).rstrip().endswith(
                    "遇到的最大挑战吗？"), "【硬性要求】不再位于提示词末尾")

    def test_占位符都替换干净了(self):
        for round_number in (1, 5, 10):
            with self.subTest(round=round_number):
                prompt = self.ask(round_number)
                for placeholder in ("{stage_block}", "{reference_block}", "{role}"):
                    self.assertNotIn(placeholder, prompt, f"{placeholder} 没被替换掉")

    def test_本轮_user_消息末尾也带着阶段要求(self):
        """★ 这是 2026-10-01 首次排练之后补的。

        只把阶段写进 system prompt **中段**挡不住历史势头：那次前十轮都在追项目，
        模型在技术段、反问段**都继续追项目**（参考题明明注进去了，245~278 字）。
        brief 就是为了占住"离下一句最近"的那个位置。
        """
        # 断言的是**行为要求**（那几句是不能丢的保证），不是措辞本身 ——
        # 措辞可以改，这几条要求改了就得回来改测试。
        for round_number, fragment in ((1, "不要再让他自我介绍"),
                                       (5, "不要只围着他那个项目问"),
                                       (10, "只问这一句")):
            with self.subTest(round=round_number):
                last = self.ask_kwargs(round_number)["messages"][-1]["content"]
                self.assertIn("候选人回答：", last, "末尾那条不该丢掉候选人的回答")
                self.assertIn(f"第 {round_number} 轮", last)
                self.assertIn(fragment, last, "本轮的阶段要求没带上")


class TestAskBackFallback(unittest.TestCase):
    """反问环节：模型没问出「有什么想做的吗」时，**代码**换成固定问句。

    同 reply_guard / report_guard 的取舍 —— 提示词劝不住的在代码里拦。
    """

    def run_round(self, round_number, reply):
        history = []
        for r in range(1, round_number):
            history.append({"role": "user", "content": f"第 {r} 轮回答"})
            history.append({"role": "assistant", "content": f"第 {r} 轮的追问？"})
        history.append({"role": "user", "content": "本轮回答"})
        with mock.patch.object(llm_service, "call_llm", return_value=reply):
            return llm_service.next_question("AI 应用开发", history[:-1], "本轮回答")

    def test_没问出想问就换成固定句(self):
        out = self.run_round(10, "那你们线上有没有做答案质量的监控？")
        self.assertEqual(out["text"], interview_stage.ASK_BACK_FALLBACK)
        self.assertEqual(out["next_action"], "continue")

    def test_正常问出想问就原样保留(self):
        reply = "我的问题问完了，您有什么想问我的吗？"
        self.assertEqual(self.run_round(10, reply)["text"], reply)

    def test_别的轮次不受影响(self):
        """兜底只在反问那一轮生效 —— 别把技术轮的正常追问也换掉。"""
        reply = "那你们线上有没有做答案质量的监控？"
        self.assertEqual(self.run_round(5, reply)["text"], reply)


if __name__ == "__main__":
    unittest.main(verbosity=2)
