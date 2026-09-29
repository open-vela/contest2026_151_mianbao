#!/usr/bin/env python3
"""PC 端面试排练 —— 不开板子，把云端整条链路跑满 11 轮并逐轮体检。

用途：上板之前先在 PC 上把端云链路（ASR → LLM → TTS）完整走一遍，
把"报告轮空返回""参考块泄漏""TTS 体积越界"这类问题在电脑上抓出来。

跑法（**需要 MIMO_API_KEY，会真打 LLM / ASR / TTS，要花钱**）：

    export MIMO_API_KEY="$(sed -n '42p' ~/test-project/README.md | tr -d '\\r\\n')"
    cd cloud && python3 app.py &          # 另开一个终端，或后台起
    python3 cloud/rehearsal.py

    # 常用可选参数
    python3 cloud/rehearsal.py --role "AI/ML Engineer"   # 换岗位（走英文题库）
    python3 cloud/rehearsal.py --rounds 3                # 只跑 3 轮（不校验报告轮）
    python3 cloud/rehearsal.py --say-finish --rounds 3   # 第 3 轮说"结束吧"，验证提前收尾
    python3 cloud/rehearsal.py --no-tts                  # 静音自检：验证空识别短路与历史奇偶

⚠️ 三条踩过的坑，脚本已经替你处理，改的时候别踩回去：
  1. **每轮必须带 `state="recording_finished"`**（`cloud/app.py:42`）。漏掉的话
     ASR 会被整段静默跳过：没有候选人回答进历史，`llm_interview()` 永远走不到
     结束判据（不出报告），模型还会在无输入下长篇独白（实测可达 1345 字 / 14.56MB）。
  2. **候选人语音是现合成的**，不是拿一段音频反复打。同一个音频重复 11 次是病态输入：
     历史里全是同一句话，题库检索匹配不到任何东西，等于没测题库这条路。
     （`cloud/test_tts_output.wav` 在 .gitignore 里，也不能依赖它。）
  3. **报告轮出现在第 11 次调用**，不是第 10 次：端侧只发 `recording_finished`，
     第一次调用时历史里只有候选人这句话（`start_interview` 在真实链路上不可达），
     所以第 N 次调用时 `len(history)-1 == 2N-2`，凑满 `HISTORY_FINISH_THRESHOLD=20`
     需要 N=11。轮数对不上先回来核对这一段。
     （候选人中途说"结束吧"是另一条路径，那一轮就出报告，见 `finish_guard`。）

判据的两条纪律（2026-09 补强，都来自"差点被骗过去"的经历）：
  * **只查"不该出现"是不够的**。原先只查泄漏串，于是全链路失败时依然是绿的：
    模型调不通 → 各处 return 兜底串 → HTTP 200、结构完整、没有泄漏串，全过。
    现在 `FALLBACK_STRINGS` 专门查"这一步是不是失败得体面"。
  * **判据要跟着"判据本身"变**。报告轮由结束判据决定，所以"末轮必是报告"这种
    断言只在 `--rounds 11` 或 `--say-finish` 时成立，`--rounds 3` 下它是假失败。
"""
import argparse
import base64
import json
import struct
import sys
import time
import uuid

import requests

from finish_guard import match_reason
from reply_guard import FALLBACK_QUESTION

# ---------------- 判据阈值（改动要同步更新台账 §11.21） ----------------

# 端侧 8MiB 缓冲（CLOUD_RESP_MAX）的一半。TTS 音频 base64 会再胀 1/3，
# 所以这里量的是**解码后**的字节数。
MAX_TTS_BYTES = 4 * 1024 * 1024

# 单条问句上限：提示词要求 120 字以内，留出模型的越界余量。
MAX_QUESTION_CHARS = 150

# 报告上限：提示词要求 200 字以内，余量同上。
MAX_REPORT_CHARS = 250

# 一轮面试成功的标志：11 次调用后历史里正好 11 问 + 11 答。
# 轮数断言不写死条数，而是 `2 × 实际跑的轮数` —— 报告轮由结束判据决定，
# `--say-finish` 时它会提前到第 3 轮，写死 22 就是给自己下绊子。
EXPECTED_ROUNDS = 11

