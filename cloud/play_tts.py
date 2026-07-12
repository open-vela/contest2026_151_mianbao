"""
AI模拟面试官 — TTS 语音播放脚本
负责：A同学
"""
import os
import sys
import subprocess
import logging

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def play_audio_file(file_path: str, player: str = "auto") -> bool:
    """
    播放音频文件

    Args:
        file_path: 音频文件路径
        player: 播放器选择 ("aplay", "paplay", "play", "auto")

    Returns:
        是否播放成功
    """
    if not os.path.exists(file_path):
        logger.error(f"音频文件不存在: {file_path}")
        return False

    # 自动选择播放器
    if player == "auto":
        # 优先使用 PulseAudio，然后是 ALSA，最后是 SoX
        for p in ["paplay", "aplay", "play"]:
            try:
                subprocess.run(["which", p], capture_output=True, check=True)
                player = p
                break
            except subprocess.CalledProcessError:
                continue

    logger.info(f"使用播放器: {player}")
    logger.info(f"播放文件: {file_path}")

    try:
        if player == "paplay":
            subprocess.run(["paplay", file_path], check=True)
        elif player == "aplay":
            subprocess.run(["aplay", file_path], check=True)
        elif player == "play":
            subprocess.run(["play", file_path], check=True)
        else:
            logger.error(f"不支持的播放器: {player}")
            return False

        logger.info("播放完成")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"播放失败: {e}")
        return False
    except KeyboardInterrupt:
        logger.info("播放被用户中断")
        return True


def tts_and_play(text: str, voice: str = "冰糖") -> bool:
    """
    合成语音并立即播放

    Args:
        text: 要合成的文字
        voice: 音色名称

    Returns:
        是否成功
    """
    from tts_service import tts_text_to_audio

    logger.info(f"合成语音: {text}")

    # TTS 合成
    audio_base64 = tts_text_to_audio(text, voice=voice)

    if not audio_base64:
        logger.error("TTS 合成失败")
        return False

    # 保存到临时文件
    import base64
    temp_file = "/tmp/tts_play_temp.wav"
    with open(temp_file, "wb") as f:
        f.write(base64.b64decode(audio_base64))

    logger.info(f"音频已保存到: {temp_file}")

    # 播放
    success = play_audio_file(temp_file)

    # 清理临时文件
    try:
        os.remove(temp_file)
    except:
        pass

    return success


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 从命令行参数获取文本
        text = " ".join(sys.argv[1:])
    else:
        # 默认测试文本
        text = "你好，我是AI模拟面试官。欢迎参加今天的面试，请简单介绍一下你自己。"

    print(f"🎤 TTS 语音播放测试")
    print(f"=" * 50)
    print(f"文本: {text}")
    print(f"=" * 50)

    success = tts_and_play(text)

    if success:
        print("✅ 播放完成!")
    else:
        print("❌ 播放失败!")


if __name__ == "__main__":
    main()
