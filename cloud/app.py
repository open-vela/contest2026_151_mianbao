"""
AI模拟面试官 — 云端 Flask 服务
负责：C同学
功能：接收端侧音频，调用 xiaomi mimo API 进行 ASR → LLM → TTS
"""
from flask import Flask, request, jsonify
import base64, uuid, logging
from asr_service import asr_audio_to_text
from llm_service import llm_interview
from tts_service import tts_text_to_audio
from session_manager import SessionManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
session_manager = SessionManager()

@app.route('/api/interview', methods=['POST'])
def handle_interview():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"type": "error", "text": "请求体不能为空", "tts_audio": "", "session_id": "", "next_action": "finish"}), 400
        session_id = data.get('session_id', '')
        audio_base64 = data.get('audio', '')
        audio_format = data.get('audio_format', 'wav')
        role = data.get('role', '产品经理')
        state = data.get('state', '')
        history = data.get('history', [])
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"创建新会话: {session_id}")
        logger.info(f"[session={session_id}] 开始 ASR...")
        user_text = asr_audio_to_text(audio_base64, audio_format)
        if not user_text:
            return jsonify({"type": "error", "text": "未能识别到有效语音，请重试", "tts_audio": "", "session_id": session_id, "next_action": "continue"})
        session = session_manager.get_or_create_session(session_id, role)
        session.add_user_message(user_text)
        logger.info(f"[session={session_id}] 调用 LLM...")
        llm_result = llm_interview(role, session.get_history(), state)
        ai_text = llm_result.get('text', '')
        next_action = llm_result.get('next_action', 'continue')
        session.add_ai_message(ai_text)
        logger.info(f"[session={session_id}] 开始 TTS...")
        tts_audio_base64 = tts_text_to_audio(ai_text)
        return jsonify({"type": "question" if next_action == "continue" else "report", "text": ai_text, "tts_audio": tts_audio_base64, "session_id": session_id, "next_action": next_action})
    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        return jsonify({"type": "error", "text": f"服务器内部错误: {str(e)}", "tts_audio": "", "session_id": session_id if 'session_id' in locals() else '', "next_action": "continue"}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "AI模拟面试官云端服务运行中"})

if __name__ == '__main__':
    logger.info("启动 AI模拟面试官 云端服务...")
    app.run(host='0.0.0.0', port=5000, debug=True)
