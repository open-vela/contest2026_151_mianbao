"""`cloud/question_bank.py` 的离线单测。

跑法（**不联网、不需要 MIMO_API_KEY、不依赖 Flask**）：
    python3 cloud/test_question_bank.py
或在 cloud/ 目录下：
    python3 -m unittest test_question_bank -v
"""
import ast
import json
import logging
import pathlib
import re
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import question_bank as qb

# 被测模块的源码（用于「只依赖标准库」与「不用 glob」两条断言）
SOURCE_PATH = pathlib.Path(qb.__file__).resolve()
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")

# 允许 import 的顶层模块 —— 这份名单就是"离线可测"的保证
ALLOWED_IMPORTS = {"json", "logging", "pathlib", "re", "threading", "unicodedata"}

# 三个中文岗位的题数（与 question_bank/README.md 的出处表一致）
ZH_ROLE_COUNTS = {"AI 应用开发": 748, "AI Agent 开发": 315, "大模型算法工程师": 120}
EN_ROLE_COUNTS = {"AI/ML Engineer": 576, "Data Scientist": 495, "Data Analyst": 576}

# 演示岗位 + 每个题库岗位都要过一遍，防止某个岗位的数据把块撑爆
ALL_ROLES = list(ZH_ROLE_COUNTS) + list(EN_ROLE_COUNTS)

# 像"真人回答"的检索词（真实链路里这是候选人的 ASR 结果）
SAMPLE_ANSWER = "我负责检索这块，用向量数据库做知识库召回，重排模型用的是 bge-reranker，上线后缓存把延迟降到了两百毫秒。"


def setUpModule():
    """单测里把 INFO 日志静音，只留 WARNING 以上。"""
    logging.getLogger("question_bank").setLevel(logging.WARNING)


class TestBankLoading(unittest.TestCase):
    def test_record_count_and_roles(self):
        bank = qb.load_bank()
        self.assertEqual(len(bank), 2830, "题库总数应为 1183(zh) + 1647(en)")
        counts = {}
        for record in bank:
            role = record["role"]
            counts[role] = counts.get(role, 0) + 1
        for role, expected in {**ZH_ROLE_COUNTS, **EN_ROLE_COUNTS}.items():
            self.assertEqual(counts.get(role), expected, f"{role} 题数不符")

    def test_whitelist_ignores_stray_json(self):
        """白名单的关键性质：data/ 里多出来的 JSON 不能被吃进题库。

        导入脚本会写出 fe_questions.json（6160 道前端题），上游用 glob("*.json")
        会把它一起加载进来、把 AI 题淹没。这里用临时目录实跑一遍验证。
        """
        stray = [{"question": "什么是前端盒模型", "keywords": [], "role": "前端工程师",
                  "category": "css", "level": "", "stage": ""}]
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for name in qb.BANK_FILES:
                (root / name).write_text(
                    json.dumps([{"question": f"{name} 的题", "keywords": [], "role": "AI 应用开发",
                                 "category": "x", "level": "", "stage": ""}], ensure_ascii=False),
                    encoding="utf-8")
            (root / "fe_questions.json").write_text(
                json.dumps(stray, ensure_ascii=False), encoding="utf-8")
            saved_dir, saved_cache = qb.BANK_DIR, qb._BANK_CACHE
            try:
                qb.BANK_DIR = root
                qb._BANK_CACHE = None
                loaded = qb.load_bank()
                self.assertEqual(len(loaded), len(qb.BANK_FILES),
                                 "只有白名单里的文件该被加载，fe_questions.json 必须被忽略")
                self.assertNotIn("前端", {r["question"] for r in loaded})
            finally:
                qb.BANK_DIR, qb._BANK_CACHE = saved_dir, saved_cache

    def test_missing_dir_degrades_without_raising(self):
        """题库整个目录缺失时：不抛异常、返回空库、参考块为空。"""
        saved_dir, saved_cache = qb.BANK_DIR, qb._BANK_CACHE
        try:
            qb.BANK_DIR = pathlib.Path(tempfile.gettempdir()) / "不存在的题库目录_xyz"
            qb._BANK_CACHE = None
            self.assertEqual(qb.load_bank(), [])
            self.assertEqual(qb.build_reference_block("AI 应用开发", "随便答"), "")
            self.assertEqual(qb.search_questions("RAG"), [])
        finally:
            qb.BANK_DIR, qb._BANK_CACHE = saved_dir, saved_cache
            qb.load_bank()          # 恢复真缓存

    def test_stdlib_only(self):
        """只依赖标准库 —— 否则这个文件没法脱网直跑。"""
        tree = ast.parse(SOURCE)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= ALLOWED_IMPORTS,
                        f"出现了非白名单 import：{sorted(imported - ALLOWED_IMPORTS)}")
        for forbidden in ("openai", "flask", "requests"):
            self.assertNotIn(forbidden, imported)

    def test_no_glob_in_source(self):
        """§11.21 的安全设计：用白名单，不用 glob("*.json")。

        用 AST 找真正的调用（不能对源码做子串匹配 —— 模块 docstring 里
        就写着 `glob("*.json")` 这五个字，会把自己测挂）。
        """
        offenders = []
        for node in ast.walk(ast.parse(SOURCE)):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "glob":
                    offenders.append(f"第 {node.lineno} 行 glob()")
                elif isinstance(func, ast.Attribute) and func.attr == "glob":
                    offenders.append(f"第 {node.lineno} 行 *.glob()")
        self.assertEqual(offenders, [], "必须用 BANK_FILES 白名单，不能扫目录")


