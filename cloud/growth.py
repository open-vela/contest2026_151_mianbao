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
from datetime import date, datetime, timedelta

import interview_spec

logger = logging.getLogger(__name__)

# 评分维度固定顺序：唯一来源是 interview_spec（2026-11-01 收拢，别再在这里手写）。
DIMENSIONS = interview_spec.DIMENSION_NAMES

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
    weak_items = []
    for dim in score.get("dimensions") or []:
        if not isinstance(dim, dict):
            continue
        name = dim.get("name")
        value = _finite(dim.get("score"))
        if name and value is not None:
            dimensions[name] = value
            if value < WEAK_SCORE:
                text = (dim.get("comment") or dim.get("evidence") or "").strip()
                weak_items.append({
                    "dimension": name,
                    "score": value,
                    "text": text or f"{name}偏弱",
                })

    messages = snapshot.get("messages") or []
    rounds = sum(1 for m in messages
                 if isinstance(m, dict) and m.get("role") == "user")

    return {
        "session_id": snapshot.get("session_id", ""),
        "role": snapshot.get("role", ""),
        "created_at": snapshot.get("created_at"),
        "total": _finite(score.get("total")),
        "dimensions": dimensions,
        # 本场低于阈值的维度（含最近一次评语），供弱点生命周期聚类。
        "weak_items": weak_items,
        # 没有版本字段的老场次按 v1（四维均分）算；v2 起是 30/30/25/15 加权。
        "scoring_version": score.get("scoring_version", 1),
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


# ---------------------------------------------------------------- 弱点生命周期
# 2026-11-01：借鉴同作者 myagent 的 backend/profile.py（MIT）。
# 只做**云端聚合**，板子不参与；给网页成长页显示"这个短板出现过几次、
# 最近一次是什么时候、下次建议什么时候复习、是不是已经改善/归档"。
REVIEW_INTERVALS = (1, 3, 7, 14)   # 简化版 SM-2：1/3/7/14 天
ARCHIVE_AFTER_GOOD = 3             # 连续 3 次评估 >= 阈值且改善过 → 归档


def _date_of(value):
    """created_at 可能是 unix 秒（float）或 ISO 字符串；转成 date，失败返回 None。"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).date()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _quality(score):
    """0~10 的维度分 → 0~5 的复习质量（阈值同 myagent）。"""
    if score is None:
        return 2
    if score >= 8.5:
        return 5
    if score >= 7.0:
        return 4
    if score >= 5.5:
        return 3
    if score >= 4.0:
        return 2
    return 0


def weak_lifecycle(points, today=None):
    """把「同一维度反复低分」聚合成有生命周期的薄弱项。

    输入是 `point_of()` 的点（按时间升序）。只统计**该维度确实被评过**的场次：
    某场里模型漏评该维度（missing）不算"改善"，也不中断连续低分。

    返回每项：
      dimension / text / times_seen / first_seen / last_seen / latest_score /
      worst_score / good_streak / improved / archived / interval_days /
      next_review / due
    """
    today = today or date.today()
    scored = [p for p in (points or [])
              if isinstance(p, dict) and isinstance(p.get("dimensions"), dict)
              and p.get("dimensions")]

    # 先按维度收集"被评过"的场次（保持时间顺序）
    by_dim = {}
    for point in scored:
        for name, value in point["dimensions"].items():
            if name in interview_spec.DIMENSION_NAMES:
                by_dim.setdefault(name, []).append((point, value))

    out = []
    for name, assessments in by_dim.items():
        if not any(value < WEAK_SCORE for _, value in assessments):
            continue        # 从没低过，不算薄弱项

        first_seen = last_seen = None
        times_seen = 0
        sessions = []
        latest_text = ""
        latest_score = None
        worst_score = None
        good_streak = 0
        interval_days = 1
        review_streak = 0
        next_review = None

        for point, value in assessments:
            when = _date_of(point.get("created_at"))
            latest_score = value
            worst_score = value if worst_score is None else min(worst_score, value)

            if value < WEAK_SCORE:
                times_seen += 1
                if when is not None:
                    first_seen = first_seen or when
                    last_seen = when
                sid = point.get("session_id") or ""
                if sid and sid not in sessions:
                    sessions.append(sid)
                for item in point.get("weak_items") or []:
                    if item.get("dimension") == name and item.get("text"):
                        latest_text = item["text"]
                        break
                good_streak = 0
                interval_days = 1
                review_streak = 0
                if when is not None:
                    next_review = when + timedelta(days=interval_days)
            else:
                good_streak += 1
                if _quality(value) >= 3:
                    interval_days = REVIEW_INTERVALS[min(review_streak,
                                                         len(REVIEW_INTERVALS) - 1)]
                    review_streak += 1
                else:
                    interval_days = 1
                    review_streak = 0
                if when is not None:
                    next_review = when + timedelta(days=interval_days)

        improved = times_seen >= 2 and good_streak >= 2
        archived = improved and good_streak >= ARCHIVE_AFTER_GOOD
        out.append({
            "dimension": name,
            "text": latest_text or f"{name}偏弱",
            "times_seen": times_seen,
            "first_seen": first_seen.isoformat() if first_seen else None,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "latest_score": latest_score,
            "worst_score": worst_score,
            "good_streak": good_streak,
            "improved": improved,
            "archived": archived,
            "interval_days": interval_days,
            "next_review": None if archived or next_review is None
                           else next_review.isoformat(),
            "due": bool(not archived and next_review is not None
                        and next_review <= today),
        })

    # 活跃的在前；同状态按出现次数、再按下次复习日期。
    out.sort(key=lambda item: (item["archived"], -item["times_seen"],
                               item["next_review"] or "9999-12-31"))
    return out


def build_growth(snapshots, limit=20):
    """给 `/api/growth` 用：把最近若干场聚合成一份可直接 jsonify 的报告。"""
    points = points_of(snapshots)[-int(limit):]
    versions = sorted({p.get("scoring_version", 1)
                       for p in points if p.get("dimensions")})
    return {
        "points": points,
        "deltas": dimension_deltas(points),
        "weak_points": weak_points(points),
        "weak_lifecycle": weak_lifecycle(points),
        # 跨版本提示：v1（均分）和 v2（加权）的分数不在一个尺度上，
        # 前端看到 version_mixed 时应提示"趋势仅供参考"。
        "scoring_versions": versions,
        "version_mixed": len(versions) > 1,
    }