# 静音 WAV：44 字节标准 PCM 头 + 0 字节数据（16000Hz / 单声道 / 16bit）。
# 用 struct 拼而不是写字节串字面量：手抄那个字面量时我多塞了一个 0x00（45 字节），
# 后面每个字段都错位，头其实是坏的 —— 而它**照样"通过"**（坏文件同样让 ASR 返回
# 空），属于"因为错误的原因而绿"。拼出来就不可能错位。
SILENT_WAV = (b"RIFF" + struct.pack("<I", 36) + b"WAVE"
              + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
              + b"data" + struct.pack("<I", 0))
assert len(SILENT_WAV) == 44, "标准 WAV 头必须是 44 字节"
SILENT_WAV_B64 = base64.b64encode(SILENT_WAV).decode()

# 空识别短路回复的字数上限：它必须是**短**的 —— 静音轮曾经诱发模型长篇输出，
# TTS 音频 base64 撑破端侧 8MB 缓冲（CLOUD_RESP_MAX），端侧直接报错中止。
# 所以这里不只查"有没有回复"，还查"够不够短"。
MAX_SHORT_CIRCUIT_CHARS = 30

# 参考块/提示词的痕迹绝不能出现在模型输出里 —— 会被 TTS 逐字念给候选人听。
LEAK_STRINGS = ("题库", "参考题", "参考资料", "使用要求", "面试纪律", "硬性要求",
                "**", "##", "理由：", "判断：", "新问题：", "问题设计说明", "下一步：")

# 兜底文案：**这些一旦出现，说明那一步的模型调用失败了**。
#
# 为什么要单列一类：原先只查"不该出现的痕迹"，于是全链路失败时**依然是绿的**
# —— 模型调不通 → 各处 return 兜底串 → HTTP 200、结构完整、没有泄漏串，
# 所有既有判据全部通过，脚本打印"✅ 排练通过"。这是最坏的一种假绿：
# 它会让"上板前先排练一遍"这道防线形同虚设。
FALLBACK_STRINGS = (
    "生成报告失败",                  # llm_service.generate_feedback 的兜底
    "抱歉，加载面试配置失败。",        # skill 文件加载失败
    "抱歉，生成问题失败，请重试。",    # call_llm 返回空
    "抱歉，我没听清，请再说一次。",    # app.py 空识别短路（静音轮，正常流程里不该出现）
    FALLBACK_QUESTION,               # reply_guard：整段都是元叙述时顶上的问句
)

# 语音请求结束面试的短语（--say-finish 用）。走一圈 TTS→ASR 之后还能不能命中
# finish_guard 的白名单，只有真跑一次才知道 —— ASR 可能把"结束吧"转写成别的。
FINISH_PHRASE = "结束吧"

# 候选人回答，逐轮轮换。都是"像样的中文回答"：有具体名词、数字和取舍，
# 这样题库检索才有东西可匹配（这也是不能用同一段音频反复打的原因）。
CANDIDATE_ANSWERS = [
    "我叫李昊，本科学计算机，毕业后做了三年后端开发，最近一年半在一家电商公司做 AI 应用，"
    "主要负责大模型智能客服和知识库问答这两个方向。",
    "我们做的是一个基于 RAG 的客服知识库，文档来源是商品手册和售后政策，"
    "每天大概两千次提问，检索用的是向量数据库加关键词的混合召回。",
    "切分策略上我们试过固定长度和按标题层级切两种，最后选了按标题切，"
    "因为这样每个文本块语义比较完整，召回时的噪声少一些。",
    "重排用的是开源的 bge-reranker 模型，在我们自己建的评测集上，"
    "把前三条的命中率从百分之七十二提到了八十五左右。",
    "上线之后延迟是个大问题，首字延迟最高到过八百毫秒，因为每次都要跑一遍重排，"
    "后来我们把候选从五十条降到二十条。",
    "还加了语义缓存，很多问题问法不同但意思一样，命中缓存就直接返回，"
    "延迟降到了两百毫秒以内。",
    "缓存最难的是失效，文档更新之后缓存还是旧的，我们现在把文档版本号做进缓存的键里，"
    "文档一更新就换版本，旧的自然就失效了。",
    "评测这块我们建了三百条金标集，覆盖商品咨询、退款、物流这几类，"
    "每次改动都要跑一遍，主要看有没有回退。",
    "团队一共五个人，我负责检索和评测这两块，另外有同学做前端和部署运维，"
    "我们每周同步一次进度。",
    "如果重新做一遍，我会先把评测集和监控建起来再动手写代码，"
    "现在这套是边做边补的，出问题排查起来比较被动。",
    "好的，这个岗位我大概了解了，暂时没有什么想问的。",
]


