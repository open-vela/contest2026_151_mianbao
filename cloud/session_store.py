"""会话落盘 —— 让一场面试活过 Flask 重启。

为什么需要它
------------
会话在此之前**只活在内存里**（`session_manager.SessionManager.sessions`）。
云端进程一重启，上一场面试连同最后的报告一起消失：网页变回"等待面试开始"，
报告导不出来，也没法回头看自己上个月答成什么样。对一个用来**长期练习**的工具
来说，这是最难受的一种丢失 —— 恰恰是你最想回看的那一场没有了。

设计上的四条自我约束
--------------------
* **save() 永不抛异常**。落盘发生在面试主链路上（板子正阻塞等我们这个回包），
  磁盘满、权限错、目录被删，都只能记一条日志，绝不能把一次正常的面试变成 500。
* **原子写**（临时文件 + `os.replace`）。P2 的结构化评分跑在**后台线程**里，
  和主线程会先后写同一个文件；半截文件比没有文件更糟 —— 下次读回来是坏的 JSON。
* **文件名白名单**。`session_id` 直接来自请求体（`app.py:59`），而这里要拿它当
  文件名用。只要放宽一个字符（`.`、`/`），`../../` 这种值就能写到目录外面去。
  所以只接受我们自己会生成的形状：uuid 的字符集。
* **落进 `cloud/data/sessions/`，并加进 `.gitignore`** —— 运行期数据是**产物**，不入库。
  （这一条原写作"不落进 `logs/`，那是大赛要求提交的 AI 编码日志目录，运行期数据混进去
  是污染"。`logs/` 已于 2026-09-29 整体移除，约束随之改成本句。）

存储格式就是 `session_manager.snapshot()` 的返回值原样 —— 刻意不做二次加工，
这样"内存里看到的"和"磁盘上存着的"永远一致，读回来能直接喂给 `/api/history`。
"""
import json
import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)

# 与 cloud/app.py 同级：cloud/data/sessions/<session_id>.json
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sessions")

# session_id 白名单。云端新建会话用的是 uuid4()（app.py:69），形状是
# 8-4-4-4-12 的十六进制加连字符；这里宽松到"字母数字下划线连字符，1~64 位"，
# 既覆盖 uuid 也覆盖手工 curl 测试用的短 id，同时把 `/`、`..`、空白、控制字符
# 全部挡在外面。
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SUFFIX = ".json"


def is_valid_id(session_id) -> bool:
    """这个 id 能不能安全地当文件名用。"""
    return bool(isinstance(session_id, str) and _SID_RE.match(session_id))


def _path(session_id):
    """id 合法时返回绝对路径，否则返回 None（调用方据此拒绝，绝不拼接）。"""
    if not is_valid_id(session_id):
        return None
    return os.path.join(DATA_DIR, session_id + SUFFIX)


def save(snapshot) -> bool:
    """把一份快照写进磁盘；成功返回 True，任何失败都返回 False 且不抛异常。

    调用时机是"本轮响应已经准备好了，只差 return" —— 所以这里的耗时只影响
    用户看到回复的延迟，宁可慢一点点也不要丢数据。但**失败绝不能冒泡**。
    """
    try:
        session_id = (snapshot or {}).get("session_id", "")
        path = _path(session_id)
        if path is None:
            logger.warning(f"[落盘] 拒绝非法 session_id，未写入: {session_id!r}")
            return False

        os.makedirs(DATA_DIR, exist_ok=True)
        payload = json.dumps(snapshot, ensure_ascii=False, indent=1)

        # 同目录下的临时文件 —— 必须同目录，跨设备的 os.replace 不是原子操作。
        # 文件名带随机后缀，避免评分线程与主线程同时写时互相踩。
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix=session_id + ".",
                                   suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())   # 断电也不会留下半截内容
            os.replace(tmp, path)       # 原子替换：读者要么看到旧的，要么看到新的
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except Exception as e:
        logger.warning(f"[落盘] 会话保存失败（不影响本轮面试）: {e}")
        return False


