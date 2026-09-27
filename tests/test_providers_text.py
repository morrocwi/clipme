from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.providers import ProviderRegistry
from core.providers_text import (
    ClaudeCLITextAdapter,
    CodexCLITextAdapter,
    GeminiCLITextAdapter,
    OllamaTextAdapter,
    ProviderUnavailableError,
    register_defaults,
)


def _ollama_model_available(model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434") -> bool:
    return OllamaTextAdapter(model=model, base_url=base_url).is_available()


class OllamaTextAdapterTests(unittest.TestCase):
    def test_unreachable_server_is_unavailable(self):
        adapter = OllamaTextAdapter(model="qwen2.5:3b", base_url="http://localhost:1")
        self.assertFalse(adapter.is_available())
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_text("hello")

    def test_missing_model_reported_unavailable(self):
        # Real server may or may not be reachable here; either way a model
        # name that (almost certainly) is not pulled must not be available.
        adapter = OllamaTextAdapter(model="definitely-not-a-real-model:latest")
        self.assertFalse(adapter.is_available())

    @unittest.skipUnless(_ollama_model_available(), "ollama server / qwen2.5:3b model not available")
    def test_real_ollama_generate(self):
        adapter = OllamaTextAdapter(model="qwen2.5:3b")
        result = adapter.generate_text("Reply with the single word OK", timeout=60)
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["model"], "qwen2.5:3b")
        self.assertIsInstance(result["text"], str)
        self.assertTrue(result["text"].strip())


class ClaudeCLITextAdapterTests(unittest.TestCase):
    def test_unavailable_when_binary_missing(self):
        adapter = ClaudeCLITextAdapter()
        if shutil.which("claude"):
            self.skipTest("claude CLI is on PATH; missing-binary path covered by construction only")
        self.assertFalse(adapter.is_available())
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_text("hello")

    @unittest.skipUnless(shutil.which("claude"), "claude CLI not on PATH")
    def test_real_claude_cli_generate(self):
        adapter = ClaudeCLITextAdapter(timeout=120)
        result = adapter.generate_text("Reply with the single word OK")
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "claude_cli")
        self.assertIsInstance(result["text"], str)
        self.assertTrue(result["text"].strip())


class GeminiCLITextAdapterTests(unittest.TestCase):
    def test_unavailable_when_binary_missing(self):
        adapter = GeminiCLITextAdapter()
        if shutil.which("gemini"):
            self.skipTest("gemini CLI is on PATH; missing-binary path covered by construction only")
        self.assertFalse(adapter.is_available())
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_text("hello")

    @unittest.skipUnless(shutil.which("gemini"), "gemini CLI not on PATH")
    def test_real_gemini_cli_generate(self):
        # Binary presence does not imply a usable account session (OAuth may
        # be unauthenticated, expired, or ineligible for the CLI's current
        # tier). Attempt the real call and skip — rather than fail — on a
        # `ProviderUnavailableError`, since that reflects this machine's
        # account/session state, not a bug in the adapter itself.
        adapter = GeminiCLITextAdapter(timeout=120)
        try:
            result = adapter.generate_text("Reply with the single word OK")
        except ProviderUnavailableError as exc:
            self.skipTest(f"gemini CLI account/session not usable: {exc}")
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "gemini_cli")
        self.assertIsInstance(result["text"], str)
        self.assertTrue(result["text"].strip())


class CodexCLITextAdapterTests(unittest.TestCase):
    def test_unavailable_when_binary_missing(self):
        adapter = CodexCLITextAdapter()
        if shutil.which("codex"):
            self.skipTest("codex CLI is on PATH; missing-binary path covered by construction only")
        self.assertFalse(adapter.is_available())
        with self.assertRaises(ProviderUnavailableError):
            adapter.generate_text("hello")

    @unittest.skipUnless(shutil.which("codex"), "codex CLI not on PATH")
    def test_real_codex_cli_generate(self):
        # Binary presence does not imply a usable account session or a
        # trusted-directory sandbox. Attempt the real call and skip — rather
        # than fail — on a `ProviderUnavailableError`, since that reflects
        # this machine's account/session/trust state, not a bug in the
        # adapter itself.
        adapter = CodexCLITextAdapter(timeout=180)
        try:
            result = adapter.generate_text("Reply with the single word OK")
        except ProviderUnavailableError as exc:
            self.skipTest(f"codex CLI account/session not usable: {exc}")
        self.assertTrue(result["executed"])
        self.assertEqual(result["provider"], "codex_cli")
        self.assertIsInstance(result["text"], str)
        self.assertTrue(result["text"].strip())


class RegisterDefaultsTests(unittest.TestCase):
    def test_registers_explicit_capabilities(self):
        registry = ProviderRegistry()
        register_defaults(registry)
        self.assertIn("generate_text", registry.capabilities())
        self.assertIn("generate_text:ollama", registry.capabilities())
        self.assertIn("generate_text:claude_cli", registry.capabilities())
        self.assertIn("generate_text:gemini_cli", registry.capabilities())
        self.assertIn("generate_text:codex_cli", registry.capabilities())
        self.assertIsInstance(registry.get("generate_text:ollama"), OllamaTextAdapter)
        self.assertIsInstance(registry.get("generate_text:claude_cli"), ClaudeCLITextAdapter)
        self.assertIsInstance(registry.get("generate_text:gemini_cli"), GeminiCLITextAdapter)
        self.assertIsInstance(registry.get("generate_text:codex_cli"), CodexCLITextAdapter)

    def test_default_prefers_first_available(self):
        registry = ProviderRegistry()
        register_defaults(registry)
        default = registry.get("generate_text")
        if _ollama_model_available():
            self.assertIsInstance(default, OllamaTextAdapter)
        elif shutil.which("claude"):
            self.assertIsInstance(default, ClaudeCLITextAdapter)
        elif shutil.which("codex"):
            self.assertIsInstance(default, CodexCLITextAdapter)
        elif shutil.which("gemini"):
            self.assertIsInstance(default, GeminiCLITextAdapter)


if __name__ == "__main__":
    unittest.main()