class TestCacheIntegrity(unittest.TestCase):
    def test_cache_not_polluted_by_sorting(self):
        """排序必须在副本上做：检索跑一轮后缓存顺序与内容都不能变。"""
        bank = qb.load_bank()
        before = [(r["question"], r["role"], r["category"]) for r in bank[:50]]
        self.assertIs(qb.load_bank(), bank, "缓存应返回同一个对象")
        for round_index in range(10):
            qb.search_questions(SAMPLE_ANSWER, role="AI 应用开发")
            qb.pick_candidates("AI 应用开发", SAMPLE_ANSWER, "之前问过的题", round_index)
            qb.build_reference_block("Data Scientist", SAMPLE_ANSWER, "", round_index)
        after = [(r["question"], r["role"], r["category"]) for r in bank[:50]]
        self.assertEqual(before, after, "缓存被就地排序污染了")

    def test_concurrent_load_is_single_and_stable(self):
        """双检锁：并发首载只加载一次，所有线程拿到同一个对象。"""
        saved_cache = qb._BANK_CACHE
        qb._BANK_CACHE = None
        results, errors = [], []

        def worker():
            try:
                results.append(qb.load_bank())
            except Exception as error:       # pragma: no cover - 失败即测试失败
                errors.append(error)

        try:
            threads = [threading.Thread(target=worker) for _ in range(16)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 16)
            self.assertEqual(len({id(r) for r in results}), 1, "并发加载产生了多个缓存对象")
            self.assertEqual(len(results[0]), 2830)
        finally:
            qb._BANK_CACHE = saved_cache


