"""
AI模拟面试官 — 云端 Flask 服务
"""
from flask import Flask, request, jsonify, send_file
import io
import os
import threading
import uuid
import logging
from llm_service import llm_interview, score_interview
from asr_service import asr_audio_to_text
from tts_service import tts_text_to_audio
from session_manager import SessionManager
from question_bank import warmup as warmup_question_bank
import report_export
import session_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
session_manager = SessionManager()


def _snapshot(session_id=None):
    """取一份会话快照：**内存优先，磁盘兜底**；都没有则返回 None。

    磁盘兜底是为了让重启不再等于"上一场没了"：会话在每轮结束时落盘
    （见 cloud/session_store.py），重启后网页仍能看到上一场、也仍能导出报告。
    只读，不创建会话 —— 展示层调用它不会产生任何副作用。
    """
    snap = session_manager.snapshot(session_id)
    if snap is not None:
        return snap
    return session_store.load(session_id) if session_id else session_store.load_latest()


def _start_scoring(session_id):
    """报告轮之后，**在后台线程里**跑结构化评分（P2）。

    三条纪律，每条都有代价换来的理由：

    * **只"发起"不"等待"** —— 评分是额外一次 LLM 调用（实测十几秒），而板子正
      阻塞等这个回包。放在请求线程里就是把那十几秒加到板子头上，违反"云端处理
      不能让端侧多等"这条底线。所以线程在这里起、响应紧接着返回。
    * **绝不改端侧响应体** —— 评分只进会话快照（网页 / 导出 / 落盘），
      `handle_interview` 里那段 jsonify 一个字段都不动。板子只解析 5 个字段、
      缓冲 8MB，多塞东西没有半点好处。
    * **失败只记日志** —— 评分是锦上添花，不能影响一场已经完成的面试。
      整段包在 try 里，异常一律吞掉记 warning。

    返回刚起的那个线程（调用方直接丢掉），**为的是让测试能 join 它** ——
    否则"评分到底有没有写进会话"只能靠 sleep 去猜，那是最不可靠的一种测试。
    """
    def _work():
        try:
            session = session_manager.get_session(session_id)
            if session is None:
                return                      # 会话已被清理，那就算了
            score = score_interview(session.role, list(session.history))
            if not score:
                logger.warning(f"[评分] session={session_id} 未拿到可用评分（跳过）")
                return
            session.score = score
            # 落一份带评分的存档。session_store 的原子写**本来就是为"后台线程与
            # 主线程先后写同一个文件"设计的**（见它的 docstring 第二条）。
            session_store.save(session_manager.snapshot(session_id))
            logger.info(f"[评分] session={session_id} 完成：总分 {score.get('total')}，"
                        f"{len(score.get('dimensions', []))} 个维度")
        except Exception as error:          # noqa: BLE001 —— 见上面第三条
            logger.warning(f"[评分] session={session_id} 评分线程出错"
                           f"（不影响这场面试）：{error}")

    thread = threading.Thread(target=_work, name=f"score-{session_id[:8]}", daemon=True)
    thread.start()
    return thread

# ---- 启动时校验 MIMO_API_KEY：空 key 直接拒绝启动 ----
# 为什么要在**启动时**拦：asr/llm/tts 三个 service 都是在模块顶层 `os.environ.get("MIMO_API_KEY", "")`，
# 进程一起来就绑定死了 —— 之后再也补不上，运行期没有任何补救机会。
# 而空 key 的症状是最难查的那一种：**HTTP 200，但 tts_audio 是空串**，端侧只会报
# 「云端多半缺 API key」，看起来像网络问题。演示时录到一半才发现没声音，代价太大。
# 宁可现在就退出。（提示词只能劝、拦不住的要在代码里拦 —— 同上。）
_KEY = os.environ.get("MIMO_API_KEY", "")
if not _KEY:
    logger.error("=" * 74)
    logger.error("⛔ MIMO_API_KEY 未设置或为空串，拒绝启动。")
    logger.error("   空 key 不走报错路径：接口仍返回 HTTP 200，只是 tts_audio 为空 ——")
    logger.error("   录到一半才会发现板子没声音，所以在这里停下来。")
    logger.error("")
    logger.error("   key 只放环境变量，别写进代码、别提交。任选一种设法：")
    logger.error("")
    logger.error("   Windows (PowerShell) — 推荐从「仓库外」的文件读，key 不进命令行历史：")
    logger.error(r'     Set-Content "$HOME\.mimo_key" "你的key" -NoNewline        # 一次性')
    logger.error(r'     $env:MIMO_API_KEY = (Get-Content "$HOME\.mimo_key" -Raw).Trim()')
    logger.error("")
    logger.error("   Linux / macOS：")
    logger.error('     export MIMO_API_KEY="$(cat ~/.mimo_key)"')
    logger.error("")
    logger.error("   ⚠️ 那个 key 文件必须放在「仓库外」（如 ~/.mimo_key）——")
    logger.error("      放仓库里，迟早会被一次 git add -A 带进历史，之后只能靠轮换收场。")
    logger.error("   启动成功后会打印「[密钥] MIMO_API_KEY 已加载（长度 N）」：")
    logger.error("      核对那个长度对不对即可，不要把 key 本身打印出来。")
    logger.error("=" * 74)
    raise SystemExit(1)