def load(session_id):
    """按 id 读回一份快照；不存在或内容损坏时返回 None（同样不抛异常）。"""
    path = _path(session_id)
    if path is None or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        logger.warning(f"[落盘] 会话读取失败 {session_id}: {e}")
        return None

    # 文件名与内容对不上只可能是被人手工改过 —— 当作损坏处理，别把错的数据
    # 当成另一场面试返回给网页。
    if not isinstance(data, dict) or data.get("session_id") != session_id:
        logger.warning(f"[落盘] 文件内容与文件名不符，忽略: {session_id}")
        return None
    return data


def load_latest():
    """磁盘上最近更新的一场会话；一场都没有时返回 None。

    给"重启后网页还能看到上一场"用（P3）。按文件 mtime 排序而不是读进每个文件
    再比 `updated_at` —— 后者要解析全部会话，前者一次 `os.scandir` 就够。
    """
    try:
        entries = [
            e for e in os.scandir(DATA_DIR)
            if e.is_file() and e.name.endswith(SUFFIX)
            and is_valid_id(e.name[:-len(SUFFIX)])
        ]
    except OSError:
        return None    # 目录还不存在：没跑过任何一场，属于正常情况

    if not entries:
        return None
    newest = max(entries, key=_safe_mtime)
    return load(newest.name[:-len(SUFFIX)])


def _safe_mtime(entry):
    """取文件 mtime；文件在遍历中途消失时返回 0（排到最后）而不是抛异常。"""
    try:
        return entry.stat().st_mtime
    except OSError:
        return 0.0


def _first_answer(messages) -> str:
    """候选人说过的第一句话（列表页靠它帮人认出自己那一场）。"""
    for message in messages or []:
        if isinstance(message, dict) and message.get("role") == "user":
            text = (message.get("content") or "").strip()
            if text:
                return text
    return ""


def summary_of(snapshot, mtime=None) -> dict:
    """把一份完整快照压成**列表页真正要的那几个字段**。

    为什么不直接把快照丢给列表页：一场 10 轮的对话有几十 KB，20 条就是几百 KB，
    而列表上只显示时间 / 岗位 / 轮次 / 首句 —— 传整场对话过去纯属浪费。

    `first_answer` 是这里最要紧的字段：公共设备上一天有十个人用过，
    **人靠"我说过什么"认出自己那一场**，光看时间只能定位到"大概"。
    """
    if not isinstance(snapshot, dict):
        snapshot = {}                 # 形状不对就当空的（同 save()/normalize() 的取舍）
    messages = snapshot.get("messages") or []
    first = _first_answer(messages)
    score = snapshot.get("score")

    return {
        "session_id": snapshot.get("session_id", ""),
        "role": snapshot.get("role", ""),
        "created_at": snapshot.get("created_at"),
        "updated_at": snapshot.get("updated_at"),
        "mtime": mtime,
        "rounds": sum(1 for m in messages
                      if isinstance(m, dict) and m.get("role") == "user"),
        "is_finished": bool(snapshot.get("is_finished")),
        "score_total": score.get("total") if isinstance(score, dict) else None,
        "first_answer": (first[:40] + "…") if len(first) > 40 else first,
    }


def list_summaries(limit=20) -> list:
    """列出最近的若干场会话（摘要，按最后写入时间倒序）。

    两处刻意的设计：

    * **先按 mtime 排序取前 N 个，再解析** —— 目录迟早会涨到几百个，每个请求都
      全量解析是不必要的；mtime 是 `stat` 拿的，很便宜，解析才是贵的那个。
    * **单个文件坏掉不能拖垮整个列表** —— 解析失败就跳过。列表页因为一个半截文件
      而 500，比"少显示一条记录"严重得多（同 `load()` 的取舍）。
    """
    try:
        entries = [
            e for e in os.scandir(DATA_DIR)
            if e.is_file() and e.name.endswith(SUFFIX)
            and is_valid_id(e.name[:-len(SUFFIX)])
        ]
    except OSError:
        return []          # 目录还不存在：一场都没跑过，属于正常

    entries.sort(key=_safe_mtime, reverse=True)

    summaries = []
    for entry in entries[:max(0, int(limit))]:
        snapshot = load(entry.name[:-len(SUFFIX)])
        if snapshot is None:
            continue       # 坏文件 / 内容与文件名不符 —— 跳过，不影响别人
        summaries.append(summary_of(snapshot, _safe_mtime(entry) or None))
    return summaries