class TestRoleMapping(unittest.TestCase):
    def test_alias_targets_are_real_roles(self):
        """别名表的目标必须是题库里真实存在的岗位名 —— 写错会静默失效。"""
        roles = set(qb.bank_roles())
        for alias, target in qb.ROLE_ALIASES.items():
            self.assertIn(target, roles, f"别名 {alias} 指向了不存在的岗位 {target}")
            self.assertEqual(qb.normalize_role(alias), target)

    def test_normalize_role(self):
        cases = {
            "AI 应用开发": "AI 应用开发",
            "AI应用开发": "AI 应用开发",           # 题库岗位名带空格，必须吃掉
            "ai应用开发": "AI 应用开发",
            "ＡＩ应用开发": "AI 应用开发",          # NFKC 全角
            " AI 应用开发 ": "AI 应用开发",
            '"AI 应用开发"': "AI 应用开发",
            "AI Agent 开发": "AI Agent 开发",
            "AI Agent开发": "AI Agent 开发",
            "大模型算法工程师": "大模型算法工程师",
            "算法工程师": "大模型算法工程师",
            "ai/ml engineer": "AI/ML Engineer",
            "AI/ML Engineer": "AI/ML Engineer",
            "数据分析师": "Data Analyst",
            "数据科学家": "Data Scientist",
            "AI 应用开发工程师": "AI 应用开发",     # 双向包含
        }
        for raw, expected in cases.items():
            self.assertEqual(qb.normalize_role(raw), expected, f"normalize_role({raw!r})")
        # 题库里没有的岗位必须落空 —— 这是"退化为自由提问"的触发条件
        for unmapped in ("产品经理", "前端工程师", "架构师", "", "   ", "Java 开发"):
            self.assertEqual(qb.normalize_role(unmapped), "", f"{unmapped!r} 不该命中题库")

    def test_unmapped_role_yields_empty_block(self):
        """落空岗位 → 空块 → 提示词与没有题库时逐字节相同。"""
        for role in ("产品经理", "前端工程师", ""):
            self.assertEqual(qb.build_reference_block(role, SAMPLE_ANSWER, "", 3), "")
            self.assertEqual(qb.pick_candidates(role, SAMPLE_ANSWER, "", 3), [])


class TestSearch(unittest.TestCase):
    def test_hits_are_relevant(self):
        hits = qb.search_questions("向量数据库 检索", role="AI 应用开发", limit=5)
        self.assertTrue(hits, "应当能搜到向量数据库相关题目")
        for record in hits:
            self.assertEqual(record["role"], "AI 应用开发", "role 过滤必须生效")

    def test_filters_are_case_insensitive_substrings(self):
        hits = qb.search_questions("", role="AI/ML Engineer", category="system design", limit=10)
        self.assertTrue(hits)
        for record in hits:
            self.assertIn("system design", record["category"].lower())

    def test_level_filter_only_works_for_english(self):
        self.assertTrue(qb.search_questions("", role="AI/ML Engineer", level="Level 1", limit=5))
        # 中文题库 level 全空 —— 传了会一道都搜不到，这是文档里写明的已知行为
        self.assertEqual(qb.search_questions("", role="AI 应用开发", level="Level 1"), [])

    def test_unknown_role_returns_empty(self):
        self.assertEqual(qb.search_questions("RAG", role="产品经理"), [])

    def test_limit_is_clamped(self):
        self.assertLessEqual(len(qb.search_questions("", role="AI 应用开发", limit=999)), 10)


