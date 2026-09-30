"""
AI模拟面试官 — LLM 服务（小米 MIMO API）
负责：A同学（统一接口）
"""
import os
import json
import logging
from openai import OpenAI

from finish_guard import match_reason
from question_bank import build_reference_block
from reply_guard import FALLBACK_QUESTION, clean_history, strip_meta
import interview_stage
import report_guard
import score_guard

logger = logging.getLogger(__name__)

# 小米 MIMO API 配置（与 ASR/TTS 统一）
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
LLM_MODEL = "mimo-v2.5"

# 加载 Skills Prompt 模板
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")

# 面试结束判据：历史累计到 20 条（约 10 轮问答）即收尾。
# ⚠️ 两个调用点的 history 长度差 1：next_question() 收到的**不含**本轮回答，
# llm_interview() 收到的**含**本轮回答，所以后者要先减 1 再比。
HISTORY_FINISH_THRESHOLD = 20

# ⚠️ mimo-v2.5 是**推理模型**：它先产出思考（reasoning_content），且 reasoning_tokens
# 与正文**共用** max_tokens 预算。实测思考会吃掉 300~800 token，而各 skill 的
# max_tokens 是按"输出额度"配的（600/800），于是历史越长思考越久、正文余量越小：
#   - 第 10 轮（消息数 21）next_question：reasoning 峰值 801 撞满 800 → 正文 0 token
#   - 上板排练实测：报告轮正文被挤空，用户听到兜底文案"生成报告失败"（6 字）
# 关掉思考后 reasoning_tokens=0，全部预算给正文：实测输出质量无可见下降（追问依旧
# 自然、报告结构完整），且报告轮从 16 秒降到几秒。这是端云链路上**每一轮**都会走的
# 咽喉点，所以集中改在这里。若将来换模型，需重新验证该参数是否被支持。
THINKING_DISABLED = {"thinking": {"type": "disabled"}}


def load_skill(skill_name: str) -> dict:
    """
    加载 Skill Prompt 模板

    Args:
        skill_name: Skill 名称（不含 .json 后缀）

    Returns:
        Skill 配置字典
    """
    skill_path = os.path.join(SKILLS_DIR, f"{skill_name}.json")
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            skill = json.load(f)
        logger.info(f"加载 Skill: {skill_name}")
        return skill
    except Exception as e:
        logger.error(f"加载 Skill 失败: {e}")
        return {}


def call_llm(system_prompt: str, messages: list, temperature: float = 0.7,
             max_tokens: int = 500) -> str:
    """
    调用小米 MIMO LLM API

    Args:
        system_prompt: 系统提示词
        messages: 对话消息列表
        temperature: 温度参数
        max_tokens: 最大生成 token 数

    Returns:
        LLM 生成的文本
    """
    try:
        client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL
        )

        # 构建完整消息列表
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        logger.info(f"LLM 请求: model={LLM_MODEL}, 消息数={len(full_messages)}")

        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=THINKING_DISABLED
        )

        result = completion.choices[0].message.content
        logger.info(f"LLM 返回: {result[:100]}...")
        return result

    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return ""


# ============================================================
# Skill 实现函数
# ============================================================

def start_interview(role: str) -> dict:
    """
    Skill: start_interview — 开始面试，生成第一个问题

    Args:
        role: 面试岗位，如 "AI 应用开发"、"前端开发工程师"

    Returns:
        {"text": "面试问题", "next_action": "continue"}
    """
    skill = load_skill("start_interview")
    if not skill:
        return {"text": "抱歉，加载面试配置失败。", "next_action": "continue"}

    # 替换 system_prompt 中的变量
    system_prompt = skill["system_prompt"].replace("{role}", role)

    # 调用 LLM
    messages = [{"role": "user", "content": "请开始面试，提出第一个问题。"}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.7),
        max_tokens=skill.get("max_tokens", 500)
    )

    if result:
        return {"text": result, "next_action": "continue"}
    else:
        return {"text": "抱歉，生成问题失败，请重试。", "next_action": "continue"}


