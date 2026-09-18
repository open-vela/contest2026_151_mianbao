"""从 MIT 许可的 GitHub 仓库导入中文面试题库（补充英文的 InterviewForge）。

来源（均为 MIT 许可；本文件只导入题目、不复制答案，来源标注在数据与 README 中）：
  - bcefghj/ai-agent-interview-guide      AI Agent 面试八股文（有 Q&A 结构，抽取质量高）
  - aceliuchanghong/FAQ_Of_LLM_Interview  大模型算法岗 FAQ（笔记型，用文件名/标题作题）
  - haizlin/fe-interview                  前端面试每日 3+1（按日期归档，history.md 自带分类标签）
  - guocong-bincai/ai-interview-guide     AI 全岗位面试宝典（26 个细分主题，`### Qn: 题干`）
  - bcefghj/learn-nanobot                 AI Agent 面试八股文 134 题（同作者另一仓库）
  - lengyue1024/BAT_interviews            BAT 各语言面试题（取 Python/机器学习/前端三个文件）
  - lf2021/Front-End-Interview            前端按主题分类（含「面试高频手撕代码题」）
  - FEGuideTeam/FEGuide                   前端八股（css/html/javascript/手写代码/框架/网络）

用法（在仓库根目录跑）：
  python3 question_bank/import/import_github_bank.py          # 浅克隆到临时目录并导入
  python3 question_bank/import/import_github_bank.py --fresh  # 忽略已有克隆，重新拉取

产物：question_bank/data/zh_questions.json（AI 岗中文题，**本仓只收这一份**）
      question_bank/data/fe_questions.json（前端岗，**本仓不收录**）

⚠️ 前端一份（6160 题）不随本仓分发，理由见 ../README.md「为什么只有 AI 侧两份」。
   脚本保留前端来源是为了让导入过程完整可复现；真跑一遍会在 data/ 下写出
   fe_questions.json，但 cloud/question_bank.py 只按白名单加载两个文件，多出来的
   文件不会被读进题库（这正是用白名单而不是 glob("*.json") 的原因）。
"""
import collections
import json
import pathlib
import re
import subprocess
import sys
import tempfile

# 本文件在 question_bank/import/ 下，数据在同级的 question_bank/data/
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
CLONE_ROOT = pathlib.Path(tempfile.gettempdir()) / "interview_banks"

# 看起来像问题的标题（真正的疑问词才算；"原理/介绍"是主题词，不算）
QUESTION_HINTS = ("什么", "为什么", "如何", "怎么", "怎样", "区别", "是否", "哪些", "？", "?")

# 元文件/操作性文件名——不是面试主题，跳过
META_HINTS = ("readme", "使用", "入门", "基本用法", "基本操作", "编写", "代码",
              "参数解释", "说明", "进阶", "tutorial", "guide", "环境配置")

# ---------- fe-interview 专用 ----------

# history.md 的每行带分类标签：`- [ECMAScript] [题干](issue链接)`
FE_TAGGED_LINE = re.compile(r"^\s*-\s*\[([^\]]+)\]\s*\[(.*)\]\((https?://\S+)\)\s*$")
# 其余 8 个文件没有标签：`- [题干](issue链接)`，分类取文件名
FE_PLAIN_LINE = re.compile(r"^\s*-\s*\[(.+?)\]\((https?://\S+)\)\s*$")

# 其余文件的文件名 → history.md 的分类名（避免同一个主题裂成两个分类）
FE_CATEGORY_ALIAS = {"nodejs": "NodeJs", "skill": "软技能", "ecmascript": "ECMAScript"}

# 源站的「本题含代码块」标记，不是题干的一部分，提问时要去掉
FE_CODE_MARK = re.compile(r"\s*\[代码\]\s*")

# 行为/软技能题的信号词——命中就把 stage 标成行为面，供面试官按 stage 过滤
# （英文题库的行为面是 "Stage 3: Team Fit & Scenario Handling"，这里沿用同一取值）
# 用词要窄：像「管理」「失败」「压力」「冲突」这类看似行为、实则大量出现在技术题里
# （内存管理 / promise 失败重试 / 压力测试 / 端口冲突），命中即误标，不能用。
FE_BEHAVIOR_HINTS = ("团队", "沟通", "协作", "跨部门", "合作", "向上汇报",
                     "职业规划", "为什么离职", "离职", "感悟",
                     "如何看待", "你怎么看", "意见不合", "带人", "作为管理者")
