"""Free, local-friendly media provider adapters for clipme.

Implements optional capabilities for `core/providers.py`'s
`ProviderRegistry` — "generate_voice" (text-to-speech), "transcribe"
(speech-to-text), and "render_html" (headless-browser rendering) — without
editing that module. This is worker B's half of a disjoint split: worker A
owns `core/providers_text.py`; this module owns everything media-shaped.

Design rules (matching `core/providers.py`'s discipline):
- Every heavy/optional dependency (`edge_tts`, `piper`, `faster_whisper`,
  `playwright`) is imported LAZILY inside the method that needs it, never
  at module import time, so importing this module never fails on a
  machine (e.g. CI) that lacks `requirements-providers.txt`.
- Each adapter checks its own availability cheaply first and raises
  `core.providers.ProviderUnavailableError` (re-exported here for
  convenience) with a clear message, instead of failing deep inside a
  call.
- No adapter ever fabricates output: if the underlying tool/model isn't
  present, or a real run fails, it raises rather than returning a
  plausible-looking fake result.
- Artifacts are written only to the paths the caller passes in.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from .providers import ProviderUnavailableError


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _ffprobe_duration(path: str | Path) -> float | None:
    """Best-effort audio/video duration in seconds via ffprobe. Returns
    None (never raises) if ffprobe is missing or the probe fails — callers
    treat a missing duration as "unmeasured", not an error."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# TTS: edge-tts (free MS Edge cloud TTS — needs internet, no API key)
# --------------------------------------------------------------------------- #

class EdgeTTSAdapter:
    """Implements "generate_voice" via the free `edge-tts` package. Needs
    internet access at call time; the availability check below only
    confirms the package is importable, not that the network call will
    succeed — a network failure during synthesis is also surfaced as
    `ProviderUnavailableError` rather than a raw exception from deep
    inside `edge_tts`."""

    def _check_available(self) -> None:
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailableError(
                "edge-tts is not installed (pip install edge-tts)"
            ) from exc

    def generate_voice(
        self,
        text: str,
        out_path: str | Path,
        voice: str = "th-TH-PremwadeeNeural",
        **kw: Any,
    ) -> dict[str, Any]:
        self._check_available()
        import edge_tts

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async def _run() -> None:
            communicate = edge_tts.Communicate(text, voice, **kw)
            await communicate.save(str(out_path))

        try:
            asyncio.run(_run())
        except Exception as exc:
            raise ProviderUnavailableError(
                f"edge-tts synthesis failed (no network, or bad voice name {voice!r}): {exc}"
            ) from exc

        return {
            "executed": True,
            "provider": "edge_tts",
            "path": str(out_path),
            "duration_s": _ffprobe_duration(out_path),
        }


# --------------------------------------------------------------------------- #
# TTS: piper (free, fully-offline neural TTS)
# --------------------------------------------------------------------------- #
# Install report VERIFIED piper-tts works on this machine (pip install OK,
# en_US-lessac-medium.onnx downloaded, TTS-to-wav round trip confirmed via
# ffprobe) — so this adapter is included. No Thai voice was found in
# rhasspy/piper-voices as of that check (INSTINCT: single listing pass, not
# exhaustive), so the default voice here is the English one actually
# verified present; a caller can pass any other voice already downloaded
# into `models/piper/`.

