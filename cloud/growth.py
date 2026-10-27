"""跨场成长追踪 —— 2026-10-27 加（P0-1）。

只读历史会话、算聚合，**不训练任何模型**：把每场的总分/四维分/表达指标压成
一条"点"，再回答三个问题：总分在涨还是在跌、哪一维比上一场退步、哪几维
反复失分（薄弱点）。

设计上的三个克制
----------------
* **纯函数**：输入是快照列表（`session_manager.snapshot()` / 落盘那份的格式），
  输出是可直接 jsonify 的纯数据。单测不需要 Flask、不需要磁盘。
* **老数据兼容**：10/27 之前的会话没有 `expression`、未结束/评分失败的会话
  没有 `score` —— 缺什么就留空，绝不编造（同 speech_metrics 的纪律）。
* **薄弱点用"连续低分"而不是"平均分低"**：偶尔一场 4 分说明不了问题，
  两场以上都低于阈值才列出来，避免给用户贴错标签。
"""
import logging

logger = logging.getLogger(__name__)

# 评分维度固定顺序（与 skills/generate_feedback.json、score_report.json 一致，
# 见台账 §11.34 —— 报告正文与评分卡念的是同一套词）。
DIMENSIONS = ("技术正确性", "深度与原理", "工程与场景思考", "表达与结构")

# 薄弱点阈值：单场低于它算"失分"；至少 2 场失分才算薄弱点。
WEAK_SCORE = 6.0
WEAK_MIN_SESSIONS = 2


def _finite(value):
    """只接受 int/float（bool 排除）；其余（None、'?'、NaN）一律 None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value:          # NaN
        return None
    return value


def _expression_summary(expression):
    """把一场里的逐轮表达指标压成一场的汇总；没有数据时各字段为 None。"""
    rounds = [e for e in (expression or []) if isinstance(e, dict)]
    if not rounds:
        return {"avg_speed": None, "fillers": None, "pauses": None,
                "avg_answer_sec": None}

    speeds = [_finite(e.get("chars_per_min")) for e in rounds]
    speeds = [s for s in speeds if s is not None]
    durations = [_finite(e.get("duration_sec")) for e in rounds]
    durations = [d for d in durations if d is not None]
    fillers = sum(int(e.get("fillers") or 0) for e in rounds)
    pauses = [e.get("pauses") for e in rounds if isinstance(e.get("pauses"), int)]

    return {
        "avg_speed": round(sum(speeds) / len(speeds)) if speeds else None,
        "fillers": fillers,
        "pauses": sum(pauses) if pauses else None,
        "avg_answer_sec": round(sum(durations) / len(durations), 1) if durations else None,
    }


def point_of(snapshot):
    """一场会话 → 一个成长点。形状不对就当空的（同 session_store 的取舍）。"""
    if not isinstance(snapshot, dict):
        snapshot = {}
    score = snapshot.get("score") if isinstance(snapshot.get("score"), dict) else {}
    dimensions = {}
    for dim in score.get("dimensions") or []:
        if not isinstance(dim, dict):
            continue
        name = dim.get("name")
        value = _finite(dim.get("score"))
        if name and value is not None:
            dimensions[name] = value

    messages = snapshot.get("messages") or []
    rounds = sum(1 for m in messages
                 if isinstance(m, dict) and m.get("role") == "user")

    return {
        "session_id": snapshot.get("session_id", ""),
        "role": snapshot.get("role", ""),
        "created_at": snapshot.get("created_at"),
        "total": _finite(score.get("total")),
        "dimensions": dimensions,
        "rounds": rounds,
        "expression": _expression_summary(snapshot.get("expression")),
    }


def points_of(snapshots):
    """快照列表 → 按时间升序的点列表（缺 created_at 的排在前面）。"""
    points = [point_of(s) for s in (snapshots or [])]
    points.sort(key=lambda p: (p.get("created_at") or 0))
    return points


def dimension_deltas(points):
    """最近两场「都有评分」的维度对比。

    返回 dict：
        previous / latest：两场的 session_id
        total：两场总分差（任一缺总分则 None）
        dimensions：[{name, previous, latest, delta}]（只列两场都评过的维度）
    不足两场时返回 None。
    """
    scored = [p for p in points if p.get("dimensions")]
    if len(scored) < 2:
        return None
    previous, latest = scored[-2], scored[-1]
    dims = []
    for name in DIMENSIONS:
        before = _finite(previous["dimensions"].get(name))
        after = _finite(latest["dimensions"].get(name))
        if before is None or after is None:
            continue
        dims.append({"name": name, "previous": before, "latest": after,
                     "delta": round(after - before, 1)})
    total = None
    if _finite(previous.get("total")) is not None and _finite(latest.get("total")) is not None:
        total = round(latest["total"] - previous["total"], 1)
    return {
        "previous": previous.get("session_id"),
        "latest": latest.get("session_id"),
        "total": total,
        "dimensions": dims,
    }


def weak_points(points, threshold=WEAK_SCORE, min_sessions=WEAK_MIN_SESSIONS):
    """反复失分的维度：至少 min_sessions 场低于阈值。

    排序：先按失分场次多的，再按平均分低的 —— 用户先看到的是最该练的那个。
    """
    scored = [p for p in points if p.get("dimensions")]
    result = []
    for name in DIMENSIONS:
        values = [_finite(p["dimensions"].get(name)) for p in scored]
        values = [v for v in values if v is not None]
        if len(values) < min_sessions:
            continue
        low = [v for v in values if v < threshold]
        if len(low) < min_sessions:
            continue
        result.append({
            "name": name,
            "sessions": len(values),
            "low_sessions": len(low),
            "average": round(sum(values) / len(values), 1),
            "latest": values[-1],
        })
    result.sort(key=lambda item: (-item["low_sessions"], item["average"]))
    return result


def build_growth(snapshots, limit=20):
    """给 `/api/growth` 用：把最近若干场聚合成一份可直接 jsonify 的报告。"""
    points = points_of(snapshots)[-int(limit):]
    return {
        "points": points,
        "deltas": dimension_deltas(points),
        "weak_points": weak_points(points),
    }