FE_BEHAVIOR_STAGE = "Stage 3: Team Fit & Scenario Handling"

# 明显不是面试题的闲聊（人工抽查 5370 题后确认的少数几条）
FE_NOISE = ("我也要出题", "你会开车吗", "你喜欢跑步吗", "你喜欢爬山吗",
            "你平时熬夜吗", "你有什么爱好", "薅羊毛", "玩手机")


def clean_title(text: str) -> str:
    """清理标题：去 markdown 标记/编号前缀/多余空白。"""
    text = re.sub(r"[#*`>\-—]+", " ", text)
    text = re.sub(r"^\s*\d+(?:[.\-、]\d+)*[.\-、]?\s*", "", text)
    text = re.sub(r"^[0-9]+-[^\d]*", "", text)          # 形如 "1-大模型应用基础" 的目录编号
    return " ".join(text.split()).strip(" .：:")


def looks_like_question(text: str) -> bool:
    return any(hint in text for hint in QUESTION_HINTS)


def extract_from_agent_guide(markdown: str) -> list[str]:
    """从 AI Agent 八股文里抽题：优先 `### Q13：xxx`，其次 `## 3. xxx` 小节标题。"""
    questions = []
    for line in markdown.splitlines():
        match = re.match(r"^###\s*Q\d+\s*[：:]\s*(.+)", line.strip())
        if match:
            questions.append(clean_title(match.group(1)))
            continue
        match = re.match(r"^##\s+\d+(?:\.\d+)*\s*[.、]?\s*(.+)$", line.strip())
        if match:
            title = clean_title(match.group(1))
            if (title and len(title) > 4
                    and not title.startswith(("目录", "综合面试题库", "参考", "附录"))):
                questions.append(title)
    return [q for q in questions if len(q) >= 6]


def question_from_filename(name: str) -> str:
    """笔记型仓库：用文件名生成一道面试题（文件名本身就是主题）。"""
    topic = clean_title(pathlib.Path(name).stem)
    if not topic:
        return ""
    if any(hint in topic.lower() for hint in META_HINTS):   # readme/使用说明之类，不是题目
        return ""
    if looks_like_question(topic):
        return topic if topic.endswith(("？", "?")) else f"{topic}？"
    return f"请讲讲「{topic}」的关键点，并结合实际场景举例。"


def category_from_path(relative: pathlib.Path) -> str:
    """用所在目录名（去编号）作为类别。"""
    parts = [clean_title(part) for part in relative.parts[:-1]]
    parts = [p for p in parts if p and p not in ("docs", "README")]
    return parts[-1] if parts else "通用"


def build_entries(questions: list[str], role: str, category: str, source: str,
                  seen: set) -> list[dict]:
    entries = []
    for question in questions:
        key = re.sub(r"\s+", "", question)
        if len(key) < 6 or key in seen:
            continue
        seen.add(key)
        entries.append({
            "question": question,
            "keywords": [],
            "role": role,
            "category": category,
            "level": "",
            "stage": "",
            "lang": "zh",
            "source": source,
        })
    return entries


def clone(repo: str, target: pathlib.Path, fresh: bool = False) -> pathlib.Path:
    if target.is_dir() and not fresh:
        return target
    if target.exists():
        subprocess.run(["rm", "-rf", str(target)], check=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"  克隆 {repo} …")
    subprocess.run(["git", "clone", "--depth", "1", "-q",
                    f"https://github.com/{repo}.git", str(target)], check=True)
    return target


# ---------- 各数据源的抽取器 ----------
# 签名统一为 (root, source, ctx) -> list[record]；ctx 持有跨文件去重集合：
#   ctx["text"]  AI 岗两个源共用的题干去重（保持原有行为）
#   ctx["url"]   前端题库按 issue 链接去重

def _wanted(md: pathlib.Path, root: pathlib.Path, source: dict) -> bool:
    rel = md.relative_to(root).as_posix()
    return any(rel.startswith(prefix) for prefix in source.get("include", ()))


def _extract_agent_guide(root: pathlib.Path, source: dict, ctx: dict) -> list[dict]:
    entries: list[dict] = []
    for md in sorted(root.glob("docs/**/*.md")):
        if not _wanted(md, root, source):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        entries += build_entries(extract_from_agent_guide(text), source["role"],
                                 category_from_path(md.relative_to(root)),
                                 source["repo"], ctx["text"][source["out"]])
    return entries


