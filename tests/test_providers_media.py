import shutil
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.providers import ProviderRegistry
from core.providers_media import (
    BrowserRenderAdapter,
    EdgeTTSAdapter,
    FasterWhisperSTTAdapter,
    MMSTTSAdapter,
    PiperTTSAdapter,
    ProviderUnavailableError,
    register_defaults,
)


def _has_module(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


HAS_EDGE_TTS = _has_module("edge_tts")
HAS_PIPER = _has_module("piper")
HAS_FASTER_WHISPER = _has_module("faster_whisper")
HAS_PLAYWRIGHT = _has_module("playwright")
HAS_TRANSFORMERS = _has_module("transformers")
HAS_TORCH = _has_module("torch")
HAS_SOUNDFILE = _has_module("soundfile")
HAS_MMS_TTS = HAS_TRANSFORMERS and HAS_TORCH and HAS_SOUNDFILE
HAS_FFPROBE = bool(shutil.which("ffprobe"))

PIPER_MODEL = PiperTTSAdapter.DEFAULT_MODELS_DIR / "en_US-lessac-medium.onnx"
HAS_PIPER_MODEL = HAS_PIPER and PIPER_MODEL.exists()

PIPER_TH_MODEL = PiperTTSAdapter.DEFAULT_MODELS_DIR / "th_TH-mms_female-medium.onnx"
HAS_PIPER_TH_MODEL = HAS_PIPER and PIPER_TH_MODEL.exists()

THAI_TEST_SENTENCE = "สวัสดีครับ นี่คือการทดสอบเสียงภาษาไทยของระบบคลิปมี"


class RegisterDefaultsTests(unittest.TestCase):
    def test_register_defaults_wires_all_three_capabilities(self):
        registry = ProviderRegistry()
        register_defaults(registry)
        self.assertIn("generate_voice", registry.capabilities())
        self.assertIn("transcribe", registry.capabilities())
        self.assertIn("render_html", registry.capabilities())
        self.assertIsInstance(registry.get("generate_voice"), EdgeTTSAdapter)
        self.assertIsInstance(registry.get("transcribe"), FasterWhisperSTTAdapter)
        self.assertIsInstance(registry.get("render_html"), BrowserRenderAdapter)


class EdgeTTSAdapterTests(unittest.TestCase):
    def test_raises_clean_error_when_package_missing(self):
        if HAS_EDGE_TTS:
            self.skipTest("edge-tts is installed; missing-package path not reachable here")
        adapter = EdgeTTSAdapter()
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_voice("hello", "/tmp/should-not-exist.mp3")

    @unittest.skipUnless(HAS_EDGE_TTS, "edge-tts not installed")
    def test_generate_voice_produces_real_audio(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-edge-tts-"))
        out_path = tmp / "voice.mp3"
        adapter = EdgeTTSAdapter()
        try:
            result = adapter.generate_voice(
                "Clip me local text to speech test.",
                out_path,
                voice="en-US-AriaNeural",
            )
        except ProviderUnavailableError as exc:
            # Real (network-dependent) failure on a network-less run; do not
            # treat as a fabricated pass, but also don't fail CI over it.
            self.skipTest(f"edge-tts network call unavailable: {exc}")
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "edge_tts")
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        if HAS_FFPROBE:
            self.assertIsNotNone(result["duration_s"])
            self.assertGreater(result["duration_s"], 0)


class PiperTTSAdapterTests(unittest.TestCase):
    def test_raises_clean_error_when_model_missing(self):
        adapter = PiperTTSAdapter()
        tmp = Path(tempfile.mkdtemp(prefix="clipme-piper-empty-"))
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_voice(
                "hello", tmp / "out.wav", voice="does-not-exist", models_dir=tmp,
            )

    @unittest.skipUnless(HAS_PIPER_MODEL, "piper-tts + en_US-lessac-medium model not installed")
    def test_generate_voice_produces_real_wav(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-piper-"))
        out_path = tmp / "voice.wav"
        adapter = PiperTTSAdapter()
        result = adapter.generate_voice(
            "Clip me local text to speech test.",
            out_path,
            voice="en_US-lessac-medium",
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "piper_tts")
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        if HAS_FFPROBE:
            self.assertIsNotNone(result["duration_s"])
            self.assertGreater(result["duration_s"], 0)


class FasterWhisperSTTAdapterTests(unittest.TestCase):
    def test_raises_clean_error_when_audio_missing(self):
        if not HAS_FASTER_WHISPER:
            self.skipTest("faster-whisper not installed")
        adapter = FasterWhisperSTTAdapter()
        with self.assertRaises(ProviderUnavailableError):
            adapter.transcribe("/tmp/clipme-does-not-exist.mp3")

    @unittest.skipUnless(
        HAS_FASTER_WHISPER and HAS_EDGE_TTS,
        "faster-whisper and edge-tts both required for the real round trip",
    )
    def test_tts_to_stt_round_trip_matches_most_words(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-stt-roundtrip-"))
        audio_path = tmp / "voice.mp3"
        source_text = "Clip me local text to speech test today"

        tts = EdgeTTSAdapter()
        try:
            tts.generate_voice(source_text, audio_path, voice="en-US-AriaNeural")
        except ProviderUnavailableError as exc:
            self.skipTest(f"edge-tts network call unavailable: {exc}")

        stt = FasterWhisperSTTAdapter()
        result = stt.transcribe(str(audio_path), language="en", model_size="base")

        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "faster_whisper")
        self.assertIsInstance(result["segments"], list)
        self.assertGreater(len(result["segments"]), 0)
        for seg in result["segments"]:
            self.assertIn("start", seg)
            self.assertIn("end", seg)
            self.assertIn("text", seg)

        source_words = {w.strip(".,!?").lower() for w in source_text.split()}
        transcribed_words = {w.strip(".,!?").lower() for w in result["text"].split()}
        matched = source_words & transcribed_words
        self.assertGreaterEqual(
            len(matched) / len(source_words), 0.5,
            f"less than half of words matched: source={source_words} transcribed={transcribed_words}",
        )


class BrowserRenderAdapterTests(unittest.TestCase):
    def test_raises_clean_error_when_package_missing(self):
        if HAS_PLAYWRIGHT:
            self.skipTest("playwright is installed; missing-package path not reachable here")
        adapter = BrowserRenderAdapter()
        with self.assertRaises(ProviderUnavailableError):
            adapter.render_html("<html></html>", "/tmp/should-not-exist.png")

    @unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed")
    def test_render_html_string_produces_real_png(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-render-"))
        out_png = tmp / "shot.png"
        adapter = BrowserRenderAdapter()
        try:
            result = adapter.render_html(
                "<html><body style='background:#123456'><h1>clipme</h1></body></html>",
                out_png,
                width=640,
                height=360,
            )
        except ProviderUnavailableError as exc:
            self.skipTest(f"chromium not installed for playwright: {exc}")
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "playwright_chromium")
        self.assertTrue(out_png.exists())
        self.assertGreater(out_png.stat().st_size, 0)

    @unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed")
    def test_render_html_file_produces_real_png(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-render-file-"))
        html_path = tmp / "page.html"
        html_path.write_text("<html><body><p>from file</p></body></html>")
        out_png = tmp / "shot.png"
        adapter = BrowserRenderAdapter()
        try:
            result = adapter.render_html(html_path, out_png)
        except ProviderUnavailableError as exc:
            self.skipTest(f"chromium not installed for playwright: {exc}")
        self.assertTrue(result["executed"])
        self.assertTrue(out_png.exists())
        self.assertGreater(out_png.stat().st_size, 0)


class PiperTTSAdapterThaiTests(unittest.TestCase):
    @unittest.skipUnless(
        HAS_PIPER_TH_MODEL,
        "piper-tts + th_TH-mms_female-medium model not installed under models/piper/",
    )
    def test_generate_voice_thai_produces_real_wav(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-piper-th-"))
        out_path = tmp / "voice_th.wav"
        adapter = PiperTTSAdapter()
        result = adapter.generate_voice(
            THAI_TEST_SENTENCE,
            out_path,
            voice="th_TH-mms_female-medium",
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "piper_tts")
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        if HAS_FFPROBE:
            self.assertIsNotNone(result["duration_s"])
            self.assertGreater(result["duration_s"], 0.5)


class MMSTTSAdapterTests(unittest.TestCase):
    def test_raises_clean_error_when_deps_missing(self):
        if HAS_MMS_TTS:
            self.skipTest("transformers/torch/soundfile installed; missing-deps path not reachable here")
        adapter = MMSTTSAdapter()
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_voice(THAI_TEST_SENTENCE, "/tmp/should-not-exist.wav")

    @unittest.skipUnless(
        HAS_MMS_TTS,
        "transformers, torch and soundfile all required for facebook/mms-tts-tha",
    )
    def test_generate_voice_produces_real_wav(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-mms-tts-"))
        out_path = tmp / "voice_mms.wav"
        adapter = MMSTTSAdapter()
        result = adapter.generate_voice(THAI_TEST_SENTENCE, out_path)
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "mms_tts")
        self.assertEqual(result["model"], "facebook/mms-tts-tha")
        self.assertEqual(result["license"], "CC-BY-NC-4.0")
        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        if HAS_FFPROBE:
            self.assertIsNotNone(result["duration_s"])
            self.assertGreater(result["duration_s"], 0.5)


if __name__ == "__main__":
    unittest.main()
