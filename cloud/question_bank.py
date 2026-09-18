"""面试题库检索层 —— 离线、纯标准库、确定性。

给 `llm_service.next_question()` 提供「本轮参考题」文本块，注入到 system prompt 里
当选题方向（**绝不进 history**）。题库与出处见 `../question_bank/README.md`。

设计约束（都是踩过坑换来的，改之前先读 `../documents/progress_audit_2026-09-11.md` §11.21）：

1. **只依赖标准库**（json/logging/pathlib/re/threading/unicodedata）。
   本模块要能脱网单测（`test_question_bank.py` 直接 python3 跑），
   所以绝不 import openai / flask / requests。
2. **白名单加载 `BANK_FILES`，不用 `glob("*.json")`**。导入脚本会往 data/ 里写
   `fe_questions.json`（6160 道前端题），glob 会把它静默混进题库、淹没 AI 题。
3. **加载失败不抛异常**，只 warning 并返回空库 —— 题库缺失时全链路优雅退化为
   「自由提问」（参考块为空，提示词与没有题库时逐字节相同），不能让云端起不来。
4. **确定性**：不用 random，所有排序都带完整 tiebreaker。否则单测会漂、
   A/B 对照不可复现。
5. **缓存列表只读**：排序一律在副本上做，绝不就地 sort 缓存。
"""
import json
import logging
import pathlib
import re
import threading
import unicodedata

logger = logging.getLogger(__name__)

# 本文件在 cloud/ 下，题库在同级的 question_bank/data/
BANK_DIR = pathlib.Path(__file__).resolve().parent.parent / "question_bank" / "data"

# 白名单（见模块 docstring 第 2 条）。加数据源在这里加，不要在磁盘上乱放 JSON。
BANK_FILES = ("zh_questions.json", "ai_questions.json")

# 参考块硬上限：最坏情况下模型整段照抄 → 约 400 字 → 约 4MB TTS 音频，
# 端侧 8MiB 缓冲（CLOUD_RESP_MAX）还留一倍余量。
# 对照：不截断的英文题干 3 条约 1500 字 → 约 15MB，会直接撞死端侧。
MAX_BLOCK_CHARS = 400

# 单条题干上限。中文题库中位数 28 字，超 60 字的只有 83/1183；
# 英文题库 1647/1647 都超（中位数 508 字，多为多部分场景题），所以英文题
# 实际只能当"选题方向"用 —— 提示词里显式要求先译成中文再改写提问，禁止照读。
MAX_QUESTION_CHARS = 60

# 「理想题干长度」：40 字上下最适合口语一问一答（太短没信息量，太长念不完）。
_IDEAL_QUESTION_LEN = 40

# 类目轮换的优先级。方法论（skills/README.md「一场面试内」）要求一场面试至少覆盖
# 系统设计、编码/基础原理、行为/协作三类，但题库有 24 个类目、面试只有 10 轮，
# **纯字母序会让「Python」落在第 13 位 —— 10 轮根本轮不到**（实测过）。
# 所以把这三类顶到固定槽位：轮次 0 就能一次拿到三类，后面再按字母序轮。
_COVERAGE_PRIORITY = (
    ("系统设计", "system design", "架构设计", "architecture"),
    ("python", "coding", "编码", "基础原理", "编程"),
    ("collaboration", "conflict", "communication", "沟通", "协作", "软技能", "行为"),
)


def _ordered_categories(categories: set) -> list:
    """把类目排成「先覆盖三类、其余按字母序」的固定顺序（确定性）。

    不这么排的话，`pick_candidates` 的轮换虽然也在换类目，但换到的都是字母序靠前
    的那几个（AI Agent / AI 安全 / AI 进阶……），真正的编码题和系统设计题
    在第 10 轮之后才会出现 —— 而面试在那之前就结束了。

    每组**全部**命中类目都排进去（不只第一个）：`AI 编程工具与自主 Coding Agent
    面试题` 按字母序比 `Python` 靠前，只取第一个的话「Python」会被挤到十几位去，
    等于没覆盖。轮换每轮取 3 个类目，所以第 0 轮就能同时拿到三类。
    """
    remaining = set(categories)
    ordered = []
    for group in _COVERAGE_PRIORITY:
        for category in sorted(c for c in remaining
                               if any(hint in c.lower() for hint in group)):
            ordered.append(category)
            remaining.discard(category)
    ordered.extend(sorted(remaining))
    return ordered

