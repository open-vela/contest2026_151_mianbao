"""
AI模拟面试官 — ASR 语音识别服务
使用 xiaomi mimo ASR API
负责：A同学
"""
import base64
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# xiaomi mimo API 配置
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
ASR_MODEL = "mimo-v2.5-asr"


def asr_audio_to_text(audio_base64: str, audio_format: str = "wav", language: str = "zh") -> str:
    """
    将音频转换为文字（ASR）

    Args:
        audio_base64: base64 编码的音频数据
        audio_format: 音频格式，支持 "wav" 或 "mp3"
        language: 语言代码，支持 "zh"（中文）、"en"（英文）、"auto"（自动检测）

    Returns:
        识别出的文字，失败时返回空字符串
    """
    if not audio_base64:
        logger.warning("ASR: 音频数据为空")
        return ""

    try:
        # 创建 OpenAI 客户端（兼容 xiaomi mimo API）
        client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL
        )

        # 构建 data URL
        mime_type = "audio/wav" if audio_format == "wav" else "audio/mpeg"
        audio_data_url = f"data:{mime_type};base64,{audio_base64}"

        logger.info(f"ASR: 开始识别，音频格式={audio_format}，语言={language}")

        # 调用 ASR API
        completion = client.chat.completions.create(
            model=ASR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data_url
                            }
                        }
                    ]
                }
            ],
            extra_body={
                "asr_options": {
                    "language": language
                }
            }
        )

        # 提取识别结果
        result_text = completion.choices[0].message.content
        logger.info(f"ASR: 识别完成，结果长度={len(result_text)}")

        return result_text

    except Exception as e:
        logger.error(f"ASR 调用失败: {str(e)}")
        return ""


def asr_audio_file_to_text(file_path: str, language: str = "zh") -> str:
    """
    从文件读取音频并转换为文字

    Args:
        file_path: 音频文件路径（支持 wav 和 mp3）
        language: 语言代码

    Returns:
        识别出的文字
    """
    try:
        # 读取音频文件
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        # 转换为 base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # 根据文件扩展名确定格式
        file_ext = os.path.splitext(file_path)[1].lower()
        audio_format = "mp3" if file_ext == ".mp3" else "wav"

        return asr_audio_to_text(audio_base64, audio_format, language)

    except Exception as e:
        logger.error(f"ASR 文件读取失败: {str(e)}")
        return ""


# 测试函数
if __name__ == "__main__":
    # 测试用例
    print("ASR 服务模块已加载")
    print(f"API Key: {MIMO_API_KEY[:10]}..." if MIMO_API_KEY != "your_api_key_here" else "API Key: 未配置")
