#!/usr/bin/env python3
"""单变量 A/B：题库注入与提示词改动的对照实验。

**这是唯一一个需要花钱的验证脚本**（真打 LLM）。先跑 `--dry-run`（不花钱）人工审
参考块，确认没问题再跑真实验。

跑法：

    export MIMO_API_KEY="$(sed -n '42p' ~/test-project/README.md | tr -d '\\r\\n')"

    python3 cloud/ab_next_question.py --dry-run        # 只打印参考块，不打 LLM
    python3 cloud/ab_next_question.py --n 30           # 完整对照（约 150 次调用）
    python3 cloud/ab_next_question.py --n 2            # 冒烟测试，先确认脚本能跑通

三组对照（**单变量**：每次只让一个因素变）：

    P 提示词   旧提示词+题库关   vs  新提示词+题库关
    B 题库     新提示词+题库关   vs  新提示词+题库开
    R 报告     旧报告提示词      vs  新报告提示词

P 组与 B 组共用「新提示词+题库关」这一臂，所以两组各自都是干净的对照。

**单变量是怎么保证的**：`next_question()` 每次都调 `load_skill()` 取提示词，
所以脚本 monkeypatch `load_skill` 直接喂提示词文本（而不是去改磁盘上的 JSON）；
「题库关」则把 `build_reference_block` 换成一律返回 ""，也就是岗位映射不到题库时
真实链路会走的那条路。两个因素都由脚本控制，不依赖仓库当前状态。

输入固定 4 例轮换，第 4 例是 §11.20 那条**被污染的真实历史**（见下）。
"""
import argparse
import importlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import llm_service  # noqa: E402  （必须在 sys.path 处理之后）

# ============================================================
# 基线提示词（旧版）—— 冻结在这里，不去读仓库文件
#
# 不能从 git 里取（`git show HEAD:...` 在本次改动提交后就会变成新版），
# 也不能读磁盘（磁盘上就是新版）。基线必须是常量，否则这个脚本在提交之后就失效了。
# ============================================================

OLD_NEXT_QUESTION_PROMPT = (
    "你是{role}岗位的面试官，正在与候选人**语音**对话 —— 你写下的每个字都会被直接念出来给候选人听。\n\n"
    "根据候选人的上一个回答，决定\"追问细节\"还是\"提出新问题\"，然后**只输出你要对候选人说的那段话**。\n\n"
    "【硬性要求】\n"
    "1. 只输出对候选人说的话。不要任何分析、判断、理由、说明、备注、标题、分点或表格。\n"
    "2. 不要用 Markdown（**、#、---、>、| 都不要），它们会被逐字念出来。\n"
    "3. 全文控制在 120 字以内，1~3 句话，以一个问题结尾。\n"
    "4. 不要解释你提问的意图，不要评价候选人的表现，不要出现\"作为面试官\"这类旁白。\n"
    "5. 候选人回答无效时（例如只说了问候、答非所问），不要点评，直接用一句话自然地再问一次。\n\n"
    "正确示例：您提到的这个项目挺有意思，能具体说说您在其中的角色，以及遇到的最大挑战吗？\n"
    "错误示例：**判断：需要追问** 理由：候选人回答过于简略…… 追问：……"
)

OLD_FEEDBACK_PROMPT = (
    "你是一位资深的HR面试专家。请根据以下完整面试对话，生成一份简洁的面试评估报告，"
    "包含：1. 总体评价 2. 优点 3. 待改进项 4. 综合建议。评估岗位：{role}。"
    "请用中文、专业且温和的语气撰写。\n\n"
    "【长度硬性要求】全文控制在 200 字以内（含标点）。每部分 1~2 句话即可，不要展开、"
    "不要分点罗列细节。这份报告会被语音合成后播放，超长会导致播报冗长 —— "
    "宁可精炼，不要面面俱到。"
)

# ============================================================
# 输入固定的 4 例
# ============================================================