_BLOCK_HEADER = "【本轮参考题（仅供你选题方向，不要照读）】"
_BLOCK_RULES = (
    "使用要求：从上列题目里挑一道最贴合候选人刚才所说内容的，用你自己的话问出来，"
    "只问一个问题。禁止提到题库、资料、参考、上面列出的题目等字样；"
    "禁止照读原句；英文题先在心里译成中文再改写提问；"
    "上列题目都不合适就自己出一道，不要勉强套用。"
)

# 岗位别名 → 题库里的真实岗位名。
# ⚠️ 目标必须是题库里真实存在的 role 字符串（test_question_bank.py 会断言），
# 写错不会报错、只会静默退化成自由提问。
ROLE_ALIASES = {
    # AI 应用开发（本次演示岗位）
    "ai开发": "AI 应用开发",
    "ai应用": "AI 应用开发",
    "ai应用开发工程师": "AI 应用开发",
    "应用开发工程师": "AI 应用开发",
    "ai工程师": "AI 应用开发",
    "大模型应用开发": "AI 应用开发",
    # AI Agent 开发
    "agent开发": "AI Agent 开发",
    "aiagent": "AI Agent 开发",
    "aiagent工程师": "AI Agent 开发",
    "智能体开发": "AI Agent 开发",
    "智能体工程师": "AI Agent 开发",
    # 大模型算法工程师
    "大模型算法": "大模型算法工程师",
    "算法工程师": "大模型算法工程师",
    "llm算法工程师": "大模型算法工程师",
    "大模型工程师": "大模型算法工程师",
    # 英文侧（ai_questions.json 的三个岗位）
    "aimlengineer": "AI/ML Engineer",
    "ai/ml": "AI/ML Engineer",
    "mlengineer": "AI/ML Engineer",
    "machinelearningengineer": "AI/ML Engineer",
    "机器学习工程师": "AI/ML Engineer",
    "datascientist": "Data Scientist",
    "数据科学家": "Data Scientist",
    "dataanalyst": "Data Analyst",
    "数据分析师": "Data Analyst",
    "数据分析": "Data Analyst",
}

_BANK_LOCK = threading.Lock()
_BANK_CACHE = None          # list[dict] | None，None 表示尚未加载
_ROLE_MAP = None            # dict[str, str]  归一化岗位名 → 题库真实岗位名


# ============================================================
# 内部工具
# ============================================================

def _norm_key(text: str) -> str:
    """岗位名归一化：NFKC（全角→半角）→ 去空白与引号 → 转小写。

    题库里的岗位名带空格（`AI 应用开发`），而调用方可能传 `AI应用开发`，
    两边都过这个函数才能对齐。`产品经理` 这类题库里没有的岗位会落空——
    这是**预期行为**（退化为自由提问），不是 bug。
    """
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = re.sub(r"[\s　]+", "", text)
    text = text.strip("\"'“”‘’`")
    return text.lower()


def _text_terms(text: str) -> set:
    """切词：ASCII 词保留整词；中文没有空格，拆成相邻 2 字的二元组。

    与上游 myagent 的 `_text_terms` 同源。中文二元组会带来一些假命中
    （「前端」会命中任何含「前」「端」相邻的句子），但配合岗位过滤与
    确定性排序，实测足以选出可用题目。
    """
    terms = set(re.findall(r"[a-z0-9_]{3,}", text.lower()))
    for run in re.findall(r"[一-鿿]+", text):
        terms.update(run[i:i + 2] for i in range(len(run) - 1))
    return terms


