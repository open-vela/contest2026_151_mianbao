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
from question_bank import warmup as warmup_question_bank

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
session_manager = SessionManager()

# ---- 启动时预热题库（见 cloud/question_bank.py）----
# Flask dev server 默认多线程，第一次请求进来再加载会有并发竞争；预热一次之后就只读缓存。
# ⚠️ 演示当天**必须看这几行日志**：题库没加载成功不会报错，只会静默退化成自由提问
#    （面试照样能跑，但选题不再走题库）—— 缺了数据要当场发现，别到台上才发现。
_bank = warmup_question_bank()
if _bank["loaded"]:
    logger.info(f"[题库] 就绪：{_bank['records']} 道题，岗位：{'、'.join(_bank['roles'])}")
else:
    logger.warning(f"[题库] 未加载到题目（目录 {_bank['dir']}）—— 面试将退化为自由提问，"
                   f"不注入参考题。检查 question_bank/data/ 是否随代码一起拷过去了。")


@app.route('/api/interview', methods=['POST'])
def handle_interview():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"type": "error", "text": "请求体不能为空", "tts_audio": "", "session_id": "", "next_action": "finish"}), 400

        session_id = data.get('session_id', '')
        audio_base64 = data.get('audio', '')
        audio_format = data.get('audio_format', 'wav')
        # 默认岗位与端侧 Kconfig 的默认值保持一致（板子每次都显式带 role，
        # 这里只影响手工 curl 测试）。改成题库里有的岗位，手工测时也能拿到参考题。
        role = data.get('role', 'AI 应用开发')
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
                logger.warning(f"[session={session_id}] ASR 识别失败或未识别到语音")

            # ---- 空识别短路 ----
            # 用户没说话（整轮静音）或 ASR 失败时，绝不能让 LLM 自由发挥：
            # 实测过一次静音轮，LLM 生成了超长回复，TTS 音频 base64 让整个响应体
            # 冲破端侧的 8MB 缓冲上限（`CLOUD_RESP_MAX`），端侧直接报错中止。
            # 这里固定回一句短的，响应大小可控，且对用户是合理的交互。
            if not user_text.strip():
                reply = "抱歉，我没听清，请再说一次。"
                logger.info(f"[session={session_id}] 空识别 -> 短路回复：{reply}")
                session.add_ai_message(reply)
                return jsonify({
                    "type": "question",
                    "text": reply,
                    "tts_audio": tts_text_to_audio(
                        reply, style="专业、友好、有洞察力的面试官"
                    ),
                    "session_id": session_id,
                    "next_action": "continue",
                    "user_text": ""
                })

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


# ============================================================
# 对话展示页（只读）
#
# 给评委和组员看面试对话内容用的 —— 比在串口里看方便得多。
#
# ⚠️ 这一节是**纯增量**：没有改动 handle_interview 的任何一行，板子走的那条
#    链路完全不变。页面只**读**不写，既不创建也不污染会话，所以不存在"网页
#    把板子那场面试搅乱"的风险；也刻意不做网页发消息的输入框 —— 那会让网页
#    也去调 /api/interview、多出一个 session。
#
# 页面文件是 cloud/static/index.html，由 Flask 自带的静态目录直接提供（和
# app.py 同级的 static/），不引入任何新依赖，也不依赖任何外部 CDN ——
# 演示现场是手机热点，外网不一定通。
# ============================================================

@app.route('/', methods=['GET'])
def index():
    """对话展示页。"""
    return app.send_static_file('index.html')


@app.route('/api/history', methods=['GET'])
def history():
    """只读快照：不带参数返回最近更新的那场会话；带 session_id 则返回指定会话。

    没有任何会话时返回 waiting=True，前端据此显示"等待面试开始"。
    """
    snap = session_manager.snapshot(request.args.get('session_id'))
    if snap is None:
        return jsonify({"waiting": True, "session_id": "", "messages": []})
    return jsonify(snap)


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