def _extract_llm_faq(root: pathlib.Path, source: dict, ctx: dict) -> list[dict]:
    entries: list[dict] = []
    for md in sorted(root.glob("**/*.md")):
        if not _wanted(md, root, source):
            continue
        if any(part.startswith(".") for part in md.relative_to(root).parts):
            continue
        question = question_from_filename(md.name)
        entries += build_entries([question], source["role"],
                                 category_from_path(md.relative_to(root)),
                                 source["repo"], ctx["text"][source["out"]])
    return entries


def _extract_fe_interview(root: pathlib.Path, source: dict, ctx: dict) -> list[dict]:
    """抽取 haizlin/fe-interview 的 category/*.md。

    history.md 覆盖最全（第 1 天 2019-04 起全部题目，按日期倒序）且每行自带分类标签，
    其余 8 个文件与它重叠 96%、只补 100 余道，分类取文件名。所以先跑 history.md，
    再用其余文件补缺；按 issue 链接去重——同一道题在不同文件里有 2318 处措辞不同，
    先跑的那个版本胜出（history.md 的措辞更新，也是想要的）。
    """
    category_dir = root / "category"
    if not category_dir.is_dir():
        return []
    seen = ctx["url"][source["out"]]
    entries: list[dict] = []
    ordered = sorted(category_dir.glob("*.md"), key=lambda p: p.name != "history.md")
    for md in ordered:
        tagged = md.name == "history.md"
        fallback_category = FE_CATEGORY_ALIAS.get(md.stem.lower(), md.stem)
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            match = FE_TAGGED_LINE.match(line) if tagged else FE_PLAIN_LINE.match(line)
            if not match:
                continue
            if tagged:
                category, question, url = match.group(1), match.group(2), match.group(3)
            else:
                category, question, url = fallback_category, match.group(1), match.group(2)
            if url in seen:
                continue
            seen.add(url)                # 先认领：同一 issue 只取优先级最高文件里的措辞
            question = " ".join(FE_CODE_MARK.sub(" ", question).split())
            if len(question) < 6 or any(hint in question for hint in FE_NOISE):
                continue
            entries.append({
                "question": question,
                "keywords": [],
                "role": source["role"],
                "category": category,
                "level": "",
                "stage": FE_BEHAVIOR_STAGE if any(h in question for h in FE_BEHAVIOR_HINTS) else "",
                "lang": "zh",
                "source": source["repo"],
                "url": url,
            })
    return entries


# ---------- 通用：markdown 标题即题目 ----------
# 后加入的这几个仓库结构各异，但共同点是「某一级标题行就是题目」。
# 差异全部用 SOURCES 里的键描述，不再一个仓库写一个抽取器：
#   files     相对仓库根的 glob（可给多个）
#   skip      路径片段黑名单——简历/投递/个人面经等求职向目录，不是技术题
#   pattern   正文里作题的行正则，第 1 个捕获组是题干
#   section   可选，小节标题正则（第 1 组是小节名）；用它给题目分类
#   category  分类来源："h1" 文件首个一级标题 | "section" 当前小节 | "filename" 文件名
#             | "parent" 上级目录名（默认）
#   catmap    分类名归一化的映射（可选）

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿️]")
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")      # [文字](链接) → 文字
BARE_URL = re.compile(r"https?://\S+")
# 源站的难度标记（「(必考)」「[易混淆]」这类），念出来会怪，去掉；
# 括号里必须「只有」标记词才匹配，免得误伤「（包括 Number、String）」这种正文
DIFFICULTY_MARK = re.compile(
    r"[（(\[【]\s*(常考|必考|易混淆|重点|高频|经典|面试题|加分项)\s*[)）\]】]")


def _clean_heading(text: str) -> str:
    """标题清理：剥掉 markdown 链接只留文字，再去标记、编号前缀、emoji 与多余空白。

    必须先剥链接再交给 clean_title——clean_title 会把 URL 里的 `-` 换成空格，
    「leetcode-cn.com」会变成「leetcode cn.com」这种残渣。
    """
    text = MD_LINK.sub(r"\1", EMOJI.sub("", text))
    text = BARE_URL.sub(" ", DIFFICULTY_MARK.sub("", text))
    return clean_title(text)