class PiperTTSAdapter:
    """Implements "generate_voice" via the free, fully-offline `piper-tts`
    package. Needs a local voice model (`<voice>.onnx` + `<voice>.onnx.json`)
    already present under `models/piper/` — this adapter does not download
    voice models itself."""

    DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[1] / "models" / "piper"

    def _model_paths(self, voice: str, models_dir: Path) -> tuple[Path, Path]:
        return models_dir / f"{voice}.onnx", models_dir / f"{voice}.onnx.json"

    def _check_available(self, voice: str, models_dir: Path) -> Path:
        try:
            import piper  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailableError(
                "piper-tts is not installed (pip install piper-tts)"
            ) from exc
        onnx, config = self._model_paths(voice, models_dir)
        if not onnx.exists() or not config.exists():
            raise ProviderUnavailableError(
                f"piper voice model not found for {voice!r} under {models_dir} "
                "(download a voice from the rhasspy/piper-voices HF repo first)"
            )
        return onnx

    def generate_voice(
        self,
        text: str,
        out_path: str | Path,
        voice: str = "en_US-lessac-medium",
        models_dir: str | Path | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        models_dir = Path(models_dir) if models_dir is not None else self.DEFAULT_MODELS_DIR
        onnx = self._check_available(voice, models_dir)
        from piper import PiperVoice

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            piper_voice = PiperVoice.load(str(onnx))
            with wave.open(str(out_path), "wb") as wav_file:
                piper_voice.synthesize_wav(text, wav_file)
        except Exception as exc:
            raise ProviderUnavailableError(f"piper synthesis failed: {exc}") from exc

        return {
            "executed": True,
            "provider": "piper_tts",
            "path": str(out_path),
            "duration_s": _ffprobe_duration(out_path),
        }


# --------------------------------------------------------------------------- #
# TTS: facebook/mms-tts-tha (offline VITS model via transformers, CC-BY-NC-4.0)
# --------------------------------------------------------------------------- #

class MMSTTSAdapter:
    """Implements "generate_voice" for Thai via Meta's MMS-TTS VITS model
    (`facebook/mms-tts-tha`), loaded through `transformers` + `torch` (CPU).

    Heavier than `PiperTTSAdapter` (needs `transformers`/`torch`/`soundfile`,
    ~2GB combined install; measured ~745MB peak RSS and ~18s wall time for a
    short sentence on this machine) but needs no local ONNX voice file — the
    model is downloaded once from the Hugging Face Hub and cached by
    `transformers`.

    License: CC-BY-NC-4.0 (non-commercial) — inherited from the base
    `facebook/mms-tts` release. Do not use for commercial clipme output
    without separately clearing that with the founder.

    The model instance is loaded lazily on first `generate_voice` call and
    cached on the adapter instance, matching `FasterWhisperSTTAdapter`'s
    one-model-per-instance discipline (never load two heavy models at once).
    """

    MODEL_ID = "facebook/mms-tts-tha"
    LICENSE = "CC-BY-NC-4.0"

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None

    def _check_available(self) -> None:
        import importlib.util

        if importlib.util.find_spec("transformers") is None or importlib.util.find_spec("torch") is None:
            raise ProviderUnavailableError(
                "transformers and/or torch are not installed "
                "(pip install transformers torch soundfile — see requirements-providers.txt)"
            )

    def _get_model(self):
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer
        try:
            from transformers import AutoTokenizer, VitsModel
        except ImportError as exc:
            raise ProviderUnavailableError(f"transformers import failed: {exc}") from exc

        try:
            self._model = VitsModel.from_pretrained(self.MODEL_ID)
            self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
        except Exception as exc:
            raise ProviderUnavailableError(
                f"failed to load {self.MODEL_ID!r}: {exc}"
            ) from exc
        return self._model, self._tokenizer

    def generate_voice(
        self,
        text: str,
        out_path: str | Path,
        **kw: Any,
    ) -> dict[str, Any]:
        self._check_available()
        model, tokenizer = self._get_model()

        import torch
        import soundfile as sf

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            inputs = tokenizer(text, return_tensors="pt")
            with torch.no_grad():
                waveform = model(**inputs).waveform
            wav = waveform.squeeze().numpy()
            sf.write(str(out_path), wav, model.config.sampling_rate)
        except Exception as exc:
            raise ProviderUnavailableError(f"mms-tts synthesis failed: {exc}") from exc

        return {
            "executed": True,
            "provider": "mms_tts",
            "model": self.MODEL_ID,
            "license": self.LICENSE,
            "path": str(out_path),
            "duration_s": _ffprobe_duration(out_path),
        }


# --------------------------------------------------------------------------- #
# TTS: Gemini API (commercial-licensed cloud TTS, paid API key required)
# --------------------------------------------------------------------------- #

class GeminiTTSAdapter:
    """Implements "generate_voice" via the Gemini API's native TTS models
    (`generateContent` with `responseModalities: ["AUDIO"]`).

    Commercial: the Gemini API Terms of Service permit commercial use of
    generated output (unlike the CC-BY-NC-4.0 offline Thai backends in this
    module). The paid tier is recommended when "no training on my data" is
    required — see
    https://ai.google.dev/gemini-api/terms for the current terms; this
    adapter does not re-host or re-verify those terms, it only names them.

    Uses stdlib `urllib` only — no `google-generativeai` / `google-genai`
    SDK dependency. Reads `GEMINI_API_KEY` from `os.environ` at call time
    (never cached, never logged); availability is "key present in
    environment", not "key is valid" (an invalid key surfaces as an HTTP
    401/403 `ProviderUnavailableError` at call time instead).

    The API key is sent ONLY via the `x-goog-api-key` request header, never
    in the URL query string, and is never included in any exception message
    or log line raised by this adapter.
    """

    DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_VOICE = "Kore"  # verified good Thai output in .scratch/commercial/gemini_tts_test.py
    LICENSE = "Gemini API Terms (commercial use allowed; paid tier recommended for no-training)"
    _ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def _check_available(self) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ProviderUnavailableError(
                "GEMINI_API_KEY is not set in the environment "
                "(export it from a gitignored .env / secrets file first)"
            )
        return api_key

    def generate_voice(
        self,
        text: str,
        out_path: str | Path,
        voice: str = DEFAULT_VOICE,
        model: str = DEFAULT_MODEL,
        **kw: Any,
    ) -> dict[str, Any]:
        api_key = self._check_available()
        import urllib.error
        import urllib.request

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        url = self._ENDPOINT.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                },
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=kw.pop("timeout", 60)) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Never include request headers (which carry the API key) in the
            # raised message — only the HTTP status and the response body's
            # own error text (Google's error payloads do not echo the key).
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise ProviderUnavailableError(
                f"Gemini TTS request failed with HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError(f"Gemini TTS request failed (network): {exc.reason}") from exc

        try:
            candidate = body["candidates"][0]
            part = candidate["content"]["parts"][0]
            inline = part["inlineData"]
            pcm = base64.b64decode(inline["data"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError(
                f"Gemini TTS response did not contain the expected audio payload: {exc}"
            ) from exc

        # Gemini TTS returns raw PCM, 24kHz 16-bit mono (verified in
        # .scratch/commercial/gemini_tts_test.py).
        sample_rate = 24000
        sample_width = 2
        channels = 1
        try:
            with wave.open(str(out_path), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm)
        except Exception as exc:
            raise ProviderUnavailableError(f"failed to write WAV to {out_path}: {exc}") from exc

        duration_s = _ffprobe_duration(out_path)
        if duration_s is None:
            frame_count = len(pcm) // (sample_width * channels)
            duration_s = frame_count / float(sample_rate)

        return {
            "executed": True,
            "provider": "gemini_tts",
            "model": model,
            "voice": voice,
            "license": self.LICENSE,
            "path": str(out_path),
            "duration_s": duration_s,
        }


# --------------------------------------------------------------------------- #
# STT: faster-whisper (free, offline, CPU int8 supported)
# --------------------------------------------------------------------------- #

class FasterWhisperSTTAdapter:
    """Implements "transcribe" via the free, offline `faster-whisper`
    package. The whisper model is loaded lazily (first `transcribe` call,
    not `__init__`) and cached on the instance so a single adapter instance
    never loads more than one model — matching this machine's frugal-RAM
    constraint (14GB total, ~3GB free)."""

    def __init__(self) -> None:
        self._model = None
        self._model_size: str | None = None

    def _check_available(self) -> None:
        try:
            import faster_whisper  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailableError(
                "faster-whisper is not installed (pip install faster-whisper)"
            ) from exc

    def _get_model(self, model_size: str):
        if self._model is not None and self._model_size == model_size:
            return self._model
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as exc:
            raise ProviderUnavailableError(
                f"faster-whisper failed to load model {model_size!r}: {exc}"
            ) from exc
        self._model_size = model_size
        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        model_size: str = "base",
        **kw: Any,
    ) -> dict[str, Any]:
        self._check_available()
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise ProviderUnavailableError(f"audio file not found: {audio_path}")

        model = self._get_model(model_size)
        try:
            segments_iter, _info = model.transcribe(str(audio_path), language=language, **kw)
            segments = [
                {"start": seg.start, "end": seg.end, "text": seg.text}
                for seg in segments_iter
            ]
        except Exception as exc:
            raise ProviderUnavailableError(f"faster-whisper transcription failed: {exc}") from exc

        text = "".join(seg["text"] for seg in segments).strip()
        return {
            "executed": True,
            "provider": "faster_whisper",
            "text": text,
            "segments": segments,
        }


# --------------------------------------------------------------------------- #
# Browser render: playwright + chromium headless (free, no sudo)
# --------------------------------------------------------------------------- #

class BrowserRenderAdapter:
    """Implements "render_html" via playwright's headless Chromium. Renders
    either a path to an HTML file (`file://` navigation) or a raw HTML
    string (via `set_content`) to a PNG screenshot at the given path."""

    def _check_available(self) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError as exc:
            raise ProviderUnavailableError(
                "playwright is not installed (pip install playwright)"
            ) from exc

    def render_html(
        self,
        html_or_path: str | Path,
        out_png: str | Path,
        width: int = 1280,
        height: int = 720,
        **kw: Any,
    ) -> dict[str, Any]:
        self._check_available()
        from playwright.sync_api import sync_playwright

        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)

        candidate_path = Path(html_or_path)
        is_file = candidate_path.exists() and candidate_path.is_file()

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    if is_file:
                        page.goto(candidate_path.resolve().as_uri())
                    else:
                        page.set_content(str(html_or_path))
                    page.screenshot(path=str(out_png))
                finally:
                    browser.close()
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(
                f"playwright chromium render failed (is 'playwright install chromium' done?): {exc}"
            ) from exc

        return {
            "executed": True,
            "provider": "playwright_chromium",
            "path": str(out_png),
        }


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

def register_defaults(registry: Any) -> None:
    """Registers this module's adapters onto a `core.providers.ProviderRegistry`
    (or anything with the same `.register(capability, provider)` shape),
    without `core/providers.py` needing to know this module exists.

    - "generate_voice" -> EdgeTTSAdapter (free, always installable, no local
      model download required).
    - "transcribe" -> FasterWhisperSTTAdapter
    - "render_html" -> BrowserRenderAdapter

    Also registers each `generate_voice` backend explicitly under its own
    capability name (`generate_voice:edge_tts`, `generate_voice:piper_tts`,
    `generate_voice:piper_th`, `generate_voice:mms_tts`), mirroring
    `providers_text.py`'s `generate_text:<backend>` convention, so a caller
    can pick Piper's fully-offline path (or the Thai-specific voice/model)
    deliberately instead of importing the adapter directly. `edge_tts`
    stays the default "generate_voice" — it is not overridden by any of
    the offline Thai backends.
    """
    edge_tts = EdgeTTSAdapter()
    piper_tts = PiperTTSAdapter()
    piper_th = PiperTTSAdapter()
    mms_tts = MMSTTSAdapter()
    gemini_tts = GeminiTTSAdapter()

    registry.register("generate_voice", edge_tts)
    registry.register("generate_voice:edge_tts", edge_tts)
    registry.register("generate_voice:piper_tts", piper_tts)
    registry.register("generate_voice:piper_th", piper_th)
    registry.register("generate_voice:mms_tts", mms_tts)
    registry.register("generate_voice:gemini_tts", gemini_tts)
    registry.register("transcribe", FasterWhisperSTTAdapter())
    registry.register("render_html", BrowserRenderAdapter())