def _question_of(record: dict) -> str:
    return str(record.get("question", "")).strip()


def _role_of(record: dict) -> str:
    return str(record.get("role", "")).strip()


def _pick_key(record: dict):
    """确定性排序键：优先 40 字上下，其次短句，最后用题干本身兜底。

    最后那项是必需的 —— 没有它，长度相同的两条题在集合遍历顺序变化时
    会排出不同结果，单测就漂了。
    """
    question = _question_of(record)
    return (abs(len(question) - _IDEAL_QUESTION_LEN), len(question), question)


def _score_records(records: list, query: str) -> list:
    """按关键词重合度打分。只看题干 + keywords，**刻意不看 role/category/stage**。

    那三个字段已经在过滤阶段用过；再参与打分会让筛选词反过来淹没结果——
    query 里只要有「前端」这个二元组，该岗位下几千道题就全部命中得 1 分。
    """
    terms = _text_terms(query) if query.strip() else set()
    scored = []
    for record in records:
        keywords = record.get("keywords") or []
        haystack = f"{_question_of(record)} {' '.join(map(str, keywords))}".lower()
        score = sum(1 for term in terms if term in haystack) if terms else 1
        if score:
            scored.append((score, record))
    # 分数高的在前；同分按 _pick_key 排，保证确定性
    scored.sort(key=lambda item: (-item[0],) + _pick_key(item[1]))
    return [record for _score, record in scored]


def _load_locked() -> list:
    """真正的加载逻辑，调用方必须已持有 _BANK_LOCK。"""
    global _ROLE_MAP
    records = []
    role_map = {}
    for name in BANK_FILES:
        path = BANK_DIR / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            # 不抛异常：题库是锦上添花，缺了要能退化成自由提问（docstring 第 3 条）
            logger.warning(f"[题库] {name} 加载失败，跳过：{error}")
            continue
        if not isinstance(data, list):
            logger.warning(f"[题库] {name} 顶层不是 JSON 数组，跳过")
            continue
        records.extend(data)
        for record in data:
            if isinstance(record, dict):
                role = _role_of(record)
                if role:
                    role_map.setdefault(_norm_key(role), role)
    _ROLE_MAP = role_map
    if records:
        logger.info(f"[题库] 已加载 {len(records)} 道题"
                    f"（{len(BANK_FILES)} 个文件，{len(role_map)} 个岗位）")
    else:
        logger.warning(f"[题库] 空库 —— 目录 {BANK_DIR} 下没有可用数据，"
                       f"面试将退化为自由提问（不注入参考题）")
    return records


# ============================================================
# 公开 API
# ============================================================

def warmup() -> dict:
    """预加载题库并返回摘要（供 app.py 启动时调用一次并打日志）。

    Flask dev server 默认多线程，第一次请求进来时再加载会有并发竞争；
    启动时预热一次，之后就只读缓存了。**永不抛异常。**
    """
    bank = load_bank()
    return {
        "records": len(bank),
        "roles": bank_roles(),
        "dir": str(BANK_DIR),
        "loaded": bool(bank),
    }


def load_bank() -> list:
    """返回题库缓存（**只读**，调用方不得修改）。

    双检锁：多线程下只会真正加载一次。加载失败返回 `[]`，不抛异常。
    """
    global _BANK_CACHE
    if _BANK_CACHE is None:
        with _BANK_LOCK:
            if _BANK_CACHE is None:
                _BANK_CACHE = _load_locked()
    return _BANK_CACHE


def bank_roles() -> list:
    """题库里真实存在的岗位名（排序，供日志与单测用）。"""
    load_bank()
    return sorted(set((_ROLE_MAP or {}).values()))