def _clean_section(text: str) -> str:
    """小节名清理：只去中文序号前缀与空白。

    不能用 clean_title——它会把 `-` 换成空格，把「Q1-Q15」毁成「Q1 Q15」。
    """
    text = re.sub(r"^[一二三四五六七八九十]+\s*[、.．]\s*", "", EMOJI.sub("", text))
    return " ".join(text.split()).strip(" .：:")


def _source_files(root: pathlib.Path, source: dict) -> list[pathlib.Path]:
    """按白名单 glob 取文件，并排除求职向/个人日志等非技术目录。"""
    patterns = source["files"]
    if isinstance(patterns, str):
        patterns = (patterns,)
    skip = source.get("skip", ())
    files = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not any(part in path.relative_to(root).as_posix() for part in skip):
                files.append(path)
    return files


def _category_for(text: str, md: pathlib.Path, section: str, source: dict) -> str:
    how = source.get("category", "parent")
    if how == "h1":
        name = next((line.lstrip("# ").strip() for line in text.splitlines()
                     if line.startswith("# ")), md.parent.name)
    elif how == "section":
        name = section or md.parent.name
    elif how == "filename":
        name = md.stem
    else:
        name = md.parent.name
    # 统一过一遍 catmap（分类归一化），各分支都不能绕过
    cleaned = _clean_section(name) if how == "section" else _clean_heading(name)
    return source.get("catmap", {}).get(cleaned, cleaned)


def _extract_headings(root: pathlib.Path, source: dict, ctx: dict) -> list[dict]:
    """通用抽取器：按 SOURCES 里的 pattern 取标题行作题。"""
    pattern = re.compile(source["pattern"])
    section_pattern = re.compile(source["section"]) if source.get("section") else None
    seen = ctx["text"][source["out"]]
    entries: list[dict] = []
    for md in _source_files(root, source):
        text = md.read_text(encoding="utf-8", errors="replace")
        section = ""
        for line in text.splitlines():
            if section_pattern:
                match = section_pattern.match(line)
                if match:
                    section = _clean_section(match.group(1))
                    continue
            match = pattern.match(line)
            if not match:
                continue
            question = _clean_heading(match.group(1))
            key = re.sub(r"\s+", "", question)
            if len(key) < 6 or key in seen:
                continue
            seen.add(key)
            entries.append({
                "question": question,
                "keywords": [],
                "role": source["role"],
                "category": _category_for(text, md, section, source),
                "level": "",
                "stage": FE_BEHAVIOR_STAGE if any(h in question for h in FE_BEHAVIOR_HINTS) else "",
                "lang": "zh",
                "source": source["repo"],
            })
    return entries


