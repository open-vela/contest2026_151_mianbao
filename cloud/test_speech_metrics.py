"""speech_metrics 单元测试（纯标准库，不依赖 Flask / 网络）。

重点守三件事：
1. 口头语只数明确的语气词，**不误伤"然后/就是"**；
2. 停顿检测对合成音频给得出合理结果；
3. 没有音频时（文字演练）绝不编造语速。
"""
import io
import math
import struct
import unittest
import wave

import speech_metrics


def make_wav(segments, rate=16000):
    """segments: [(秒数, 是否发声)] → 16bit 单声道 WAV bytes。"""
    frames = []
    for seconds, voiced in segments:
        count = int(rate * seconds)
        for i in range(count):
            if voiced:
                # 440Hz 正弦，幅度 0.3（约 -10dBFS）
                value = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / rate))
            else:
                value = 0
            frames.append(value)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(struct.pack("<%dh" % len(frames), *frames))
    return buf.getvalue()


class TestFillerStats(unittest.TestCase):
    def test_counts_explicit_fillers(self):
        total, detail = speech_metrics.filler_stats("嗯，我觉得呃这个方案那个可以")
        self.assertEqual(total, 3)
        self.assertEqual(detail, {"嗯": 1, "呃": 1, "那个": 1})

    def test_multi_char_filler_not_double_counted(self):
        total, detail = speech_metrics.filler_stats("就是说，嗯，就是说")
        self.assertEqual(detail.get("就是说"), 2)
        self.assertEqual(detail.get("嗯"), 1)
        self.assertEqual(total, 3)

    def test_connectors_not_counted(self):
        """然后/就是 是正常连接词，不能算口头语。"""
        total, detail = speech_metrics.filler_stats("然后我做了缓存，就是用了 Redis")
        self.assertEqual(total, 0)
        self.assertEqual(detail, {})


class TestCharCount(unittest.TestCase):
    def test_cjk_and_english_words(self):
        self.assertEqual(speech_metrics.count_chars("我用了 Redis 缓存，QPS 提升 3 倍。"), 10)

    def test_empty(self):
        self.assertEqual(speech_metrics.count_chars(""), 0)


class TestWavStats(unittest.TestCase):
    def test_pause_detection(self):
        # 1s 说话 + 1s 静音 + 1s 说话 → 1 次停顿，最长 1s
        stats = speech_metrics.wav_stats(make_wav([(1.0, True), (1.0, False), (1.0, True)]))
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats["duration_sec"], 3.0, places=1)
        self.assertEqual(stats["pauses"], 1)
        self.assertAlmostEqual(stats["longest_pause_sec"], 1.0, places=1)
        self.assertGreater(stats["speech_ratio"], 0.5)

    def test_short_gap_not_counted(self):
        # 0.3s 的静音不够 0.5s，不算停顿
        stats = speech_metrics.wav_stats(make_wav([(1.0, True), (0.3, False), (1.0, True)]))
        self.assertEqual(stats["pauses"], 0)

    def test_invalid_audio(self):
        self.assertIsNone(speech_metrics.wav_stats(b"not a wav"))
        self.assertIsNone(speech_metrics.wav_stats(b""))


class TestSpeechMetrics(unittest.TestCase):
    def test_text_only_has_no_fake_speed(self):
        metrics = speech_metrics.speech_metrics("嗯，我先说结论，然后讲依据。", None)
        self.assertEqual(metrics["chars"], 11)
        self.assertEqual(metrics["fillers"], 1)
        self.assertIsNone(metrics["duration_sec"])
        self.assertIsNone(metrics["chars_per_min"])
        self.assertIsNone(metrics["pauses"])

    def test_with_audio(self):
        audio = make_wav([(2.0, True), (1.0, False), (2.0, True)])
        metrics = speech_metrics.speech_metrics("我负责检索链路，召回率做到了九成。", audio)
        self.assertAlmostEqual(metrics["duration_sec"], 5.0, places=1)
        self.assertEqual(metrics["pauses"], 1)
        self.assertIsNotNone(metrics["chars_per_min"])
        self.assertGreater(metrics["chars_per_min"], 100)

    def test_empty_text(self):
        metrics = speech_metrics.speech_metrics("", None)
        self.assertEqual(metrics["chars"], 0)
        self.assertEqual(metrics["fillers"], 0)


if __name__ == "__main__":
    unittest.main()