def _parse(response) -> tuple:
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"_raw": response.text[:200]}


def post_json(url: str, payload: dict, timeout: int = 180) -> tuple:
    """POST 一个 JSON，返回 (status_code, body_dict)。网络异常也返回 (0, {...})。"""
    try:
        return _parse(requests.post(url, json=payload, timeout=timeout))
    except Exception as error:
        return 0, {"_error": str(error)}


def get_json(url: str, timeout: int = 30) -> tuple:
    """GET 一个 JSON。`/api/health` 与 `/api/history` 都只接受 GET，别用 POST 打它们。"""
    try:
        return _parse(requests.get(url, timeout=timeout))
    except Exception as error:
        return 0, {"_error": str(error)}


def synthesize_answer(base_url: str, text: str) -> str:
    """把候选人的回答文字合成为音频 base64 —— 模拟"候选人说了这句话"。

    走的是和生产同一条 TTS 通路（`/api/test/tts`），所以它同时也是 TTS 的健康检查。
    """
    status, body = post_json(f"{base_url}/api/test/tts", {"text": text})
    if status != 200 or not body.get("audio"):
        return ""
    return body["audio"]


def run_round(base_url: str, session_id: str, role: str, audio_base64: str) -> dict:
    """打一轮真实请求。`state` 固定为 recording_finished —— 见模块 docstring 的坑 1。"""
    status, body = post_json(f"{base_url}/api/interview", {
        "session_id": session_id,
        "role": role,
        "state": "recording_finished",        # ← 少一个字，ASR 就被整段跳过
        "audio": audio_base64,
        "audio_format": "wav",
    })
    return {"status": status, "body": body}


