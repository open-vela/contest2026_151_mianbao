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
    python3 cloud/rehearsal.py --no-tts                  # 跳过硬编码兜底文本，省一次 TTS

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
"""
import argparse
import base64
import json
import sys
import time
import uuid

import requests

# ---------------- 判据阈值（改动要同步更新台账 §11.21） ----------------

# 端侧 8MiB 缓冲（CLOUD_RESP_MAX）的一半。TTS 音频 base64 会再胀 1/3，
# 所以这里量的是**解码后**的字节数。
MAX_TTS_BYTES = 4 * 1024 * 1024

# 单条问句上限：提示词要求 120 字以内，留出模型的越界余量。
MAX_QUESTION_CHARS = 150

# 报告上限：提示词要求 200 字以内，余量同上。
MAX_REPORT_CHARS = 250

# 一轮面试成功的标志：11 次调用后历史里正好 11 问 + 11 答。
EXPECTED_MESSAGES = 22
EXPECTED_ROUNDS = 11

# 参考块/提示词的痕迹绝不能出现在模型输出里 —— 会被 TTS 逐字念给候选人听。
LEAK_STRINGS = ("题库", "参考题", "参考资料", "使用要求", "面试纪律", "硬性要求",
                "**", "##", "理由：", "判断：", "新问题：", "问题设计说明", "下一步：")

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


def main() -> int:
    parser = argparse.ArgumentParser(description="PC 端面试排练（11 轮端云链路体检）")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--role", default="AI 应用开发", help="面试岗位，默认演示岗位")
    parser.add_argument("--rounds", type=int, default=EXPECTED_ROUNDS)
    parser.add_argument("--no-tts", action="store_true",
                        help="候选人语音改用预置的静音 WAV，省一轮 TTS 调用"
                             "（只用于链路自检，题库那条路会退化，不要用它下结论）")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    session_id = str(uuid.uuid4())
    failures = []
    rounds = []

    def fail(message: str) -> None:
        failures.append(message)
        print(f"  ❌ {message}")

    print(f"排练目标：{base_url}  岗位={args.role}  轮数={args.rounds}  session={session_id}")
    print("-" * 78)

    status, body = get_json(f"{base_url}/api/health")
    if status != 200:
        print(f"❌ 健康检查失败（HTTP {status}）—— 云端起了吗？{base_url}")
        return 1
    print(f"✅ 健康检查 HTTP {status}\n")

    for index in range(args.rounds):
        number = index + 1
        answer = CANDIDATE_ANSWERS[index % len(CANDIDATE_ANSWERS)]
        started = time.time()

        if args.no_tts:
            # 44 字节的极小 WAV 头 + 一段静音，仅用于确认链路能通
            audio = base64.b64encode(
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00").decode()
        else:
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
        if not user_text.strip():
            fail(f"第 {number} 轮 ASR 结果为空 —— 这一轮会走空识别短路，"
                 f"历史对不齐，后面的判据都不作数")
            break
        if audio_bytes > MAX_TTS_BYTES:
            fail(f"第 {number} 轮 TTS 音频 {audio_bytes / 1024 / 1024:.2f} MiB "
                 f"超过 {MAX_TTS_BYTES / 1024 / 1024:.0f} MiB")
        hits = [leak for leak in LEAK_STRINGS if leak in text]
        if hits:
            fail(f"第 {number} 轮输出里出现泄漏串 {hits}（会被逐字念出来）")

        is_last = number == args.rounds
        if not is_last:
            if len(text) > MAX_QUESTION_CHARS:
                fail(f"第 {number} 轮问句 {len(text)} 字，超过 {MAX_QUESTION_CHARS} 字（话痨复发？）")
            if kind != "question":
                fail(f"第 {number} 轮 type={kind}，应为 question")
        else:
            if kind != "report":
                fail(f"第 {number} 轮 type={kind}，应为 report —— 报告没接上或轮数不对")
            elif len(text) > MAX_REPORT_CHARS:
                fail(f"报告 {len(text)} 字，超过 {MAX_REPORT_CHARS} 字")

    print("-" * 78)

    # 历史体检：22 条、无超长 assistant 消息
    status, snapshot = get_json(f"{base_url}/api/history?session_id={session_id}")
    if status != 200:
        fail(f"/api/history 返回 HTTP {status}")
    else:
        messages = snapshot.get("messages", [])
        print(f"历史：{len(messages)} 条（期望 {EXPECTED_MESSAGES} 条）")
        if len(messages) != EXPECTED_MESSAGES:
            fail(f"历史 {len(messages)} 条 ≠ {EXPECTED_MESSAGES} 条 —— "
                 f"说明有轮次没走完整（空识别短路？）")
        longest = max((len(m.get("content", "")) for m in messages
                       if m.get("role") == "assistant"), default=0)
        if longest > MAX_REPORT_CHARS:
            fail(f"历史里最长的面试官消息 {longest} 字 > {MAX_REPORT_CHARS} 字")

    print()
    if failures:
        print(f"❌ 排练失败，{len(failures)} 项不达标：")
        for message in failures:
            print(f"   · {message}")
        return 1

    total_audio = sum(r["audio"] for r in rounds)
    print(f"✅ 排练通过：{len(rounds)} 轮全部正常，末轮为报告。"
          f"最大问句 {max(r['chars'] for r in rounds)} 字，"
          f"TTS 合计 {total_audio / 1024 / 1024:.2f} MiB。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