def normalize_role(role: str) -> str:
    """把调用方给的岗位名映射到题库里的真实岗位名；落空返回 `""`。

    四步（顺序不能换）：
      ① 归一化后精确命中题库 role；
      ② 别名表 `ROLE_ALIASES`；
      ③ 双向包含取最长（`AI 应用开发工程师` 能命中 `AI 应用开发`）；
      ④ 落空返回 "" —— 调用方据此判定"该岗位没有题库"，退化为自由提问。
    """
    key = _norm_key(role)
    if not key:
        return ""
    load_bank()                       # 确保 _ROLE_MAP 已就绪
    role_map = _ROLE_MAP or {}
    if key in role_map:               # ①
        return role_map[key]
    if key in ROLE_ALIASES:           # ②（目标合法性由单测保证）
        return ROLE_ALIASES[key]
    # ③ 双向包含：谁的岗位名更长用谁的（`大模型算法工程师` 优先于 `算法工程师`）
    best = ""
    for candidate in role_map:
        if key in candidate or candidate in key:
            if len(candidate) > len(best):
                best = candidate
    return role_map.get(best, "")


def search_questions(query: str, role: str = "", category: str = "",
                     level: str = "", stage: str = "", limit: int = 5) -> list:
    """按关键词 + 过滤条件检索，返回**记录列表**（不是给模型看的文本）。

    过滤条件均为「忽略大小写的子串匹配」，与上游 myagent 的 `search_questions`
    语义一致。`role` 会先过 `normalize_role`，所以 `AI应用开发` 与 `AI 应用开发`
    都能用；传了 role 却映射不到题库岗位时返回空列表。

    ⚠️ 与上游的差别：去掉了 `@beta_tool` 装饰器（那是给 agent 运行时用的），
    返回结构化的记录列表而不是拼好的文本 —— 由调用方决定怎么呈现。
    """
    records = load_bank()
    if not records:
        return []
    pool = records
    if role:
        canonical = normalize_role(role)
        if not canonical:
            return []
        role_key = _norm_key(canonical)
        pool = [r for r in pool if _norm_key(_role_of(r)) == role_key]
    if category:
        needle = category.lower()
        pool = [r for r in pool if needle in str(r.get("category", "")).lower()]
    if level:
        needle = level.lower()
        pool = [r for r in pool if needle in str(r.get("level", "")).lower()]
    if stage:
        needle = stage.lower()
        pool = [r for r in pool if needle in str(r.get("stage", "")).lower()]
    if not pool:
        return []
    hits = _score_records(pool, query)
    return hits[:max(1, min(int(limit), 10))]


def pick_candidates(role: str, query: str = "", asked_text: str = "",
                    round_index: int = 0, limit: int = 3) -> list:
    """挑出本轮给模型参考的候选题目（**确定性，不用 random**）。

    Args:
        role: 岗位（原始值即可，内部会 normalize；映射不到题库则返回 []）
        query: 检索词 —— 用**候选人刚说的那段话**，题就贴着他答的内容选
        asked_text: 已经问过的内容（历史里 assistant 消息拼起来），用于避免重复
        round_index: 轮次，决定类目轮换的起点（调用方传 `len(history) // 2`）
        limit: 最多几道（参考块里就几条）

    Returns:
        list[dict]，每条是一个题库记录；映射不到岗位时为 []

    选题策略：先按 query 关键词命中，命中不足时按**类目轮换**补足 ——
    轮换保证一场面试里系统设计/编码/行为等类目都能覆盖到，
    否则模型可能十轮都问 RAG 一个话题。
    """
    if not role:
        return []
    canonical = normalize_role(role)
    if not canonical:
        return []
    records = load_bank()
    if not records:
        return []
    role_key = _norm_key(canonical)
    pool = [r for r in records if _norm_key(_role_of(r)) == role_key]
    if not pool:
        return []
    limit = max(1, min(int(limit), 10))

    # 去重：题干去掉空白后是否已出现在 asked_text 里。
    # 模型是"改写后提问"，所以这只能拦住逐字复用的情况 —— 拦住就够了，
    # 剩下的交给提示词里的面试纪律（同一话题最多追 2 轮）。
    asked_squashed = re.sub(r"\s+", "", asked_text or "")
    fresh = [r for r in pool
             if re.sub(r"\s+", "", _question_of(r)) not in asked_squashed] or pool

    picked: list = []
    seen: set = set()

    def _take(record) -> bool:
        question = _question_of(record)
        if not question or question in seen:
            return False
        seen.add(question)
        picked.append(record)
        return True

    # ① 关键词命中
    if query.strip():
        for record in _score_records(fresh, query):
            if len(picked) >= limit:
                break
            _take(record)

    # ② 类目轮换补足。顺序由 _ordered_categories 固定（先三类必覆盖、再字母序），
    #    轮次推进就换一类 —— 同一轮内固定，同一输入永远同一结果（确定性），
    #    但一场面试下来类目是轮着来的。
    if len(picked) < limit:
        categories = _ordered_categories({str(r.get("category", "")) for r in fresh})
        for offset in range(len(categories)):
            if len(picked) >= limit:
                break
            category = categories[(round_index + offset) % len(categories)]
            group = [r for r in fresh if str(r.get("category", "")) == category]
            if not group:
                continue
            group.sort(key=_pick_key)
            for record in group:
                if _take(record):
                    break
    return picked[:limit]