def self_check_silence(base_url: str, role: str) -> int:
    """静音自检：连打 3 轮静音，验证空识别短路 **与历史奇偶性**。

    这是 `--no-tts` 真正的用途。它原先只是"省一次 TTS 调用"，可第 1 轮就必然
    失败退出（静音 → ASR 空 → 短路回复 → 脚本自己判"ASR 结果为空"然后 break），
    也就是说这个开关从来没有成功跑完过一轮。

    核心判据是**历史条数**：静音轮没有对应的候选人发言，因此不进历史 ——
    3 轮之后历史必须仍是 0 条。在修复之前，那句"抱歉，我没听清"会被当成一条
    assistant 消息存进去，历史变奇数，报告从第 11 次 K1 被推迟到第 12 次
    （判据是 `len(history) - 1 >= 20`）。
    """
    session_id = str(uuid.uuid4())
    failures = []
    print(f"静音自检：{base_url}  岗位={role}  session={session_id}")
    print("-" * 78)

    def fail(message: str) -> None:
        failures.append(message)
        print(f"  ❌ {message}")

    for number in range(1, 4):
        started = time.time()
        result = run_round(base_url, session_id, role, SILENT_WAV_B64)
        payload = result["body"] or {}
        text = payload.get("text", "") or ""
        user_text = payload.get("user_text", "") or ""
        audio_base64 = payload.get("tts_audio") or ""
        print(f"第 {number} 轮 [{result['status']}] type={payload.get('type', ''):8s} "
              f"回复={len(text):2d}字 ASR={len(user_text)}字 "
              f"TTS={len(audio_base64) * 3 / 4 / 1024:6.1f}KB  {time.time() - started:5.1f}s")
        print(f"        {text[:70]}")

        if result["status"] != 200:
            fail(f"第 {number} 轮 HTTP {result['status']}：{str(payload)[:200]}")
            continue
        if user_text:
            fail(f"第 {number} 轮本该识别为空，却识别出 {user_text[:40]!r}")
        if not text.strip():
            fail(f"第 {number} 轮短路回复为空 —— 候选人听到的是一片静音")
        if len(text) > MAX_SHORT_CIRCUIT_CHARS:
            fail(f"第 {number} 轮短路回复 {len(text)} 字 > {MAX_SHORT_CIRCUIT_CHARS} 字"
                 f" —— 静音轮的长回复会撑破端侧 8MB 缓冲（这正是短路的由来）")
        if not audio_base64:
            fail(f"第 {number} 轮 tts_audio 为空（端侧会直接报错中止）")
        if payload.get("next_action") != "continue":
            fail(f"第 {number} 轮 next_action={payload.get('next_action')!r}，应为 continue")

    status, snapshot = get_json(f"{base_url}/api/history?session_id={session_id}")
    if status != 200:
        fail(f"/api/history 返回 HTTP {status}")
    else:
        messages = snapshot.get("messages", [])
        print(f"历史：{len(messages)} 条（期望 0 条 —— 静音不是一段对话）")
        if messages:
            fail(f"静音轮给历史留下了 {len(messages)} 条消息"
                 f"（第一条是 {messages[0].get('role')}）—— 历史奇偶被打乱，"
                 f"报告会从第 11 次 K1 推迟到第 12 次")
        if snapshot.get("question_count"):
            fail(f"question_count={snapshot.get('question_count')}，静音不该计入轮次")

    print()
    if failures:
        print(f"❌ 静音自检失败，{len(failures)} 项不达标：")
        for message in failures:
            print(f"   · {message}")
        return 1
    print("✅ 静音自检通过：3 轮静音都是短回复、都有声音、且没有污染历史。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PC 端面试排练（11 轮端云链路体检）")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--role", default="AI 应用开发", help="面试岗位，默认演示岗位")
    parser.add_argument("--rounds", type=int, default=EXPECTED_ROUNDS,
                        help=f"跑几轮（默认 {EXPECTED_ROUNDS}；小于 {EXPECTED_ROUNDS} 时"
                             f"不校验报告轮 —— 报告是按轮次阈值触发的，还没到）")
    parser.add_argument("--no-tts", action="store_true",
                        help="不合成候选人语音，改跑静音自检：连打 3 轮静音，"
                             "验证空识别短路与历史奇偶性")
    parser.add_argument("--say-finish", action="store_true",
                        help=f"把最后一轮的回答换成「{FINISH_PHRASE}」，验证候选人"
                             f"用语音请求结束面试那条路径（要过一遍 TTS→ASR，"
                             f"只有真跑才知道转写结果还能不能命中白名单）")
    args = parser.parse_args()

    # 0 轮什么都证明不了，而且它会让所有判据"空过"、最后在 max() 上崩栈
    # （`max()` 对空序列抛 ValueError）—— 在入口拦掉，别留一个崩栈的入口。
    if args.rounds < 1:
        print(f"❌ --rounds 必须是正数（收到 {args.rounds}）。")
        return 1

    base_url = args.base_url.rstrip("/")
    session_id = str(uuid.uuid4())
    failures = []
    rounds = []

    def fail(message: str) -> None:
        failures.append(message)
        print(f"  ❌ {message}")

    # 健康检查排在横幅之前：静音自检走的是另一条路（只 3 轮），先打印
    # "轮数=11" 只会让人以为脚本跑歪了。
    status, body = get_json(f"{base_url}/api/health")
    if status != 200:
        print(f"❌ 健康检查失败（HTTP {status}）—— 云端起了吗？{base_url}")
        return 1

    if args.no_tts:
        print(f"✅ 健康检查 HTTP {status}\n")
        return self_check_silence(base_url, args.role)

    print(f"排练目标：{base_url}  岗位={args.role}  轮数={args.rounds}  session={session_id}")
    print("-" * 78)
    print(f"✅ 健康检查 HTTP {status}\n")

    # 报告轮落在哪一轮，由**结束判据**决定，所以不能一律假定是末轮：
    #   * 轮次阈值（HISTORY_FINISH_THRESHOLD=20）→ 第 11 次调用；
    #   * 或候选人说「结束吧」（finish_guard）→ 就在说出口的那一轮。
    # 于是 `--rounds 3` 天然够不到报告轮，末轮断言 report 就是**假失败**。
    report_round = 0
    if args.rounds >= EXPECTED_ROUNDS:
        report_round = EXPECTED_ROUNDS       # 轮次阈值先到，说「结束吧」也轮不上
    elif args.say_finish:
        report_round = args.rounds

    for index in range(args.rounds):
        number = index + 1
        # 最后一轮换成「结束吧」：这句要真过一遍 TTS→ASR 才有意义 ——
        # 白名单匹配的是**转写后**的文本，直接喂文字等于跳过了要测的那一段。
        if args.say_finish and number == args.rounds:
            answer = FINISH_PHRASE
        else:
            answer = CANDIDATE_ANSWERS[index % len(CANDIDATE_ANSWERS)]
        started = time.time()

        audio = synthesize_answer(base_url, answer)
        if not audio:
            fail(f"第 {number} 轮：候选人语音合成失败（TTS 返回空）"
                 f" —— 优先检查 MIMO_API_KEY 是否还在进程内存里")
            break

        result = run_round(base_url, session_id, args.role, audio)
        elapsed = time.time() - started
        payload = result["body"] or {}
        text = payload.get("text", "") or ""
        audio_bytes = len(base64.b64decode(payload.get("tts_audio") or "")) if payload.get("tts_audio") else 0
        user_text = payload.get("user_text", "") or ""
        kind = payload.get("type", "")
        next_action = payload.get("next_action", "")

        rounds.append({
            "round": number, "status": result["status"], "type": kind,
            "chars": len(text), "audio": audio_bytes, "asr": len(user_text),
            "elapsed": elapsed, "text": text,
        })
        print(f"第 {number:2d} 轮 [{result['status']}] {kind:8s} next={next_action:8s} "
              f"问句={len(text):3d}字  ASR={len(user_text):3d}字  "
              f"TTS={audio_bytes / 1024:7.1f}KB  {elapsed:5.1f}s")
        print(f"        {text[:70]}")

        if result["status"] != 200:
            fail(f"第 {number} 轮 HTTP {result['status']}：{str(payload)[:200]}")
            break
        if payload.get("session_id") != session_id:
            # 端侧靠 session_id 串联多轮，每一轮都带回来。云端若自作主张换一个 id，
            # 板子那边就是每轮都在跟一场新面试说话 —— HTTP 200、结构完整，只在
            # 界面上表现为"面试永远从头开始"，极难查。
            fail(f"第 {number} 轮返回的 session_id={payload.get('session_id')!r} "
                 f"与请求的 {session_id!r} 不一致")
        if not user_text.strip():
            fail(f"第 {number} 轮 ASR 结果为空 —— 这一轮会走空识别短路，"
                 f"历史对不齐，后面的判据都不作数")
            break

        # 「结束吧」那一轮：转写结果与判据都打出来。这一轮失败时要能一眼分辨
        # 是 ASR 把话转坏了、还是白名单漏了说法 —— 两者的修法完全不同。
        finish_matched = True
        if args.say_finish and number == args.rounds:
            reason = match_reason(user_text)
            finish_matched = bool(reason)
            print(f"        说「{FINISH_PHRASE}」→ ASR 转写 {user_text!r} → 结束判据 "
                  f"{'命中 ' + repr(reason) if reason else '未命中'}")
            if not finish_matched:
                fail(f"说「{FINISH_PHRASE}」但没被判定为请求结束（转写 {user_text!r}）"
                     f" —— 要么 ASR 变形太多，要么白名单漏了这种说法")

        if audio_bytes > MAX_TTS_BYTES:
            fail(f"第 {number} 轮 TTS 音频 {audio_bytes / 1024 / 1024:.2f} MiB "
                 f"超过 {MAX_TTS_BYTES / 1024 / 1024:.0f} MiB")
        hits = [leak for leak in LEAK_STRINGS if leak in text]
        if hits:
            fail(f"第 {number} 轮输出里出现泄漏串 {hits}（会被逐字念出来）")
        fallbacks = [s for s in FALLBACK_STRINGS if s in text]
        if fallbacks:
            # 全链路失败的表现：模型调不通 → 各处 return 兜底串 → HTTP 200、
            # 结构完整、没有泄漏串，于是所有旧判据都通过。这是最坏的一种假绿。
            fail(f"第 {number} 轮输出是兜底文案 {fallbacks} —— 这一步的模型调用失败了，"
                 f"但接口看起来一切正常（假绿的来源）")

        expected_kind = "report" if number == report_round else "question"
        if kind != expected_kind:
            if expected_kind == "report" and not finish_matched:
                pass   # 根因上面已报（转写没命中白名单），这里再报一次只是噪音
            else:
                fail(f"第 {number} 轮 type={kind}，应为 {expected_kind}"
                     f"（报告没接上，或轮数不对）")
        elif expected_kind == "question":
            if len(text) > MAX_QUESTION_CHARS:
                fail(f"第 {number} 轮问句 {len(text)} 字，超过 {MAX_QUESTION_CHARS} 字（话痨复发？）")
        elif len(text) > MAX_REPORT_CHARS:
            fail(f"报告 {len(text)} 字，超过 {MAX_REPORT_CHARS} 字")

        # next_action 是端侧唯一的协议开关：`strcmp(next_action,"continue") != 0`
        # 就清空会话（main.c:207）。值不对，下一场面试会串到上一场的 session 上。
        expected_action = "finish" if number == report_round else "continue"
        if next_action != expected_action:
            fail(f"第 {number} 轮 next_action={next_action!r}，应为 {expected_action!r}")

    print("-" * 78)

    # 历史体检：条数必须正好是"轮数 × 2"（一问一答），且无超长面试官消息
    expect_messages = 2 * args.rounds
    status, snapshot = get_json(f"{base_url}/api/history?session_id={session_id}")
    if status != 200:
        fail(f"/api/history 返回 HTTP {status}")
    else:
        messages = snapshot.get("messages", [])
        print(f"历史：{len(messages)} 条（期望 {expect_messages} 条）")
        if len(messages) != expect_messages:
            fail(f"历史 {len(messages)} 条 ≠ {expect_messages} 条 —— "
                 f"说明有轮次没走完整（空识别短路？）")
        answers = [m for m in messages if m.get("role") == "assistant"]
        if snapshot.get("question_count") != len(answers):
            fail(f"question_count={snapshot.get('question_count')} 与面试官消息数 "
                 f"{len(answers)} 不一致 —— 网页的轮次显示会不准")
        longest = max((len(m.get("content", "")) for m in answers), default=0)
        if longest > MAX_REPORT_CHARS:
            fail(f"历史里最长的面试官消息 {longest} 字 > {MAX_REPORT_CHARS} 字")

        # 结束状态：`is_finished` 此前恒为 False（finish() 零调用者），网页因此
        # 永远不知道该渲染报告卡片。它必须与"有没有到报告轮"严格对齐。
        if report_round and not snapshot.get("is_finished"):
            fail("报告轮之后 is_finished 仍为 false —— 网页不会渲染报告卡片，"
                 "导出文件也会一直显示「进行中」")
        if not report_round and snapshot.get("is_finished"):
            fail(f"只跑了 {args.rounds} 轮就 is_finished —— 结束判据被提前触发了"
                 f"（阈值是 {EXPECTED_ROUNDS} 轮，或候选人说了结束语）")

    # 导出接口：报告轮之后必须真的下载得到。单测只覆盖了渲染函数，没覆盖路由，
    # 所以这里补一次真 HTTP —— 导出是 P1 新开的对外能力，不验等于没测。
    if report_round:
        status, body = get_json(f"{base_url}/api/export/{session_id}?format=md")
        raw = (body or {}).get("_raw", "")
        if status != 200:
            fail(f"导出 Markdown 返回 HTTP {status}：{str(body)[:200]}")
        elif "面试报告" not in raw:
            fail(f"导出的 Markdown 不像报告，开头是 {raw[:60]!r}")
        else:
            print(f"导出 Markdown：HTTP {status}，开头 {raw[:38]!r}…")

        status, body = get_json(f"{base_url}/api/export/{session_id}?format=json")
        if status != 200:
            fail(f"导出 JSON 返回 HTTP {status}：{str(body)[:200]}")
        elif (body or {}).get("session_id") != session_id:
            fail(f"导出 JSON 的 session_id={(body or {}).get('session_id')!r} 与请求不一致")
        elif not body.get("is_finished"):
            fail("导出 JSON 里 is_finished 为 false —— 报告已经出来了，状态却没跟上")
        else:
            print(f"导出 JSON：HTTP {status}，含 {len(body.get('messages') or [])} 条历史")

    print()
    if failures:
        print(f"❌ 排练失败，{len(failures)} 项不达标：")
        for message in failures:
            print(f"   · {message}")
        return 1
    if not rounds:
        print("❌ 一轮都没跑成 —— 判据空过不算通过。")
        return 1

    total_audio = sum(r["audio"] for r in rounds)
    ending = (f"第 {report_round} 轮为报告。" if report_round
              else f"{len(rounds)} 轮都是问句（未到报告轮）。")
    print(f"✅ 排练通过：{len(rounds)} 轮全部正常，{ending}"
          f"最长回复 {max(r['chars'] for r in rounds)} 字，"
          f"TTS 合计 {total_audio / 1024 / 1024:.2f} MiB。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
