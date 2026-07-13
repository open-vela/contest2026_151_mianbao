"""
AI模拟面试官 — TTS 语音合成服务
使用 xiaomi mimo TTS API
负责：A同学（协助完善）
"""
import base64
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# xiaomi mimo API 配置
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
TTS_MODEL = "mimo-v2.5-tts"

# 预置音色配置（面试官使用专业、友好的女声）
DEFAULT_VOICE = "冰糖"  # 中文女性音色，适合面试官场景


def tts_text_to_audio(text: str, voice: str = None, style: str = None) -> str:
    """
    将文字转换为音频（TTS）

    Args:
        text: 要合成的文字
        voice: 音色名称，可选值见预置音色列表，默认使用 "冰糖"
        style: 语音风格描述（自然语言控制），例如 "专业、友好、有洞察力"

    Returns:
        base64 编码的音频数据，失败时返回空字符串
    """
    if not text:
        logger.warning("TTS: 文字内容为空")
        return ""

    try:
        # 创建 OpenAI 客户端（兼容 xiaomi mimo API）
        client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL
        )

        # 使用默认音色
        if voice is None:
            voice = DEFAULT_VOICE

        # 构建消息
        messages = []

        # 如果有风格控制，添加 user 消息
        if style:
            messages.append({
                "role": "user",
                "content": style
            })

        # 添加要合成的文字（必须放在 assistant 角色中）
        messages.append({
            "role": "assistant",
            "content": text
        })

        logger.info(f"TTS: 开始合成，音色={voice}，文本长度={len(text)}")

        # 调用 TTS API（非流式，返回 wav 格式）
        completion = client.chat.completions.create(
            model=TTS_MODEL,
            messages=messages,
            audio={
                "format": "wav",
                "voice": voice
            }
        )

        # 提取音频数据
        message = completion.choices[0].message
        if hasattr(message, 'audio') and message.audio:
            audio_bytes = base64.b64decode(message.audio.data)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            logger.info(f"TTS: 合成完成，音频大小={len(audio_bytes)} 字节")
            return audio_base64
        else:
            logger.error("TTS: 未返回音频数据")
            return ""

    except Exception as e:
        logger.error(f"TTS 调用失败: {str(e)}")
        return ""


def tts_text_to_audio_stream(text: str, output_file: str, voice: str = None, style: str = None) -> bool:
    """
    将文字转换为音频并保存到文件（流式）

    Args:
        text: 要合成的文字
        output_file: 输出音频文件路径
        voice: 音色名称
        style: 语音风格描述

    Returns:
        是否成功
    """
    try:
        import numpy as np
        import soundfile as sf

        # 创建 OpenAI 客户端
        client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL
        )

        # 使用默认音色
        if voice is None:
            voice = DEFAULT_VOICE

        # 构建消息
        messages = []
        if style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})

        logger.info(f"TTS 流式: 开始合成，音色={voice}")

        # 流式调用 TTS API
        completion = client.chat.completions.create(
            model=TTS_MODEL,
            messages=messages,
            audio={
                "format": "pcm16",
                "voice": voice
            },
            stream=True
        )

        # 收集音频数据
        collected_chunks = np.array([], dtype=np.float32)

        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            audio = getattr(delta, "audio", None)

            if audio is not None:
                pcm_bytes = base64.b64decode(audio["data"])
                np_pcm = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                collected_chunks = np.concatenate((collected_chunks, np_pcm))

        # 保存到文件
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        sf.write(output_file, collected_chunks, samplerate=24000)
        logger.info(f"TTS 流式: 音频已保存到 {output_file}")

        return True

    except Exception as e:
        logger.error(f"TTS 流式调用失败: {str(e)}")
        return False


# 测试函数
if __name__ == "__main__":
    print("TTS 服务模块已加载")
    print(f"API Key: {MIMO_API_KEY[:10]}..." if MIMO_API_KEY != "your_api_key_here" else "API Key: 未配置")
    print(f"默认音色: {DEFAULT_VOICE}")