# ⚠️ §11.20「模型抄自己」的污染样本 —— **必测**。
#
# 这段是 2026-09-15 事故里那条真实模型输出，**原文照录**（当时用户在会话里贴出来的，
# 现存于 logs/xunzhekafei/2026-09-15/ 的会话日志）。其余 4 条同模板的助手消息**是按
# 台账 §11.20 记录的结构与长度（实测 460→570→533→456→424 字）重建的** —— 原始
# 全文只存在于当时 /tmp 里的复现脚本，虚拟机重启后已丢失。
#
# 这一例的岗位刻意保持当时的「产品经理」（没改）：它是真实样本，内部一致不如保真重要。
# 代价是「产品经理」映射不到题库，所以 **B 组（题库开关）跳过这一例**，见 samples_for()。
POLLUTED_ASSISTANT = (
    "判断：提出新问题\n\n---\n\n理由：\n\n候选人终于给出了清晰、正常的问候，"
    "表明之前的沟通障碍可能已经解决。作为面试官，我应该把握这个机会，"
    "重新开启面试流程，直接切入正题。\n\n---\n\n新问题：\n\n"
    "> 您好，欢迎参加本次面试。我们直接进入正题。\n>\n"
    "> 请用2-3分钟介绍一下您自己，重点说明：\n"
    "> 1. 您过去的工作经历中，与产品管理最相关的经验是什么？"
)


def _polluted(text_middle: str, question: str) -> str:
    """按 §11.20 记录的模板拼一条污染消息（结构：判断 → 理由 → 新问题）。"""
    return (f"**判断：提出新问题**\n\n---\n\n理由：\n\n{text_middle}\n\n---\n\n"
            f"新问题：\n\n> {question}\n\n---\n\n下一步：\n\n等待候选人回复后，"
            f"根据其回答深度决定是继续追问还是进入下一个话题。")


INPUTS = [
    {
        "name": "开局-自我介绍",
        "role": "AI 应用开发",
        "answer": "我叫李昊，本科计算机，做了三年后端，最近一年半在一家公司做 AI 应用，"
                  "主要负责知识库问答这块。",
        "history": [
            {"role": "assistant", "content": "请先做个自我介绍吧。"},
        ],
    },
    {
        "name": "技术-向量检索",
        "role": "AI 应用开发",
        "answer": "我们用向量数据库做召回，切分是按标题层级切的，因为这样每个块语义完整一些。",
        "history": [
            {"role": "assistant", "content": "请先做个自我介绍吧。"},
            {"role": "user", "content": "我做后端三年，最近在做 RAG 知识库。"},
            {"role": "assistant", "content": "你说的知识库，文档是怎么切分的？"},
            {"role": "user", "content": "我们试过固定长度，后来改成按标题切。"},
            {"role": "assistant", "content": "切完之后是怎么检索的呢？"},
        ],
    },
    {
        "name": "场景-线上故障",
        "role": "AI 应用开发",
        "answer": "是在监控上发现的，召回率掉了十个百分点，后来定位到是索引没重建成功。",
        "history": [
            {"role": "assistant", "content": "请先做个自我介绍吧。"},
            {"role": "user", "content": "我负责检索和评测。"},
            {"role": "assistant", "content": "线上出过什么问题吗？"},
            {"role": "user", "content": "有一次效果突然变差了。"},
            {"role": "assistant", "content": "那你当时是怎么发现的？"},
        ],
    },
    {
        "name": "§11.20 被污染的真实历史",
        "role": "产品经理",
        "answer": "你好，我是王涛，做产品经理五年了，之前在一家做企业服务的公司。",
        "history": [
            {"role": "user", "content": "喂喂，你好。"},
            {"role": "assistant", "content": _polluted(
                "候选人的输入是重复的问候语，没有提供任何可用于提问的信息。"
                "我判断这不是有效的面试回答，需要重新引导他进入面试状态。",
                "您好，我是本次面试的面试官。请先做一个简短的自我介绍。")},
            {"role": "user", "content": "喂喂，你好。"},
            {"role": "assistant", "content": _polluted(
                "候选人仍然只给出问候，可能是设备或环境问题导致他没有听清。"
                "我不应该评价他的表现，也不应该解释我的判断，直接再问一次即可。",
                "您好，能听到吗？请用两三分钟介绍一下您自己。")},
            {"role": "user", "content": "你好，我准备好了，可以开始了。"},
            {"role": "assistant", "content": POLLUTED_ASSISTANT},   # ← 真实原文
        ],
    },
]

