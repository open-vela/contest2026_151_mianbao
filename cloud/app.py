"""
AI模拟面试官 — 云端 Flask 服务
"""
from flask import Flask, request, jsonify
import uuid
import logging
from llm_service import llm_interview
from asr_service import asr_audio_to_text
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

        # 获取或创建会话
        session = session_manager.get_or_create_session(session_id, role)

        # 如果有音频数据，先进行 ASR 识别
        user_text = ""
        if audio_base64 and state == "recording_finished":
            logger.info(f"[session={session_id}] 开始 ASR 识别...")
            user_text = asr_audio_to_text(audio_base64, audio_format, "zh")
            if user_text:
                logger.info(f"[session={session_id}] ASR 识别结果: {user_text[:100]}...")
                session.add_user_message(user_text)
            else:
                logger.warning(f"[session={session_id}] ASR 识别失败")

        # 调用 LLM 生成回复
        logger.info(f"[session={session_id}] 调用 LLM...")
        llm_result = llm_interview(role, session.get_history(), state, audio_base64)
        ai_text = llm_result.get('text', '')
        next_action = llm_result.get('next_action', 'continue')

        # 将AI回复存入会话
        session.add_ai_message(ai_text)

        # TTS 合成
        logger.info(f"[session={session_id}] 开始 TTS...")
        tts_audio_base64 = tts_text_to_audio(
            ai_text,
            style="专业、友好、有洞察力的面试官"
        )

        return jsonify({
            "type": "question" if next_action == "continue" else "report",
            "text": ai_text,
            "tts_audio": tts_audio_base64,
            "session_id": session_id,
            "next_action": next_action,
            "user_text": user_text  # 返回 ASR 识别结果，便于调试
        })

    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        return jsonify({
            "type": "error",
            "text": f"服务器内部错误: {str(e)}",
            "tts_audio": "",
            "session_id": session_id if 'session_id' in locals() else '',
            "next_action": "continue"
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "AI模拟面试官云端服务运行中"})


@app.route('/api/test/asr', methods=['POST'])
def test_asr():
    """测试 ASR 功能"""
    try:
        data = request.get_json()
        audio_base64 = data.get('audio', '')
        audio_format = data.get('format', 'wav')

        if not audio_base64:
            return jsonify({"error": "音频数据为空"}), 400

        result = asr_audio_to_text(audio_base64, audio_format, "zh")
        return jsonify({"text": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/tts', methods=['POST'])
def test_tts():
    """测试 TTS 功能"""
    try:
        data = request.get_json()
        text = data.get('text', '')

        if not text:
            return jsonify({"error": "文字内容为空"}), 400

        result = tts_text_to_audio(text, style="专业、友好")
        return jsonify({"audio": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("启动 AI模拟面试官 云端服务...")
    app.run(host='0.0.0.0', port=5000, debug=False)
