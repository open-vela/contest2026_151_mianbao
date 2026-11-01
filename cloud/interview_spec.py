# -*- coding: utf-8 -*-
"""面试评分口径的**唯一来源**（2026-11-01 从同作者 myagent 的 interview_spec 思路拿过来）。

维度名、权重、版本号只在这里定义一次：
  * `score_guard` 用它们清洗模型输出、算总分；
  * `growth` 用它们做跨场维度对比/薄弱点；
  * `llm_service` 用它们拼报告提示词里的维度清单；
  * 网页/PDF 只读评分结果里的 dimensions，不硬编码维度名。

改这里任何一项（维度、权重、分制）都必须递增 SCORING_VERSION —— 否则成长曲线
会把「口径变了」误画成「水平变了」。

版本历史：
  v1 —— 四维简单平均（2026-10-27 之前的场次）
  v2 —— 按 30/30/25/15 加权；缺维度时按已有权重重新归一化（2026-10-31 起）
"""

SCORING_VERSION = 2

# 顺序有语义：评分卡、成长页的维度对比、报告里的维度顺序都按它。
DIMENSIONS = (
    ("技术正确性", 0.30),
    ("深度与原理", 0.30),
    ("工程与场景思考", 0.25),
    ("表达与结构", 0.15),
)

DIMENSION_NAMES = tuple(name for name, _ in DIMENSIONS)
DIMENSION_WEIGHTS = dict(DIMENSIONS)

# 报告提示词里用的中文顿号清单（如「技术正确性、深度与原理、…」）
DIMENSION_TEXT = "、".join(DIMENSION_NAMES)


def weighted_total(dims) -> int:
    """按权重算 0~100 总分（不是四维简单平均）。

    dims 可以是：
      * [{"name": "技术正确性", "score": 8}, ...]
      * {"技术正确性": 8, ...}

    缺维度时只对**已评维度**的权重重新归一化 —— 未考察的维度不应该按 0 分
    拉低总分（与 myagent 的 weighted_overall 同一条规则）。
    """
    if isinstance(dims, dict):
        pairs = dims.items()
    else:
        pairs = ((d.get("name"), d.get("score")) for d in (dims or []) if isinstance(d, dict))
    total = 0.0
    weight_sum = 0.0
    for name, score in pairs:
        weight = DIMENSION_WEIGHTS.get(name, 0.0)
        if not weight or not isinstance(score, (int, float)) or isinstance(score, bool):
            continue
        total += float(score) * weight
        weight_sum += weight
    if weight_sum <= 0:
        return 0
    return int(round(total / weight_sum * 10))