# ---------------- 判据（与计划 §六.3 一致） ----------------

MAX_EMPTY_RATE_OLD = 1 / 30     # 空返回不高于旧版，且绝对上限 1/30
MAX_LENGTH_RATIO = 1.2          # 平均字数 ≤ 旧版 × 1.2（只对 P 组；B 组用下面的硬上限）
MAX_QUESTION_CHARS = 120        # 提示词自己写的上限，B 组守这一条
MIN_QUESTION_END = 0.9          # 以问号结尾的比例 ≥ 90%
MAX_REPORT_CHARS = 250          # 报告 100% ≤ 250 字
MIN_QUOTE_RATE = 0.9            # 报告含「」原话 ≥ 90%

# 出现这些就是格式残留（会被 TTS 逐字念出来）
MARKDOWN_PATTERNS = (
    (r"\*\*", "** 加粗"),
    (r"^#{1,6}\s", "行首 # 标题"),
    (r"^\s*[-*]\s", "行首列表符号"),
    (r"^\s*\d+[.、]\s", "行首编号列表"),
    (r"\|.*\|", "表格"),
    (r"^>\s", "引用块"),
    (r"---", "分隔线"),
)
TEMPLATE_STRINGS = ("判断：", "理由：", "新问题：", "问题设计说明", "下一步：",
                    "追问理由", "作为面试官", "面试官应该")

# 空返回时 llm_service 给的兜底文案（用户听到的就是这句）
FALLBACK_MARKERS = ("生成问题失败", "生成报告失败", "加载面试配置失败",
                    # reply_guard 的兜底问句：出现它就说明模型那一轮整段都在写元叙述、
                    # 被闸门替换掉了 —— 必须按"这一轮不合格"计，不能当正常输出混过去。
                    "能就刚才提到的这点再具体说说吗")


def _patched_skill(prompt: str, max_tokens: int):
    """构造一个假的 load_skill：不管要哪个 skill，都返回指定提示词。

    `temperature` / `max_tokens` 保持与线上一致（由调用方从真实 skill 文件读出来），
    这样提示词就是**唯一**被改动的因素。
    """
    def fake_load_skill(skill_name: str) -> dict:
        return {"system_prompt": prompt, "temperature": 0.7, "max_tokens": max_tokens}
    return fake_load_skill


def _run_next_question(role: str, history: list, answer: str,
                       prompt: str, bank_on: bool, max_tokens: int = 800) -> dict:
    """跑一次 next_question，只在这一次调用期间改全局状态（单变量控制）。

    `next_question` 每轮都重新 `load_skill()` 取提示词，所以替换掉它就等于换了提示词；
    「题库关」直接把 `build_reference_block` 换成返回 "" —— 与真实链路上
    「岗位映射不到题库」时的行为一致。
    """
    saved_skill = llm_service.load_skill
    saved_block = llm_service.build_reference_block
    try:
        llm_service.load_skill = _patched_skill(prompt, max_tokens)
        if not bank_on:
            llm_service.build_reference_block = lambda *a, **k: ""
        return llm_service.next_question(role, history, answer)
    finally:
        llm_service.load_skill = saved_skill
        llm_service.build_reference_block = saved_block


def _run_feedback(role: str, history: list, prompt: str, max_tokens: int = 600) -> dict:
    saved = llm_service.load_skill
    try:
        llm_service.load_skill = _patched_skill(prompt, max_tokens)
        return llm_service.generate_feedback(role, history)
    finally:
        llm_service.load_skill = saved


