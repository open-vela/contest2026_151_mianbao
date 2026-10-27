"""副语言（表达状态）指标 —— 2026-10-27 加。

为什么有这个模块
----------------
面试练习最容易丢掉的恰恰是"怎么说"：语速、口头语、停顿。现有报告只看内容
（技术正确性/深度/工程/表达结构），而 `/text` 演练页自己都写着"打字练不出
语速、卡壳和口头语"——这里补的就是这一块。

**只做云端、只依赖标准库**：ASR 文本已经在手上（`asr_service`），音频解码用
`wave` + `array`（Python 3.13 起 `audioop` 已移除，不碰它）。不引入 Whisper /
librosa：多跑一遍模型既慢又贵，而我们只需要统计量。

指标的取舍（都有理由，别轻易改）
--------------------------------
* **口头语只数明确的语气词**：嗯/啊/呃/额/那个/就是说/怎么说呢/反正。
  **刻意不数"然后/就是"**——它们在结构化回答里是正常连接词，数进去会把
  条理清楚的人打成结巴（中文没有词边界，按字符匹配没法消歧）。
* **语速用"字/分钟"**：中文不适用英文的 WPM。字数只算 CJK 汉字与英文单词，
  标点和空白不计。
* **停顿看能量**：100ms 一块算均方，噪声底取 10 分位、语音电平取 90 分位，
  阈值取两者之间 20% 处；连续 ≥0.5s 低于阈值算一次停顿。自适应阈值是为了
  不绑死某个录音电平（板子/手机/网页录音音量差很多）。
* **拿不到音频就不编**：`/text` 演练没有音频，时长/语速/停顿一律返回 None，
  前端显示"—"，绝不用字数去猜一个"假语速"。
"""
import base64
import logging
import math
import re
import struct
import wave

logger = logging.getLogger(__name__)

# 明确的语气填充词（按出现次数计）。长词优先，避免"就是说"被"说"重复计。
FILLERS = ("怎么说呢", "就是说", "那个", "嗯", "啊", "呃", "额", "反正")

# 停顿/语速参数
CHUNK_MS = 100                 # 与板子主循环节拍一致
PAUSE_MIN_SEC = 0.5            # 多长的静音算一次"停顿"
MIN_AUDIO_SEC = 0.5            # 太短的音频不做分析

_CJK = re.compile(r"[一-鿿]")
_WORD = re.compile(r"[A-Za-z]+")
_PUNCT = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()\[\]【】…—-]+")


def count_chars(text: str) -> int:
    """有效字数：CJK 汉字数 + 英文单词数（标点/空白不算）。"""
    if not text:
        return 0
    return len(_CJK.findall(text)) + len(_WORD.findall(text))


def filler_stats(text: str):
    """口头语统计。返回 (总数, 明细 dict)。长词优先匹配，不重复计数。"""
    if not text:
        return 0, {}
    detail = {}
    total = 0
    remaining = text
    for word in FILLERS:               # FILLERS 已按长度降序
        n = remaining.count(word)
        if n:
            detail[word] = n
            total += n
            remaining = remaining.replace(word, "\0")   # 占位，防短词重复吃
    return total, detail


def wav_stats(audio_bytes):
    """解析 WAV，返回时长/停顿/有声占比；解析不了返回 None。

    返回 dict:
        duration_sec, pauses, longest_pause_sec, speech_ratio
    """
    if not audio_bytes:
        return None
    try:
        import io
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError, ValueError, struct.error) as error:
        logger.info(f"[表达] WAV 解析失败，跳过音频指标：{error}")
        return None

    if width not in (1, 2, 4) or rate <= 0 or channels <= 0 or not frames:
        return None

    # 按块算均方（int16 为主；其余宽度按位宽归一到 16bit 量级）
    sample_bytes = width * channels
    total_frames = len(frames) // sample_bytes
    chunk_frames = max(1, rate * CHUNK_MS // 1000)
    scale = {1: 256.0, 2: 1.0, 4: 1.0 / 65536.0}[width]
    fmt = {1: "b", 2: "h", 4: "i"}[width]

    energies = []
    for start in range(0, total_frames, chunk_frames):
        end = min(start + chunk_frames, total_frames)
        raw = frames[start * sample_bytes:end * sample_bytes]
        samples = struct.unpack("<%d%s" % (len(raw) // width, fmt), raw)
        if channels > 1:
            samples = samples[::channels]
        if not samples:
            continue
        acc = 0.0
        for s in samples:
            v = float(s) * scale / 32768.0
            acc += v * v
        energies.append(acc / len(samples))

    if not energies:
        return None

    ordered = sorted(energies)
    noise = ordered[int(len(ordered) * 0.10)]
    speech = ordered[int(len(ordered) * 0.90)]
    threshold = noise + (speech - noise) * 0.20
    if speech <= noise:                 # 全静音/全噪声：无从判断
        return None

    durations = len(frames) / float(sample_bytes) / rate

    # 连续低于阈值的块 → 静音段
    pauses = []
    run_start = None
    for index, energy in enumerate(energies):
        if energy < threshold:
            if run_start is None:
                run_start = index
        else:
            if run_start is not None:
                pauses.append((index - run_start) * CHUNK_MS / 1000.0)
                run_start = None
    if run_start is not None:
        pauses.append((len(energies) - run_start) * CHUNK_MS / 1000.0)

    long_pauses = [p for p in pauses if p >= PAUSE_MIN_SEC]
    voiced = sum(1 for e in energies if e >= threshold)
    return {
        "duration_sec": round(durations, 2),
        "pauses": len(long_pauses),
        "longest_pause_sec": round(max(long_pauses), 2) if long_pauses else 0.0,
        "speech_ratio": round(voiced / float(len(energies)), 2),
    }


def speech_metrics(text: str, audio_bytes=None):
    """汇总一轮回答的表达指标。

    `audio_bytes` 为 None（文字演练）时，时长/语速/停顿/占比全为 None ——
    宁可显示"—"，也不根据字数编一个假语速。
    """
    text = (text or "").strip()
    chars = count_chars(text)
    fillers, detail = filler_stats(text)

    duration = None
    chars_per_min = None
    pauses = None
    longest_pause = None
    speech_ratio = None

    stats = wav_stats(audio_bytes) if audio_bytes else None
    if stats and stats["duration_sec"] >= MIN_AUDIO_SEC and chars:
        duration = stats["duration_sec"]
        # 语速按"有声时间"算更接近真实语速：停顿不该拉低语速
        voiced = duration * stats["speech_ratio"]
        if voiced > 0.2:
            chars_per_min = round(chars / voiced * 60.0, 0)
        pauses = stats["pauses"]
        longest_pause = stats["longest_pause_sec"]
        speech_ratio = stats["speech_ratio"]

    return {
        "chars": chars,
        "fillers": fillers,
        "filler_detail": detail,
        "duration_sec": duration,
        "chars_per_min": chars_per_min,
        "pauses": pauses,
        "longest_pause_sec": longest_pause,
        "speech_ratio": speech_ratio,
    }