def next_question(role: str, history: list, last_answer: str) -> dict:
    """
    Skill: next_question — 根据用户回答生成下一个问题或追问

    Args:
        role: 面试岗位
        history: 完整对话历史 [{"role": "user"/"assistant", "content": "..."}]
        last_answer: 用户的最新回答

    Returns:
        {"text": "下一个问题", "next_action": "continue"}
    """
    skill = load_skill("next_question")
    if not skill:
        return {"text": "抱歉，加载面试配置失败。", "next_action": "continue"}

    # ---- 题库参考块（见 cloud/question_bank.py 与台账 §11.21）----
    #
    # ⚠️ 三条纪律，改这里之前先读 cloud/question_bank.py 的 docstring：
    #  1. 参考块**只进 system prompt，绝不进 history**，也不许用 assistant 消息承载 ——
    #     history 里出现参考题就是给模型递了它自己的范例，那正是 §11.20「模型抄自己」
    #     的燃料（自我强化、越写越长、且不会自愈）。
    #  2. 候选词用**候选人刚说的那段话**：他要接着答的内容就是选题方向。
    #  3. 岗位映射不到题库（例如仍是旧的「产品经理」默认值）、或题库缺失时，
    #     build_reference_block 返回 ""，提示词与没有题库时完全一致 —— 优雅退化为自由提问。
    # ---- 本轮属于哪一段（见 cloud/interview_stage.py）----
    #
    # 分工：**代码决定"现在处于哪一段"，模型决定"这一段里问什么"**。
    # 不让模型自己数轮次 —— 它数不准，而且会从历史里学（§11.20 的教训）。
    #
    # ⚠️ 这里收到的 history **不含本轮回答**（llm_interview 传的是 history[:-1]），
    #    长度是 2N-2，所以 +1 才是"端侧第几次按 K1"的那一轮。
    round_number = len(history) // 2 + 1
    stage = interview_stage.stage_key(round_number)

    # ---- 题库参考块 ----
    # ⚠️ **只在技术问答那一段取**：背景深挖问的是他自己的项目，题库帮不上忙，
    #    注进去只会把话题从他自己的经历上拽走（顺带每轮省下两百多字提示词）。
    asked_text = " ".join(m.get("content", "") for m in history if m.get("role") == "assistant")
    reference_block = ""
    if interview_stage.uses_question_bank(stage):
        reference_block = build_reference_block(role, last_answer, asked_text, len(history) // 2)

    system_prompt = skill["system_prompt"]

    # ---- 当前阶段 ----
    stage_text = (skill.get("stages") or {}).get(stage) if stage else None
    if stage_text:
        system_prompt = system_prompt.replace(
            "{stage_block}",
            f"【当前阶段：{stage_text.get('name', '')}】\n{stage_text.get('instruction', '')}")
        logger.info(f"[节奏] 第 {round_number} 轮 = {stage_text.get('name')}")
    else:
        # 查不到就整块去掉，提示词退化成"没有阶段"的样子（同参考块的优雅退化）。
        # 正常情况下第 11 轮走不到这里 —— 它被结束判据分流去生成报告了。
        logger.warning(f"[节奏] 第 {round_number} 轮查不到阶段（不该发生）")
        system_prompt = system_prompt.replace("{stage_block}\n\n", "")
        system_prompt = system_prompt.replace("{stage_block}", "")

    if reference_block:
        # 台账 §11.22 留了个悬案：「参考块到底注进去了没有」。它只改 system prompt，
        # 不进 history、不在回复里留痕，所以事后从任何输出都反推不出来 —— 只能当场记。
        logger.info(f"[题库] 第 {round_number} 轮注入参考块：{len(reference_block)} 字"
                    f"（检索词 {len(last_answer)} 字）")
        system_prompt = system_prompt.replace("{reference_block}", reference_block)
    else:
        # ⚠️ 这句日志要**分清两种"没有参考块"**：
        #    a) 这一段本来就不用（深挖/反问问的是他自己的经历）—— 正常；
        #    b) 该用却拿不到（岗位对不上题库 / 题库没随代码拷过来 / 他这轮说得太少）。
        # 混成一句话是 2026-10-01 加阶段时才发现的：照旧写法，第 1~3 轮会报
        # "岗位未映射 / 题库缺失"，把人往错的方向带。
        if interview_stage.uses_question_bank(stage):
            logger.info("[题库] 本轮该有参考块却拿不到（岗位未映射 / 题库缺失 / "
                        "候选人这轮说得太少）—— 退化为自由提问")
        else:
            name = stage_text.get("name") if stage_text else "无阶段"
            logger.info(f"[题库] 第 {round_number} 轮（{name}）本就不注入参考块 "
                        f"—— 这一段问的是他自己的经历")
        # 空块要连占位符所在的那一行一起去掉，否则留下连续空行
        system_prompt = system_prompt.replace("{reference_block}\n\n", "")
        system_prompt = system_prompt.replace("{reference_block}", "")
    # {role} 必须**最后**替换：它来自请求体，先替换的话值里若含 {reference_block}
    # 之类的字样会被当成占位符二次替换。
    system_prompt = system_prompt.replace("{role}", role)

    # 构建消息（包含历史）。
    # ⚠️ 历史先过 reply_guard.clean_history()：§11.20 那个故障的致命处是"模型抄自己"
    # ——被污染的输出原样存进 history，下一轮又成了它自己的范例，**不会自愈**。
    # 读的时候过一道闸，已经脏掉的会话就能自己恢复，不必重启云端重开一场。
    # 干净历史经过这里是逐条 no-op（见 reply_guard 的"干净文本零改动"）。
    messages = clean_history(history)
    messages.append({"role": "user", "content": f"候选人回答：{last_answer}\n\n请根据回答决定是追问还是提出新问题。"})

    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.7),
        max_tokens=skill.get("max_tokens", 800)
    )

    # 判断是否结束面试（超过 10 轮）
    next_action = "finish" if len(history) >= HISTORY_FINISH_THRESHOLD else "continue"

    if result:
        # 出去的字也要过闸：这段文本会被 TTS **逐字念出来**，绝不能带「判断：/理由：/---」。
        # 提示词层面已经禁过一轮，但 9/18 的 A/B 证明光靠提示词挡不住被污染的历史
        # （删掉提示词里的错误示例后，模型改从历史里学那个格式）。剥空了用兜底问句顶上，
        # 保证候选人听到的永远是"一句话 + 一个问号"。
        cleaned = strip_meta(result)
        if not cleaned:
            logger.warning("next_question 的回复整段都是元叙述，已替换为兜底问句：%r", result[:120])
            cleaned = FALLBACK_QUESTION
        return {"text": cleaned, "next_action": next_action}
    else:
        return {"text": "抱歉，生成问题失败，请重试。", "next_action": "continue"}