class TestDeterminismAndBudget(unittest.TestCase):
    def test_same_input_three_times_identical(self):
        """确定性：同一输入连算三次必须逐字相同（否则单测会漂、A/B 不可复现）。"""
        asked = "请介绍一下你自己。你刚才提到了 RAG，展开讲讲。"
        for round_index in (0, 3, 9):
            blocks = [qb.build_reference_block("AI 应用开发", SAMPLE_ANSWER, asked, round_index)
                      for _ in range(3)]
            self.assertEqual(blocks[0], blocks[1])
            self.assertEqual(blocks[1], blocks[2])
            self.assertTrue(blocks[0])
            picks = [qb.pick_candidates("AI 应用开发", SAMPLE_ANSWER, asked, round_index)]
            picks.append(qb.pick_candidates("AI 应用开发", SAMPLE_ANSWER, asked, round_index))
            self.assertEqual([r["question"] for r in picks[0]],
                             [r["question"] for r in picks[1]])

    def test_block_within_hard_limit_all_roles_all_rounds(self):
        """3 岗位 × 10 轮块长恒 ≤ 400 —— 这是端侧 8MiB 缓冲的第一道保险。"""
        worst = ("", 0)
        for role in ALL_ROLES:
            for round_index in range(10):
                for query in (SAMPLE_ANSWER, "", "你好"):
                    block = qb.build_reference_block(role, query, "之前问过的题", round_index)
                    self.assertLessEqual(len(block), qb.MAX_BLOCK_CHARS,
                                         f"{role} 第 {round_index} 轮超限：{len(block)}")
                    if len(block) > worst[1]:
                        worst = (f"{role}/轮{round_index}", len(block))
        self.assertLess(worst[1], qb.MAX_BLOCK_CHARS * 0.9,
                        f"最坏块长 {worst} 离上限太近，余量不足")

    def test_block_has_no_markdown(self):
        """块里不能出现 Markdown —— 它在 system prompt 里，模型可能照抄到输出中，
        而输出会被 TTS 逐字念出来。"""
        for role in ALL_ROLES:
            block = qb.build_reference_block(role, SAMPLE_ANSWER, "", 2)
            for token in ("**", "##", "|---", "```"):
                self.assertNotIn(token, block, f"{role} 的参考块含 Markdown：{token}")

    def test_question_clipping(self):
        self.assertEqual(qb._clip_question("短题干", 60), "短题干")
        clipped = qb._clip_question("x" * 200, 60)
        self.assertLessEqual(len(clipped), 60)
        self.assertTrue(clipped.endswith("…"))
        # 英文按词边界退：去掉省略号后必须是原文的前缀，且断点正好落在空格处
        # （否则就是 `...fraud dete…` 这种切在单词中间的结果）
        source = "You are working on a critical fraud detection model today"
        english = qb._clip_question(source, 30)
        self.assertTrue(english.endswith("…"))
        head = english[:-1].rstrip()
        self.assertTrue(source.startswith(head), f"{english!r} 不是原文前缀")
        self.assertEqual(source[len(head)], " ", f"{english!r} 切在了单词中间")
        self.assertEqual(qb._clip_question("任何", 1), "")


class TestRotationCoverage(unittest.TestCase):
    def test_rotation_covers_multiple_categories(self):
        """命中不足时靠类目轮换补足：一场面试的类目必须铺开，不能十轮同一个话题。"""
        categories = []
        for round_index in range(10):
            picks = qb.pick_candidates("AI 应用开发", "", "", round_index)
            self.assertTrue(picks)
            categories.extend(record["category"] for record in picks)
        distinct = set(categories)
        self.assertGreaterEqual(len(distinct), 8, f"10 轮只覆盖了 {len(distinct)} 个类目")
        self.assertTrue(any("系统设计" in category for category in distinct),
                        "轮换没有覆盖到系统设计类")
        self.assertTrue(any(category == "Python" for category in distinct),
                        "轮换没有覆盖到编码/基础类（Python）")

    def test_asked_questions_are_avoided(self):
        """已问过的原题不该再被选中（逐字复用场景）。"""
        asked = qb.pick_candidates("AI 应用开发", "", "", 0)
        asked_text = " ".join(record["question"] for record in asked)
        again = qb.pick_candidates("AI 应用开发", "", asked_text, 0)
        overlap = {r["question"] for r in again} & {r["question"] for r in asked}
        self.assertFalse(overlap, f"重复选中了已问题目：{overlap}")

    def test_all_english_questions_are_clipped(self):
        """英文题干全部超 60 字 —— 参考块里只能是"选题方向"，绝不能当原文念。"""
        block = qb.build_reference_block(
            "AI/ML Engineer", "We deployed a transformer model with TensorFlow Serving.", "", 4)
        self.assertTrue(block)
        for line in block.splitlines():
            self.assertLessEqual(len(line), qb.MAX_BLOCK_CHARS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