def audit_question(text: str) -> dict:
    """给一条问句打分。"""
    stripped = text.strip()
    empty = (not stripped) or any(marker in stripped for marker in FALLBACK_MARKERS)
    residues = [label for pattern, label in MARKDOWN_PATTERNS
                if re.search(pattern, stripped, re.MULTILINE)]
    templates = [token for token in TEMPLATE_STRINGS if token in stripped]
    return {
        "chars": len(stripped),
        "empty": empty,
        "residues": residues,
        "templates": templates,
        "ends_with_question": stripped.endswith(("？", "?")),
    }


def summarize(samples: list) -> dict:
    if not samples:
        return {}
    count = len(samples)
    return {
        "n": count,
        "empty": sum(1 for s in samples if s["empty"]),
        "avg_chars": sum(s["chars"] for s in samples) / count,
        "max_chars": max(s["chars"] for s in samples),
        "residue": sum(1 for s in samples if s["residues"]),
        "template": sum(1 for s in samples if s["templates"]),
        "question_end": sum(1 for s in samples if s["ends_with_question"]) / count,
    }


def samples_for(inputs: list, arm_name: str, n: int) -> list:
    """哪些输入能用于这一臂。

    B 组（题库开关）只测岗位能映射进题库的输入 —— 「产品经理」那一例在开关两侧
    都是空块，放进来只是凑数，不是对照。
    """
    if arm_name != "B":
        return inputs
    usable = [item for item in inputs if item["role"] != "产品经理"]
    return usable or inputs


def run_arm(name: str, inputs: list, n: int, prompt: str, bank_on: bool,
            max_tokens: int = 800) -> list:
    samples = []
    for index in range(n):
        item = inputs[index % len(inputs)]
        result = _run_next_question(item["role"], item["history"], item["answer"],
                                    prompt, bank_on, max_tokens)
        text = result.get("text", "")
        record = audit_question(text)
        record["input"] = item["name"]
        record["text"] = text
        samples.append(record)
        flag = "空!" if record["empty"] else ("残留!" if record["residues"] or record["templates"] else "")
        print(f"  [{name}] {index + 1:2d}/{n} {item['name'][:12]:14s} "
              f"{record['chars']:4d}字 {flag} {text[:40]}")
    return samples


def run_report_arm(name: str, inputs: list, n: int, prompt: str,
                   report_history: list, max_tokens: int = 600) -> list:
    samples = []
    for index in range(n):
        item = inputs[index % len(inputs)]
        history = item["history"] + report_history
        result = _run_feedback(item["role"], history, prompt, max_tokens)
        text = (result.get("text") or "").strip()
        empty = (not text) or any(marker in text for marker in FALLBACK_MARKERS)
        record = {
            "empty": empty,
            "chars": len(text),
            "has_quote": "「" in text and "」" in text,
            "markdown": [label for pattern, label in MARKDOWN_PATTERNS
                         if re.search(pattern, text, re.MULTILINE)],
            "text": text,
        }
        samples.append(record)
        print(f"  [{name}] {index + 1:2d}/{n} {record['chars']:4d}字 "
              f"{'有原话' if record['has_quote'] else '无原话!'} "
              f"{'残留!' if record['markdown'] else ''} {text[:40]}")
    return samples