def evaluate_answer(role: str, question: str, answer: str) -> dict:
    """
    Skill: evaluate_answer — 对单个回答进行打分和点评

    Args:
        role: 面试岗位
        question: 面试问题
        answer: 用户回答

    Returns:
        {"text": "点评", "score": 8, "dimensions": {"logic": 8, "professionalism": 7, "clarity": 9}}
    """
    skill = load_skill("evaluate_answer")
    if not skill:
        return {"text": "评估失败", "score": 0, "dimensions": {}}

    system_prompt = skill["system_prompt"].replace("{role}", role)

    user_content = f"问题：{question}\n候选人回答：{answer}\n\n请从逻辑性、专业性、表达清晰度三个维度打分（1-10），并给出简短点评。"

    messages = [{"role": "user", "content": user_content}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.5),
        max_tokens=skill.get("max_tokens", 400)
    )

    if result:
        # 简单解析（实际可优化为 JSON 格式输出）
        return {"text": result, "score": 0, "dimensions": {}}
    else:
        return {"text": "评估失败", "score": 0, "dimensions": {}}


def generate_feedback(role: str, history: list) -> dict:
    """
    Skill: generate_feedback — 面试结束生成完整评估报告

    Args:
        role: 面试岗位
        history: 完整对话历史

    Returns:
        {"text": "评估报告", "next_action": "finish"}
    """
    skill = load_skill("generate_feedback")
    if not skill:
        return {"text": "生成报告失败", "next_action": "finish"}

    system_prompt = skill["system_prompt"].replace("{role}", role)

    # 构建对话摘要
    conversation = "\n".join([f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}" for m in history])
    user_content = f"以下是完整面试对话：\n\n{conversation}\n\n请生成详细的面试评估报告。"

    messages = [{"role": "user", "content": user_content}]
    temperature = skill.get("temperature", 0.7)
    max_tokens = skill.get("max_tokens", 1000)

    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

    # ---- 报告闸：缺「」引用就补一次纠偏重试（见 cloud/report_guard.py）----
    #
    # 为什么要在代码里补这一道：提示词把"必须至少引用一处候选人的原话"写成了硬性
    # 要求（还注明"这一条没有例外"），但 2026-09-30 的真机实测证明**它在退化输入
    # 下会失效** —— 候选人整场只说了几个字时，四个维度全写"未涉及"，模型把引用
    # 也一起丢了（台账 §11.27）。同 §11.21 的结论：提示词是"劝"，拦不住的要在
    # 代码里拦。
    #
    # 只在**缺**的时候才多花一次调用：正常轮次（排练 11 轮全部命中过）成本为零。
    if result and not report_guard.has_quote(result):
        logger.warning("[报告] 首轮没有「」引用，补一次纠偏重试")
        retried = call_llm(
            system_prompt=system_prompt,
            messages=messages + [
                {"role": "assistant", "content": result},
                {"role": "user", "content": report_guard.RETRY_HINT},
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        if retried and report_guard.has_quote(retried):
            logger.info("[报告] 重试后拿到了「」引用")
            result = retried
        else:
            # 重试仍不合格 → **照发**，只记日志。
            # 宁可用一份缺引用的报告，也不要为了凑格式把已经生成好的内容丢掉、
            # 或者机械拼一句引用上去 —— 那份报告本身是好的，缺的只是格式要求。
            logger.warning("[报告] 重试后仍无「」引用，按原样返回（不拦）")

    # 软核对：引用的话是不是真出自候选人。**只记日志**——提示词允许"摘关键词
    # 连起来"，那种引用本来就不是连续原文，拿它当判据会大面积误报。
    if result:
        unmatched = report_guard.check_quote_evidence(result, history)
        if unmatched:
            logger.info("[报告] 有 %d 处引用未能与候选人原话逐字对上（关键词拼接属正常）"
                        "：%s", len(unmatched), unmatched[:2])

    if result:
        return {"text": result, "next_action": "finish"}
    else:
        return {"text": "生成报告失败", "next_action": "finish"}


def _dimensions_block() -> str:
    """把 `score_guard.DIMENSIONS` 拼成提示词里的维度清单。

    维度**只有这一个来源**：提示词模板里不写死，就不会出现"提示词要 5 个维度、
    代码只认 4 个"的漂移 —— 这正是 `score_guard` 把 DIMENSIONS 定成"唯一事实来源"
    时留下的约定（见它的模块 docstring）。
    """
    return "\n".join(f"· {name}" for name in score_guard.DIMENSIONS)


def _qa_pairs(history) -> list:
    """把对话历史配成「面试官问的 / 候选人答的」若干题。

    **为什么配对在代码里做、不交给模型**：题目文本我们本来就有，让模型再吐一遍只会
    多一个出错的地方（可能改写、可能编造）。模型只负责判断，题号是它唯一的"指路牌"。

    第 1 题是特例，**设备上并没有问过它** —— 我们的流程是候选人按 K1 直接开口，
    面试官才回应。这里用 `score_guard.OPENING_QUESTION` **回填**一句标准开场白，
    让复盘读起来像一场完整的面试（候选人第一句通常就是自我介绍）。
    """
    pairs = []
    last_question = score_guard.OPENING_QUESTION
    for message in history or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant":
            last_question = content        # 面试官这句是"下一题"
        elif role == "user":
            pairs.append({"index": len(pairs) + 1,
                          "question": last_question,
                          "answer": content})
    return pairs


def _qa_block(pairs) -> str:
    """把配好的问答排成给模型看的编号清单。"""
    lines = []
    for pair in pairs:
        lines.append(f"第 {pair['index']} 题")
        lines.append(f"面试官：{pair['question']}")
        lines.append(f"候选人：{pair['answer']}")
        lines.append("")
    return "\n".join(lines).strip()


def _attach_questions(items, pairs) -> list:
    """按题号把题目文本挂到逐题复盘上；**越界的题号丢掉**。

    范围校验只能在这里做 —— 闸门（`score_guard`）是纯函数，它不知道这场有几题。
    """
    by_index = {pair["index"]: pair for pair in pairs}
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue                       # 闸门已经滤过一道，这里再兜一次
        pair = by_index.get(item.get("index"))
        if pair is None:
            logger.info("[评分] 逐题复盘里出现越界题号 %r（本场共 %d 题），已丢弃",
                        item.get("index"), len(pairs))
            continue
        out.append({
            "index": pair["index"],
            "question": pair["question"],
            "evidence": item.get("evidence", ""),
            "suggestion": item.get("suggestion", ""),
        })
    return out


def score_interview(role: str, history: list) -> dict:
    """给一场面试打结构化评分（P2）—— 独立的一次 LLM 调用。

    ⚠️ 三个前提，调用方（app.py 的后台线程 `_start_scoring`）必须满足：

    1. **只在报告轮之后调** —— 没结束的面试没有可评的东西；
    2. **必须在端侧响应返回之后发起** —— 这一次调用要十几秒，放主线程就是把它
       加到板子正阻塞等着的那段时间上；
    3. **返回 `{}` 是正常结果**（模型抽不出 JSON、分数全越界、调用失败都一样），
       调用方只记日志、不要当异常处理。

    Returns:
        `score_guard.normalize()` 收拾过的评分；任何失败都返回 `{}`。
    """
    skill = load_skill("score_report")
    if not skill:
        return {}

    system_prompt = (skill["system_prompt"]
                     .replace("{dimensions}", _dimensions_block())
                     .replace("{role}", role))

    pairs = _qa_pairs(history)
    if not pairs:
        logger.warning("[评分] 这场没有可评的问答（历史里没有候选人发言）")
        return {}

    # ⚠️ 输入是**编号问答列表**，不是"整场对话原样丢进去"。两处好处：
    #   1. 模型回 per_question 时用题号指代，不会认错题；
    #   2. **把报告本身排除在评分输入之外** —— 报告在历史末尾，原样丢进去等于让
    #      评分看着自己的结论打分（锚定），评的该是问答、不是结论。
    messages = [{"role": "user",
                 "content": f"以下是这场面试的问答记录（共 {len(pairs)} 题）：\n\n"
                            f"{_qa_block(pairs)}\n\n"
                            f"请给出结构化评分与逐题复盘。"}]

    raw = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.3),
        max_tokens=skill.get("max_tokens", 800)
    )
    if not raw:
        logger.warning("[评分] LLM 返回为空")
        return {}

    parsed = score_guard.extract_json(raw)
    if parsed is None:
        logger.warning("[评分] 模型输出里抽不出 JSON：%r", raw[:120])
        return {}

    score = score_guard.normalize(parsed)
    if not score_guard.is_usable(score):
        logger.warning("[评分] 收拾不出可用的评分（原始 dimensions=%r）",
                       str(parsed.get("dimensions"))[:120])
        return {}

    # 软核对：每个维度的"依据"是不是真出自候选人。**只记日志、不拦**（同
    # report_guard 的取舍）—— 评分已经过闸门、结构可信，"未提及"这类诚实回答
    # 由 verify_evidence 自己跳过；剩下来的措辞出入不值得丢掉整份评分。
    unsupported = score_guard.verify_evidence(score, history)
    if unsupported:
        logger.info("[评分] %d 个维度的依据未能与候选人原话对上（仅供参考）：%s",
                    len(unsupported), unsupported)

    # 逐题复盘：按题号把题目文本挂上去（越界题号在这里丢掉，闸门不知道有几题）
    score["per_question"] = _attach_questions(score.get("per_question"), pairs)
    if len(score["per_question"]) != len(pairs):
        logger.info("[评分] 逐题复盘覆盖 %d/%d 题",
                    len(score["per_question"]), len(pairs))

    return score


def check_timeout(role: str, timeout_duration: int, partial_answer: str = "") -> dict:
    """
    Skill: check_timeout — 用户回答超时打断

    Args:
        role: 面试岗位
        timeout_duration: 超时时长（秒）
        partial_answer: 用户已录制的部分内容

    Returns:
        {"text": "超时提示", "next_action": "continue"}
    """
    skill = load_skill("check_timeout")
    if not skill:
        return {"text": "您思考的时间比较长了，可以先简单回答一下吗？", "next_action": "continue"}

    system_prompt = skill["system_prompt"].replace("{role}", role).replace("{timeout_duration}", str(timeout_duration))

    user_content = f"候选人已思考 {timeout_duration} 秒"
    if partial_answer:
        user_content += f"，已录制的部分内容：{partial_answer}"
    user_content += "\n\n请礼貌地提示候选人可以先做一个简要回答。"

    messages = [{"role": "user", "content": user_content}]
    result = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=skill.get("temperature", 0.5),
        max_tokens=skill.get("max_tokens", 200)
    )

    if result:
        return {"text": result, "next_action": "continue"}
    else:
        return {"text": "您思考的时间比较长了，可以先简单回答一下吗？", "next_action": "continue"}