def _clip_question(text: str, budget: int) -> str:
    """截断题干到 budget 字以内；ASCII 按词边界切，中文直接切。

    英文题干全都在 246 字以上，直接按字符切会切在单词中间（`...a fraud dete`），
    回退到最近的空格能让它至少是个完整单词结尾。
    """
    text = text.strip()
    if len(text) <= budget:
        return text
    if budget <= 1:
        return ""
    clipped = text[:budget - 1]
    if re.search(r"[A-Za-z0-9]$", clipped):
        head = clipped.rsplit(" ", 1)[0] if " " in clipped else clipped
        if len(head) >= budget // 2:      # 退太远就不退了，保持信息量
            clipped = head
    return clipped.rstrip() + "…"


def build_reference_block(role: str, query: str = "", asked_text: str = "",
                          round_index: int = 0, limit: int = 3) -> str:
    """组装注入 system prompt 的参考块；**没有可用题目时返回 `""`**。

    返回 "" 时提示词与"没有题库"逐字节相同 —— 这正是让 A/B 对照成为
    单变量实验的关键：题库关掉，链路就回到今天的样子。

    ⚠️ 调用方纪律：这个块**只能进 system prompt，绝不能进 history**。
    history 里出现参考题就等于给模型递了自己的范例 —— §11.20「模型抄自己」
    的燃料正是 assistant 消息，会自我强化、越写越长、且不会自愈。
    """
    candidates = pick_candidates(role, query, asked_text, round_index, limit)
    if not candidates:
        return ""
    # 规则先扣预算（它不能省），剩下的才给题干分
    budget = MAX_BLOCK_CHARS - len(_BLOCK_HEADER) - len(_BLOCK_RULES)
    lines = []
    for index, record in enumerate(candidates, 1):
        prefix = f"{index}. "
        # 本轮剩余预算：还要给后面的行留出 prefix 的余地
        room = budget - sum(len(line) for line in lines) - len(prefix)
        if room <= 2:
            break
        question = _clip_question(_question_of(record), min(MAX_QUESTION_CHARS, room))
        if not question:
            continue
        lines.append(prefix + question)
    if not lines:
        return ""
    block = "\n".join([_BLOCK_HEADER] + lines + [_BLOCK_RULES])
    # 兜底：截断逻辑已保证不会超，这里是防止将来改参数时静默越界
    if len(block) > MAX_BLOCK_CHARS:
        logger.warning(f"[题库] 参考块 {len(block)} 字超出上限 {MAX_BLOCK_CHARS}，已丢弃")
        return ""
    return block
