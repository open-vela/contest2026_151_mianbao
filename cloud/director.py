# -*- coding: utf-8 -*-
"""云端导演环（2026-11-01，思路取自同作者 myagent 的"双环"）。

分工：
  * 设备实时环负责"什么时候录、什么时候放"（端侧状态机，不动）；
  * 云端导演环负责**本轮该深入 / 换角度 / 换主题**（本模块，纯规则）；
  * 模型只负责把选定的动作写成一句像人说的话。

为什么不让模型自己决定动作：它数不准轮次、会抄自己、会在长会话里一直追同一个点。
为什么不多调一次模型：硬件链路每轮都在等这句回应，多一次调用就是多几秒；
这里的判据全部来自**上一答的字面信号**，零额外成本。

判据故意保守：只在 background / technical 两段生效；开场和反问不干预。
"""

# 与 skills/next_question.json 的压力规则对齐（同一道题最多追 1/2/3 轮）。
DEPTH_CAP = {"温和": 1, "标准": 2, "压力": 3}

# 空泛词：出现这些词但拿不出对象/动作/证据时，说明这一答不够实。
VAGUE_WORDS = ("负责", "优化", "提升", "主导", "参与", "做了", "一些",
               "大概", "可能", "差不多", "挺好的")

ACTION_TEXT = {
    "deeper": "深入一层 —— 顺着刚才的点追边界、取舍或代价，不要换题",
    "angle": "同层换角度 —— 换个场景、规模或反例，把同一个点问实，不要原样重复",
    "switch_topic": "换主题 —— 这个点已经问够或问不动了，转向同一项目里的另一个主题",
}


def signal(answer: str) -> str:
    """一句话的字面质量：empty / thin / normal / substantive。

    不判断对错，只看"有没有可继续追问的信息量"：
      * 太短 / 只有问候 → thin
      * 有长度、有数字或技术细节 → substantive
      * 空泛词多、没数字 → thin
    这是一个**启发式**，只用于导演的动作选择，不参与评分。
    """
    text = (answer or "").strip()
    if not text:
        return "empty"
    length = len(text)
    digits = sum(ch.isdigit() for ch in text)
    vague = sum(1 for word in VAGUE_WORDS if word in text)

    if length >= 80 and (digits >= 2 or length >= 120):
        return "substantive"
    if length < 30:
        return "thin"
    if vague >= 2 and digits == 0:
        return "thin"
    return "substantive" if length >= 60 and digits >= 1 else "normal"


def _trailing_streak(signals, wanted):
    count = 0
    for item in reversed(signals):
        if item in wanted:
            count += 1
        else:
            break
    return count


def decide(stage, pressure, last_answer, recent_answers=()):
    """返回 (action, reason)；不该干预时返回 (None, "")。

    ``recent_answers`` 是**不含** last_answer 的历史候选人回答（按时间升序），
    next_question 会从 history 里取最近几条。
    """
    if stage not in ("background", "technical"):
        return None, ""

    answers = [a for a in (recent_answers or []) if (a or "").strip()]
    answers.append(last_answer)
    signals = [signal(a) for a in answers]
    last = signals[-1] if signals else "empty"
    thin_streak = _trailing_streak(signals, {"thin", "empty"})
    strong_streak = _trailing_streak(signals, {"substantive"})
    cap = DEPTH_CAP.get(pressure, DEPTH_CAP["标准"])

    if last == "empty":
        return "angle", "这一轮没答出内容，换个更具体的问法"
    if thin_streak >= 2:
        return "switch_topic", "连续两轮空泛/没内容，这个点问不动了"
    if last == "thin":
        return "angle", "回答偏空泛，换角度要一个具体例子"
    if strong_streak >= cap:
        return "switch_topic", f"已经连着深挖 {strong_streak} 轮（{pressure}档上限 {cap}）"
    return "deeper", "上一答有具体信息，可以再往下追一层"


def hint(stage, pressure, last_answer, recent_answers=()):
    """拼成注入提示词的一行要求；不该干预时返回空串。"""
    action, reason = decide(stage, pressure, last_answer, recent_answers)
    if not action:
        return ""
    return f"【导演】本轮动作：{ACTION_TEXT[action]}（{reason}）。"