# ============================================================
# 兼容旧接口
# ============================================================

def _finish_requested(history: list) -> str:
    """候选人这一轮的最后一句是不是在**请求结束面试**；返回命中的白名单词。

    只看最后一条、且必须是 user 消息：本轮的候选人回答就是 `history[-1]`
    （app.py 在调用前刚 add_user_message）。返回原因字符串而不是布尔值，
    是为了让日志能说清"它到底匹配上了哪个词"—— 真误判时那是第一手信息。
    """
    if not history:
        return ""
    last = history[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return ""
    return match_reason(last.get("content", ""))


def llm_interview(role: str, history: list, state: str, audio_base64: str = "") -> dict:
    """
    兼容旧版接口（已被 skill 函数替代）
    """
    if state == "start":
        return start_interview(role)
    elif state == "evaluate":
        if history:
            last_q = history[-2]["content"] if len(history) >= 2 else ""
            last_a = history[-1]["content"] if history else ""
            return evaluate_answer(role, last_q, last_a)
    elif state == "feedback":
        return generate_feedback(role, history)
    else:
        if history:
            # 最后一轮直接出评估报告，而不是再抛一个问题。
            #
            # 端侧只会发 state="recording_finished"（app/ai_interview/main.c:124），
            # 从不发 "feedback" —— 所以上面那个分支在真实链路上不可达，报告一度是
            # 死代码，结尾那段"最终评估"实际是 next_question 在长历史下即兴写的。
            # 结束判据本来就是云端算出来的（见 next_question），这里提前判一次即可，
            # 端侧协议（同回合、同 next_action=finish）完全不变。
            #
            # 第二条结束路径：候选人**用嘴说**"结束吧"。在此之前只能按到第 11 轮，
            # 想练 3 题就必须硬按 11 次 K1。判据在 finish_guard（纯函数、可单测），
            # 这里只做 OR —— 刻意不放进 next_question：那边拿到的 history 比这里
            # 少一条（不含本轮回答），放那儿就得再算一次下标，正是这类错位的高发地。
            # 端侧协议零变化：next_action 本来就是 continue/finish 两个值。
            finish_reason = _finish_requested(history)
            if len(history) - 1 >= HISTORY_FINISH_THRESHOLD or finish_reason:
                if finish_reason:
                    logger.info(f"[结束] 候选人请求结束面试（命中 {finish_reason!r}，"
                                f"实际轮次 {len(history) // 2}），提前生成报告")
                return generate_feedback(role, history)
            return next_question(role, history[:-1], history[-1]["content"])

    return start_interview(role)


# 测试
if __name__ == "__main__":
    print("LLM 服务模块已加载")
    # 只报有没有，不报 key 内容 —— 连前缀也不打（终端输出会进日志、录屏、截图）
    print("API Key: 已配置" if MIMO_API_KEY else "API Key: 未配置")
    print(f"Skills 目录: {SKILLS_DIR}")

    # 测试 start_interview
    print("\n测试 start_interview:")
    result = start_interview("AI 应用开发")
    print(f"结果: {result}")
