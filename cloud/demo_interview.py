"""
AI模拟面试官 — 完整面试流程演示
负责：A同学
"""
import os
import sys
import time
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


def speak(text: str, voice: str = "冰糖") -> bool:
    """让面试官说话"""
    from tts_service import tts_text_to_audio
    from play_tts import play_audio_file

    logger.info(f"面试官: {text}")

    # TTS 合成
    import base64
    audio_base64 = tts_text_to_audio(text, voice=voice)

    if not audio_base64:
        logger.error("TTS 合成失败")
        return False

    # 保存并播放
    temp_file = "/tmp/interview_speak.wav"
    with open(temp_file, "wb") as f:
        f.write(base64.b64decode(audio_base64))

    success = play_audio_file(temp_file)

    try:
        os.remove(temp_file)
    except:
        pass

    return success


def listen(duration: int = 5) -> str:
    """录音并识别"""
    from asr_service import asr_audio_file_to_text

    temp_file = "/tmp/interview_record.wav"

    logger.info(f"开始录音 ({duration}秒)...")

    # 使用 arecord 录音
    try:
        subprocess.run([
            "arecord",
            "-f", "S16_LE",      # 16-bit little-endian
            "-r", "16000",       # 16kHz 采样率
            "-c", "1",           # 单声道
            "-d", str(duration), # 录音时长
            temp_file
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"录音失败: {e}")
        return ""

    logger.info("录音完成，开始识别...")

    # ASR 识别
    text = asr_audio_file_to_text(temp_file, language="zh")

    # 清理
    try:
        os.remove(temp_file)
    except:
        pass

    if text:
        logger.info(f"识别结果: {text}")
    else:
        logger.warning("未识别到语音")

    return text


def demo_interview():
    """演示面试流程"""
    print("🎤" + "="*50)
    print("   AI模拟面试官 — 完整面试流程演示")
    print("="*52)
    print()

    # 面试问题列表
    questions = [
        "你好，欢迎参加今天的面试。请先简单介绍一下你自己。",
        "好的，谢谢你的介绍。请谈谈你最大的优点和缺点是什么？",
        "很好。最后一个问题：你为什么想加入我们公司？",
    ]

    # 开场白
    speak("你好，我是AI模拟面试官，今天由我来为你进行面试。准备好了吗？")
    time.sleep(1)

    # 问答循环
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*50}")
        print(f"问题 {i}/{len(questions)}")
        print(f"{'='*50}")

        # 面试官提问
        speak(question)

        # 等待应聘者回答
        print("\n🎤 请回答... (等待录音)")
        answer = listen(duration=10)  # 录音10秒

        if answer:
            print(f"\n✅ 你的回答: {answer}")

            # 简单回应
            if i < len(questions):
                speak("好的，我了解了。")
            else:
                speak("好的，今天的面试到这里。感谢你的参与！")
        else:
            print("\n⚠️  未检测到语音，跳过...")
            speak("没有听到回答，我们继续下一个问题。")

        time.sleep(1)

    # 结束
    speak("面试结束，祝你有美好的一天！再见！")
    print("\n" + "="*50)
    print("✅ 面试演示完成!")
    print("="*50)


def demo_simple():
    """简单演示：只播放问题"""
    print("🎤" + "="*50)
    print("   AI模拟面试官 — 简单播放演示")
    print("="*52)
    print()

    questions = [
        "你好，欢迎参加今天的面试。",
        "请简单介绍一下你自己。",
        "你最大的优点是什么？",
        "谢谢你的回答。",
    ]

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {q}")
        speak(q)
        time.sleep(2)

    print("\n✅ 演示完成!")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        # 完整演示（包含录音）
        demo_interview()
    else:
        # 简单演示（只播放）
        demo_simple()


if __name__ == "__main__":
    main()
