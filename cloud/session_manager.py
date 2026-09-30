"""
AI模拟面试官 — 会话管理
负责：C同学
"""
import time, logging
logger = logging.getLogger(__name__)

class InterviewSession:
    def __init__(self, session_id: str, role: str):
        self.session_id = session_id
        self.role = role
        self.history = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.question_count = 0
        self.is_finished = False
        # P2 的结构化评分。**默认 None**（未评分 / 评分失败 / 老数据）——
        # 消费方（网页、导出）都必须能接受它不存在，见 snapshot() 的注释。
        self.score = None
    def add_user_message(self, text: str):
        self.history.append({"role": "user", "content": text})
        self.updated_at = time.time()
    def add_ai_message(self, text: str):
        self.history.append({"role": "assistant", "content": text})
        self.question_count += 1
        self.updated_at = time.time()
    def get_history(self):
        return self.history
    def finish(self):
        self.is_finished = True
        self.updated_at = time.time()

class SessionManager:
    def __init__(self):
        self.sessions = {}
    def get_or_create_session(self, session_id: str, role: str) -> InterviewSession:
        if session_id in self.sessions:
            return self.sessions[session_id]
        session = InterviewSession(session_id, role)
        self.sessions[session_id] = session
        return session
    def get_session(self, session_id: str):
        return self.sessions.get(session_id)
    def clean_expired_sessions(self, max_age: int = 3600):
        """清掉太久没更新的会话（默认 1 小时）。

        调用点在 `app.py` 的**新建会话**路径上 —— 正在进行的会话不在那条路径上，
        所以绝不会被误清。清理只影响内存；会话每轮都落盘（见 cloud/session_store.py），
        磁盘那份不受影响。
        """
        now = time.time()
        expired = [sid for sid, sess in self.sessions.items() if now - sess.updated_at > max_age]
        for sid in expired:
            # 用 pop 而不是 del：这条路径今天看着不会并发，但"顺手删一个可能已经
            # 不存在的键"是 KeyError 的经典来源，而它的后果是 500 —— 对一次面试来说
            # 代价远大于这五个字符。
            self.sessions.pop(sid, None)

    # ------------------------------------------------------------------
    # 以下两个方法**只读**，专供网页展示用（cloud/app.py 的 /api/history）。
    # 不创建、不修改、不清理任何会话状态，因此对板子那条链路没有任何影响。
    # ------------------------------------------------------------------
    def get_latest_session(self):
        """返回最近更新的一场会话；一个会话都没有时返回 None。"""
        if not self.sessions:
            return None
        return max(self.sessions.values(), key=lambda s: s.updated_at)

    def snapshot(self, session_id: str = None):
        """把一场会话导出成可直接 jsonify 的纯数据；找不到则返回 None。

        ⚠️ 刻意只**读取**、不往 history 的字典里加字段（比如时间戳）：
        history 会被原样送进 LLM 的 `messages` 参数（见 llm_service.next_question），
        多出来的键可能被 OpenAI SDK 一并序列化发出去。要展示的信息一律在此
        新建字典，绝不改动 session.history 本身。
        """
        session = self.sessions.get(session_id) if session_id else self.get_latest_session()
        if session is None:
            return None

        # 先取快照，避免遍历时工作线程正好在 append
        messages = list(session.history)
        return {
            "session_id": session.session_id,
            "role": session.role,
            "question_count": session.question_count,
            "is_finished": session.is_finished,
            # P2 的评分由**后台线程**写入（见 app.py 的 _start_scoring），所以这里
            # 读到的可能是旧值 —— 评分的消费者只有网页和导出，晚一拍无妨；
            # 而它**绝不进端侧那条响应**（那边是 app.py 里单独 jsonify 的固定字段）。
            "score": session.score,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
