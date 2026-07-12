"""
AI模拟面试官 — ASR/TTS 服务测试脚本
负责：A同学
"""
import os
import sys
import logging

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_tts():
    """测试 TTS 服务"""
    print("\n" + "="*60)
    print("测试 TTS 语音合成服务")
    print("="*60)

    from tts_service import tts_text_to_audio, tts_text_to_audio_stream

    # 测试文本
    test_text = "你好，我是AI模拟面试官。欢迎参加今天的面试，请简单介绍一下你自己。"
    print(f"\n测试文本: {test_text}")
    print(f"文本长度: {len(test_text)} 字符")

    # 测试1: 非流式合成
    print("\n[测试1] 非流式 TTS 合成...")
    audio_base64 = tts_text_to_audio(test_text, voice="冰糖")

    if audio_base64:
        print(f"✅ TTS 非流式合成成功!")
        print(f"   音频数据大小: {len(audio_base64)} 字节 (base64)")

        # 保存音频文件
        import base64
        output_file = "test_tts_output.wav"
        with open(output_file, "wb") as f:
            f.write(base64.b64decode(audio_base64))
        print(f"   音频已保存到: {output_file}")
        print(f"   文件大小: {os.path.getsize(output_file)} 字节")
    else:
        print("❌ TTS 非流式合成失败!")
        return False

    # 测试2: 流式合成
    print("\n[测试2] 流式 TTS 合成...")
    stream_output = "test_tts_stream_output.wav"
    success = tts_text_to_audio_stream(test_text, stream_output, voice="冰糖")

    if success and os.path.exists(stream_output):
        print(f"✅ TTS 流式合成成功!")
        print(f"   音频已保存到: {stream_output}")
        print(f"   文件大小: {os.path.getsize(stream_output)} 字节")
    else:
        print("❌ TTS 流式合成失败!")

    return True


def test_asr(audio_file=None):
    """测试 ASR 服务"""
    print("\n" + "="*60)
    print("测试 ASR 语音识别服务")
    print("="*60)

    from asr_service import asr_audio_file_to_text, asr_audio_to_text

    # 如果没有指定音频文件，使用 TTS 生成的测试文件
    if audio_file is None:
        audio_file = "test_tts_output.wav"

    if not os.path.exists(audio_file):
        print(f"❌ 音频文件不存在: {audio_file}")
        print("   请先运行 TTS 测试生成音频文件")
        return False

    print(f"\n音频文件: {audio_file}")
    print(f"文件大小: {os.path.getsize(audio_file)} 字节")

    # 测试1: 从文件识别
    print("\n[测试1] 从文件进行 ASR 识别...")
    result = asr_audio_file_to_text(audio_file, language="zh")

    if result:
        print(f"✅ ASR 识别成功!")
        print(f"   识别结果: {result}")
        print(f"   结果长度: {len(result)} 字符")
    else:
        print("❌ ASR 识别失败!")
        return False

    # 测试2: 从 base64 数据识别
    print("\n[测试2] 从 base64 数据进行 ASR 识别...")
    import base64
    with open(audio_file, "rb") as f:
        audio_bytes = f.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    result2 = asr_audio_to_text(audio_base64, audio_format="wav", language="zh")

    if result2:
        print(f"✅ ASR base64 识别成功!")
        print(f"   识别结果: {result2}")
    else:
        print("❌ ASR base64 识别失败!")

    return True


def test_integration():
    """集成测试：TTS -> ASR 完整流程"""
    print("\n" + "="*60)
    print("集成测试：TTS -> ASR 完整流程")
    print("="*60)

    from tts_service import tts_text_to_audio
    from asr_service import asr_audio_to_text

    # 原始文本
    original_text = "请介绍一下你的项目经验"
    print(f"\n原始文本: {original_text}")

    # TTS 合成
    print("\n[步骤1] TTS 合成音频...")
    audio_base64 = tts_text_to_audio(original_text, voice="冰糖")

    if not audio_base64:
        print("❌ TTS 合成失败，无法继续测试")
        return False

    print(f"✅ TTS 合成成功，音频大小: {len(audio_base64)} 字节")

    # ASR 识别
    print("\n[步骤2] ASR 识别音频...")
    recognized_text = asr_audio_to_text(audio_base64, audio_format="wav", language="zh")

    if not recognized_text:
        print("❌ ASR 识别失败")
        return False

    print(f"✅ ASR 识别成功")
    print(f"   识别结果: {recognized_text}")

    # 对比结果
    print("\n[结果对比]")
    print(f"   原始文本: {original_text}")
    print(f"   识别结果: {recognized_text}")

    # 简单相似度检查
    if original_text in recognized_text or recognized_text in original_text:
        print("✅ 识别结果与原始文本高度匹配!")
    else:
        print("⚠️  识别结果与原始文本有差异（可能正常，取决于音频质量）")

    return True


def main():
    """主测试函数"""
    print("🚀 AI模拟面试官 — ASR/TTS 服务测试")
    print("="*60)

    # 检查 API Key
    from tts_service import MIMO_API_KEY
    if not MIMO_API_KEY or MIMO_API_KEY == "your_api_key_here":
        print("❌ 错误: 未配置 MIMO API Key")
        print("   请设置环境变量 MIMO_API_KEY 或修改配置文件")
        return

    print(f"✅ API Key 已配置: {MIMO_API_KEY[:10]}...")

    # 运行测试
    tests = [
        ("TTS 服务", test_tts),
        ("ASR 服务", lambda: test_asr()),
        ("集成测试", test_integration),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} 测试出错: {str(e)}")
            results.append((test_name, False))

    # 测试总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过")


if __name__ == "__main__":
    main()
