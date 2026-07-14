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
        now = time.time()
        expired = [sid for sid, sess in self.sessions.items() if now - sess.updated_at > max_age]
        for sid in expired:
            del self.sessions[sid]