SOURCES = [
    {"repo": "bcefghj/ai-agent-interview-guide", "dir": "ai-agent-guide",
     "role": "AI Agent 开发", "out": "zh_questions.json",
     # 白名单：只取技术内容；排除 学习路线图/企业招聘/简历模板/STAR面试稿 等求职向目录
     "include": ("docs/01-面试八股文", "docs/06-面试问答集"),
     "extract": _extract_agent_guide},
    {"repo": "aceliuchanghong/FAQ_Of_LLM_Interview", "dir": "llm-faq",
     "role": "大模型算法工程师", "out": "zh_questions.json",
     # 白名单：技术各篇；排除 3-面试问题记录（作者个人求职日志）/thoughts/using_files
     "include": ("1-大模型应用基础", "2-大模型优化技术", "4-分布式训练篇",
                 "5-高效微调篇", "6-强化学习基础", "pytorch"),
     "extract": _extract_llm_faq},
    {"repo": "haizlin/fe-interview", "dir": "fe-interview",
     "role": "前端工程师", "out": "fe_questions.json",
     "extract": _extract_fe_interview},

    # ---- AI 岗补充 ----
    {"repo": "guocong-bincai/ai-interview-guide", "dir": "ai-guide",
     "role": "AI 应用开发", "out": "zh_questions.json",
     "files": "docs/*/README.md",
     # 排除 16-简历面试技巧 与 27-项目经历包装——求职向，不是技术题
     "skip": ("16-resume-interview-tips", "27-project-experience"),
     "pattern": r"^###\s*Q\d+\s*[:：.、]\s*(.+)",
     "category": "h1"},
    {"repo": "bcefghj/learn-nanobot", "dir": "learn-nanobot",
     "role": "AI Agent 开发", "out": "zh_questions.json",
     "files": "docs/13-interview-bagua/README.md",     # 其余 docs 是教程、14~17 是求职向
     "pattern": r"^###\s*Q\d+\s*[.、:：]\s*(.+)",
     "section": r"^##\s+(.+)",
     "category": "section"},
    {"repo": "lengyue1024/BAT_interviews", "dir": "bat-interviews",
     "role": "大模型算法工程师", "out": "zh_questions.json",
     "files": "机器学习.md",
     # 该仓库同一文件里有两种标题格式：`### N、题干`（MySQL/Spring）与 `#### N 题干`（Python/前端）
     "pattern": r"^\s*#{2,6}\s*\d+\s*[、. ]\s*(.+)",
     "category": "filename", "catmap": {"机器学习": "机器学习"}},
    {"repo": "lengyue1024/BAT_interviews", "dir": "bat-interviews",
     "role": "AI 应用开发", "out": "zh_questions.json",
     "files": "Python面试题及答案.md",
     "pattern": r"^\s*#{2,6}\s*\d+\s*[、. ]\s*(.+)",
     "category": "filename", "catmap": {"Python面试题及答案": "Python"}},

    # ---- 前端岗补充 ----
    {"repo": "lf2021/Front-End-Interview", "dir": "front-end-interview",
     "role": "前端工程师", "out": "fe_questions.json",
     "files": "*/*.md",                                 # 目录形如 05.JavaScript/，clean_title 会去掉编号
     # 09 是作者的个人面经；02 是教程不是题库——它的 `##` 是章节名（「一、数组」「二、栈」），
     # 抽出来全是「七、排序算法」这类噪音，其余目录的 `##` 才是真题目；
     # 13 是作者的常用工具清单（录屏 Loom / AdBlocker 插件 / vscode 配置），不是面试题
     "skip": ("09.面试复盘", "02.数据结构与算法", "13.实战篇"),
     "catmap": {"面试高频手撕代码题": "手写代码"},     # 和 FEGuide 的「手写代码」是同一类，合并
     "pattern": r"^##\s+(.+)"},                         # 目录用的是一级/二级列表，不会误match
    {"repo": "FEGuideTeam/FEGuide", "dir": "feguide",
     "role": "前端工程师", "out": "fe_questions.json",
     # 注意 手写代码/ 下的文件名是 READEME.md（源仓库拼错了），且 框架/ 下不是 README，
     # 所以这里用 ** 全收，再排除 imgs/（只有图片）
     "files": "**/*.md",
     "skip": ("imgs/",),
     "pattern": r"^###\s+(.+)",
     # 这个仓库用「xxx问题」命名目录，和 Front-End-Interview 的 CSS/HTML/JavaScript 是同一主题，
     # 不归一的话同一个考点会裂成两个分类，面试官按 category 选题时会漏掉一半
     "catmap": {"css问题": "CSS", "html问题": "HTML", "javascript问题": "JavaScript",
                "网络问题": "网络", "手写代码": "手写代码"}},
    {"repo": "lengyue1024/BAT_interviews", "dir": "bat-interviews",
     "role": "前端工程师", "out": "fe_questions.json",
     "files": "前端面试题及答案.md",
     "pattern": r"^\s*#{2,6}\s*\d+\s*[、. ]\s*(.+)",
     "category": "filename", "catmap": {"前端面试题及答案": "前端"}},
]


def main(fresh: bool = False) -> None:
    # 去重集合按产物文件隔离：AI 题与前端题各自去重，互不干扰
    ctx = {"text": collections.defaultdict(set), "url": collections.defaultdict(set)}
    outputs: dict[str, list] = {}
    for source in SOURCES:
        root = clone(source["repo"], CLONE_ROOT / source["dir"], fresh)
        # 没写 extract 的源走通用抽取器（SOURCES 里的 pattern/category 等键描述差异）
        extract = source.get("extract", _extract_headings)
        entries = extract(root, source, ctx)
        outputs.setdefault(source["out"], []).extend(entries)
        categories = sorted({entry["category"] for entry in entries})
        print(f"  {source['repo']}: {len(entries)} 题"
              f"（分类：{'、'.join(categories)}）")

    # 全部抽完再落盘：中途克隆失败不会留下「一个文件刷新了、另一个还是旧的」
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, entries in outputs.items():
        path = DATA_DIR / name
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"合计 {len(entries)} 题 → {path}")


if __name__ == "__main__":
    main(fresh="--fresh" in sys.argv)