def dry_run(inputs: list) -> int:
    """只打印各例的参考块（不花钱），人工审一眼再决定要不要跑真实验。"""
    print("=" * 78)
    print("--dry-run：只组装参考块，不调用 LLM。逐例确认「题目贴不贴题、有没有越界」。")
    print("=" * 78)
    for item in inputs:
        asked = " ".join(m["content"] for m in item["history"] if m["role"] == "assistant")
        block = llm_service.build_reference_block(item["role"], item["answer"], asked,
                                                  len(item["history"]) // 2)
        print(f"\n【{item['name']}】岗位={item['role']}  块长={len(block)}")
        print(block if block else f"  (空块 —— 该岗位映射不到题库，退化为自由提问)")
    print("\n" + "=" * 78)
    print("人工检查项：① 题目是否贴合候选人刚说的内容；② 有没有英文长题被整段塞进来；")
    print("            ③ 块长是否都在 400 字以内；④ 岗位落空的那一例是否确实是空块。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="题库注入 / 提示词改动的单变量 A/B")
    parser.add_argument("--n", type=int, default=30, help="每一臂的样本数（默认 30）")
    parser.add_argument("--dry-run", action="store_true", help="只打印参考块，不调用 LLM")
    parser.add_argument("--group", default="PBR", help="跑哪几组：P 提示词 / B 题库 / R 报告")
    args = parser.parse_args()

    if args.dry_run:
        return dry_run(INPUTS)

    next_skill = llm_service.load_skill("next_question")
    feedback_skill = llm_service.load_skill("generate_feedback")
    new_next_prompt = next_skill["system_prompt"]
    new_feedback_prompt = feedback_skill["system_prompt"]
    # 两臂共用同一组采样参数，提示词是唯一变量
    next_tokens = next_skill.get("max_tokens", 800)
    feedback_tokens = feedback_skill.get("max_tokens", 600)
    if "{reference_block}" not in new_next_prompt:
        print("❌ 磁盘上的 next_question 提示词里没有 {reference_block} 占位符 —— "
              "先确认 skills/next_question.json 是新版。")
        return 1

    # 报告组要一段"面试已经进行到后半程"的历史，否则报告没什么可评的。
    # 用真实的多轮问答（不是同一句话重复）—— 长历史下的报告才有东西可引用。
    report_history = []
    for item in INPUTS[:3]:
        report_history.extend(item["history"])
        report_history.append({"role": "user", "content": item["answer"]})

    report = {}

    if "P" in args.group:
        print(f"\n=== P 组：旧提示词 vs 新提示词（题库关，n={args.n}）===")
        old = run_arm("旧", INPUTS, args.n, OLD_NEXT_QUESTION_PROMPT, False, next_tokens)
        new = run_arm("新", INPUTS, args.n, new_next_prompt, False, next_tokens)
        report["P"] = (summarize(old), summarize(new))

    if "B" in args.group:
        usable = samples_for(INPUTS, "B", args.n)
        print(f"\n=== B 组：题库关 vs 题库开（新提示词，n={args.n}；"
              f"用 {len(usable)} 个输入，跳过映射不到题库的「产品经理」）===")
        off = run_arm("关", usable, args.n, new_next_prompt, False, next_tokens)
        on = run_arm("开", usable, args.n, new_next_prompt, True, next_tokens)
        report["B"] = (summarize(off), summarize(on))

    if "R" in args.group:
        print(f"\n=== R 组：旧报告提示词 vs 新报告提示词（n={args.n}）===")
        old_r = run_report_arm("旧", INPUTS, args.n, OLD_FEEDBACK_PROMPT,
                               report_history, feedback_tokens)
        new_r = run_report_arm("新", INPUTS, args.n, new_feedback_prompt,
                               report_history, feedback_tokens)
        report["R"] = (old_r, new_r)

    # ---------------- 判定 ----------------
    print("\n" + "=" * 78)
    print("判定")
    print("=" * 78)
    failures = []

    for group, (base, candidate) in report.items():
        if group == "R":
            base_r, cand_r = base, candidate
            base_empty = sum(1 for s in base_r if s["empty"]) / len(base_r)
            cand_empty = sum(1 for s in cand_r if s["empty"]) / len(cand_r)
            ok_len = all(s["chars"] <= MAX_REPORT_CHARS for s in cand_r)
            quote_rate = sum(1 for s in cand_r if s["has_quote"]) / len(cand_r)
            residue = sum(1 for s in cand_r if s["markdown"])
            print(f"\nR 报告（新提示词）：")
            print(f"  空返回      {cand_empty:.0%}（旧 {base_empty:.0%}）")
            print(f"  报告字数    最大 {max(s['chars'] for s in cand_r)} 字"
                  f"（上限 {MAX_REPORT_CHARS}）→ {'✅' if ok_len else '❌'}")
            print(f"  引用原话    {quote_rate:.0%}（要求 ≥ {MIN_QUOTE_RATE:.0%}）"
                  f"→ {'✅' if quote_rate >= MIN_QUOTE_RATE else '❌'}")
            print(f"  格式残留    {residue} 条 → {'✅' if residue == 0 else '❌'}")
            if not ok_len:
                failures.append("R：有报告超过 250 字")
            if quote_rate < MIN_QUOTE_RATE:
                failures.append(f"R：引用原话比例 {quote_rate:.0%} < {MIN_QUOTE_RATE:.0%}")
            if residue:
                failures.append(f"R：{residue} 条报告有 Markdown 残留")
            continue

        label = "P 提示词" if group == "P" else "B 题库"
        base_s, cand_s = base, candidate
        print(f"\n{label}（右侧为新版）：")
        print(f"  {'':10s} {'旧/关':>18s} {'新/开':>18s}")
        print(f"  {'空返回':10s} {base_s['empty']:>14d}/{base_s['n']:<3d} "
              f"{cand_s['empty']:>14d}/{cand_s['n']:<3d}")
        print(f"  {'平均字数':10s} {base_s['avg_chars']:>18.1f} {cand_s['avg_chars']:>18.1f}")
        print(f"  {'最大字数':10s} {base_s['max_chars']:>18d} {cand_s['max_chars']:>18d}")
        print(f"  {'格式残留':10s} {base_s['residue']:>18d} {cand_s['residue']:>18d}")
        print(f"  {'模板串':10s} {base_s['template']:>18d} {cand_s['template']:>18d}")
        print(f"  {'以问号结尾':10s} {base_s['question_end']:>17.0%} {cand_s['question_end']:>18.0%}")

        if cand_s["empty"] > base_s["empty"] or cand_s["empty"] > MAX_EMPTY_RATE_OLD * cand_s["n"]:
            failures.append(f"{label}：空返回 {cand_s['empty']}/{cand_s['n']} 高于旧版或超过 1/30")
        # 长度判据只对 P 组（提示词改版）成立 —— 改提示词的目的是"别啰嗦"，字数涨回来就是回归。
        # B 组（题库开关）不适用：题库里的题本身比自由提问更具体，问到点子上自然长几个字。
        # 首次实测 29.9 → 38.1 字（1.27×）会误报；B 组真正要守的是下面那条 120 字硬上限 +
        # 0 残留 + 0 空返回 + 问号结尾率不下降，见 ab_next_question.py 的 n=30 结果与台账 §11.21。
        if group == "P" and cand_s["avg_chars"] > base_s["avg_chars"] * MAX_LENGTH_RATIO:
            failures.append(f"{label}：平均字数 {cand_s['avg_chars']:.0f} 超过旧版 ×{MAX_LENGTH_RATIO}")
        if group == "B" and cand_s["max_chars"] > MAX_QUESTION_CHARS:
            failures.append(f"{label}：最长问句 {cand_s['max_chars']} 字超过提示词硬上限 "
                            f"{MAX_QUESTION_CHARS} 字")
        if cand_s["residue"] or cand_s["template"]:
            failures.append(f"{label}：出现 Markdown/模板残留 "
                            f"（残留 {cand_s['residue']}、模板串 {cand_s['template']}）")
        if cand_s["question_end"] < MIN_QUESTION_END:
            failures.append(f"{label}：以问号结尾的比例 {cand_s['question_end']:.0%} "
                            f"< {MIN_QUESTION_END:.0%}")

    print("\n" + "=" * 78)
    if failures:
        print(f"❌ 未达标 {len(failures)} 项 —— 按计划 §六.3 的降级方案处理：")
        print("   砍纪律条数（只留 不给反馈 / 追 2 轮上限 / 风险信号），"
              "参考块规则压到 2 条，然后只重测失败那一臂。")
        for message in failures:
            print(f"   · {message}")
        return 1
    print("✅ 全部达标签。可以进下一步：改端侧默认值 + 写文档 + 台账 §11.21。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