logger.info("[密钥] MIMO_API_KEY 已加载（长度 %d）" % len(_KEY))

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
        is_new = session_manager.get_session(session_id) is None
        session = session_manager.get_or_create_session(session_id, role)

        # 只在"开新会话"这一条路径上清理过期会话：正在进行的会话绝不会被扫到
        # —— 走这条路径时它根本不在内存里。清理是为了让长期挂着的进程内存不
        # 无界增长（会话现在还会落盘，磁盘那份不受影响）。
        if is_new:
            session_manager.clean_expired_sessions()

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
                # ⚠️ 这一句**刻意不写进历史**（原先是 add_ai_message）。
                # 它没有对应的 user 消息，塞进去会让历史变成奇数条，而报告判据是
                # `len(history) - 1 >= 20`（llm_service.HISTORY_FINISH_THRESHOLD）
                # —— 一次静音轮就把报告从第 11 次 K1 推迟到第 12 次，而 README
                # 和演示脚本都写死"第 11 次出报告"。静音不是一段对话，不该进记录。
                # 语音照常播（TTS 在下）、响应照常返回，只是不留痕。
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

        # 报告轮 = 这一场到此结束。此前 `is_finished` **恒为 False**：finish() 写了
        # 却从来没有调用者，于是"结束了没有"这个状态在云端根本不存在，网页也就
        # 无从判断该不该渲染报告卡片。判据与响应体里的 type 完全一致，不另立标准。
        if next_action != "continue":
            session.finish()
            logger.info(f"[session={session_id}] 面试结束（{session.question_count} 轮），"
                        f"本轮为报告轮")

        # TTS 合成
        logger.info(f"[session={session_id}] 开始 TTS...")
        tts_audio_base64 = tts_text_to_audio(
            ai_text,
            style="专业、友好、有洞察力的面试官"
        )

        # ---- 落盘 ----
        # 位置是刻意的：**TTS 之后、return 之前**。
        #   * 放前面就把 ASR+LLM+TTS 之后又叠一次磁盘 I/O 到响应延迟上（板子正阻塞
        #     等这个回包）；
        #   * save() 自己吞掉所有异常（见 cloud/session_store.py），落盘失败只是
        #     少一份存档，绝不能把一次成功的面试变成 500。
        session_store.save(_snapshot(session_id))

        # 报告轮：起一个后台线程去评分。**在 return 之前"发起"，但不在这里等** ——
        # 线程已经跑起来，而响应马上返回，板子拿到的延迟与没有评分时完全一样。
        if next_action != "continue":
            _start_scoring(session_id)

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

    内存里没有时回落到磁盘（重启后仍能看到上一场）。都没有才返回 waiting=True，
    前端据此显示"等待面试开始"。
    """
    snap = _snapshot(request.args.get('session_id'))
    if snap is None:
        return jsonify({"waiting": True, "session_id": "", "messages": []})
    return jsonify(snap)


@app.route('/api/sessions', methods=['GET'])
def sessions():
    """历史场次列表（只读）。

    公共设备上"我刚面完的那场"就是从这里认出来的 —— 网页的主路径是 `/`（直接显示
    最近一场），这里是"看更早的"那条路。

    `?limit=` 默认 20、**上限 100**：它是给人看的列表，不是导出接口。
    """
    try:
        limit = int(request.args.get('limit', 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 100))
    return jsonify({"sessions": session_store.list_summaries(limit), "limit": limit})


@app.route('/history', methods=['GET'])
def history_page():
    """历史列表页。

    与展示页**共用同一个 HTML 文件**（前端按 `location.pathname` 分支，见
    static/index.html 的"视图模式"一段）—— 列表与详情九成的样式和工具函数都一样，
    拆成两个文件迟早会出现两边不一致。
    """
    return app.send_static_file('index.html')


@app.route('/api/export/<session_id>', methods=['GET'])
def export_session(session_id):
    """把一场面试导出成可下载的文件：`?format=md`（默认）或 `?format=json`。

    纯增量：只**读**会话，不创建、不修改，因此对板子那条链路没有任何影响。
    内存优先、磁盘兜底 —— 重启之后照样能把上一场的报告导出来。
    """
    snap = _snapshot(session_id)
    if snap is None:
        return jsonify({"error": "找不到这场面试（会话不存在或已过期）"}), 404

    rendered = report_export.export(snap, request.args.get('format', 'md'))
    if rendered is None:
        return jsonify({"error": "不支持的格式，可选 md / json"}), 400

    body, mimetype, filename = rendered
    # BytesIO 直接送，不落临时文件：报告只有几十 KB，且没有"下载完要清理"的问题。
    # 文件名是纯 ASCII（见 report_export.filename），所以不涉及 RFC 5987 编码。
    payload = io.BytesIO(body.encode('utf-8'))
    payload.seek(0)
    return send_file(payload, mimetype=mimetype, as_attachment=True,
                     download_name=filename)


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
