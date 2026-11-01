"""面试的节奏：第几轮该走哪一段。

为什么把"节奏"放在代码里，而不是写进提示词（台账 §11.40）
--------------------------------------------------------
在此之前，整场面试只有一个节奏：**一直问，问到第 11 轮出报告**。提示词里只有三条
通则（不给反馈 / 同题最多追两轮 / 模糊词追一层），没有任何"这一轮该干什么"。

十个回合问下来，形状是平的 —— 没有"深挖 → 技术 → 反问"的推进，也没有收尾的仪式感。
用户的原话是"提问节奏参考一下 myagent"。

**但"让模型自己数轮次"是这个项目反复验证过不可靠的事**（它数不准，而且会抄自己）。
所以分工是：

    **代码决定"现在处于哪一段"，模型决定"这一段里问什么"。**

这一段的目标文本放在 `skills/next_question.json` 的 `stages` 里（那是提示词内容，
改措辞不用动代码）；本模块只负责按轮次取出对应的一段。

段表（1-based 轮次，与端侧"按 K1"的次数一一对应）
------------------------------------------------
    第 1 轮       开场      回应他的自述 + 请他挑一个项目讲具体
    第 2~3 轮     背景深挖  顺着那个项目往下钻
    第 4~9 轮     技术追问  顺着他的项目往原理/取舍/迁移上追（**只有这一段带参考块**）
    第 10 轮      反问      「你有什么想问我的吗」
    第 11 轮      ——        走 generate_feedback 出报告，不进本模块

第 11 轮不是"段"：结束判据 `len(history) - 1 >= HISTORY_FINISH_THRESHOLD`（= 20 条）
在那之前就把它分流去生成报告了，`next_question` 根本不会被调用 —— 所以这里查不到
第 11 轮是**正常**的，不是漏了。

轮数对照（别被 10 和 11 绕进去）
------------------------------
端侧第 N 次按 K1 时，`next_question` 收到的是**不含本轮回答**的历史，长度 `2N-2`，
所以 `len(history) // 2 + 1 == N`。而结束判据是 `2N-2 >= 20` → N ≥ 11。
即：**前 10 轮是问答，第 11 轮是报告**（README §4.5.3 一直这么写）。

可配置轮数（2026-11-01）
------------------------
`target_rounds` 指**问答轮数**（不含报告），默认 10。`plan_for(N)` 按
「开场 1 + 背景约 25% + 技术约 65% + 反问 1」动态缩放；N=10 时逐字返回
上面的 `STAGE_PLAN`，节奏不变。报告在第 N+1 次回答后出（`llm_interview` 用
`2 × target_rounds` 判历史长度）。
"""

# (段名, 起始轮, 结束轮) —— 默认 10 个问答轮的段表；`stage_key()` 按它查。
STAGE_PLAN = (
    ("opening",    1,  1),
    ("background", 2,  3),
    ("technical",  4,  9),
    ("ask_back",  10, 10),
)

# 默认 10 个问答轮 + 1 轮报告 = 11 次 K1。
TOTAL_ROUNDS = 11

# 可配置轮数（2026-11-01）：用户要"演示 5~6 轮、正式数十轮"。
# `target_rounds` 指**问答轮数**（不含最后出报告的那一次 K1）。
MIN_TARGET_ROUNDS = 4
MAX_TARGET_ROUNDS = 30
DEFAULT_TARGET_ROUNDS = TOTAL_ROUNDS - 1      # 10


def normalize_target(value):
    """把外部传来的目标轮数收进 [4, 30]；坏输入回默认 10。

    只接受整数或纯数字字符串 —— 1.5 / 8.0 这类浮点一律按坏输入处理，
    不静默截断（"6.9 轮"到底是 6 还是 7，不如回默认）。
    """
    if isinstance(value, bool) or value is None:
        return DEFAULT_TARGET_ROUNDS
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        return DEFAULT_TARGET_ROUNDS
    return max(MIN_TARGET_ROUNDS, min(MAX_TARGET_ROUNDS, number))


def plan_for(target_rounds):
    """按目标问答轮数生成段表。

    默认 10 轮时**逐字返回** `STAGE_PLAN`，保证现有节奏不变；其它轮数按
    「开场 1 + 背景约 25% + 技术约 65% + 反问 1」缩放，且至少留 1 轮技术追问。
    """
    total = normalize_target(target_rounds)
    if total == DEFAULT_TARGET_ROUNDS:
        return STAGE_PLAN

    remaining = total - 2                 # 去掉开场和反问
    background = max(1, int(round(remaining * 0.25)))
    background = min(background, remaining - 1)   # 至少留 1 轮技术
    bg_last = 1 + background
    return (
        ("opening",    1, 1),
        ("background", 2, bg_last),
        ("technical",  bg_last + 1, total - 1),
        ("ask_back",   total, total),
    )


def target_from_stage_plan(plan):
    """段表 → 问答轮数（最后一段的结束轮）。仅用于测试/日志。"""
    return plan[-1][2]


def stage_key(round_number, target_rounds=None):
    """第 `round_number` 轮走哪一段；不在计划里（该出报告了）返回 `None`。

    `target_rounds` 为空时用默认 10 轮段表（保持旧行为）；传了就按目标轮数
    动态生成。对非法输入返回 None 而不是抛异常 —— 它跑在面试主链路上，
    一个坏的轮次算错不该让整场面试变成 500（同 `session_store.save()` 的取舍）。
    """
    if not isinstance(round_number, int) or isinstance(round_number, bool):
        return None
    plan = STAGE_PLAN if target_rounds is None else plan_for(target_rounds)
    for key, first, last in plan:
        if first <= round_number <= last:
            return key
    return None


def uses_question_bank(key) -> bool:
    """只有「技术追问」那一段才该带题库参考块。

    背景深挖问的是**他自己的项目**，题库帮不上忙 —— 在那一段注入参考题，只会把话题
    从他自己的经历上拽走。顺带每轮省下两百多字的提示词。
    """
    return key == "technical"


# 反问环节的**兜底问句**。
#
# 为什么这一句要用代码兜住（2026-10-01，首次真实排练暴露）：第 10 轮明明注入了
# 「【当前阶段：反问环节】用一句话自然过渡，然后问他『有什么想问我的吗』」，
# 模型却**接着追问项目细节** —— 历史里九个回合都在追项目，那个势头压过了提示词中段的
# 阶段说明。和 §11.20「模型抄自己」是同一个机制。
#
# 这一句是整场里**唯一可以不靠模型**的话：它没有个性化内容，就是要请对方提问。
# 所以判据能定死的就别交给模型 —— 同 reply_guard / report_guard 的取舍。
ASK_BACK_FALLBACK = "好的，我的问题问完了。您有什么想问我的吗？"


def is_ask_back(text) -> bool:
    """这句话是不是在请候选人提问。

    判据**故意宽**：只要出现「想问」就算。复盘时能看到模型的各种自然说法
    （"有什么想了解的""有没有想问我的"），收紧了只会误伤自己的正常输出。
    """
    return "想问" in (text or "")
