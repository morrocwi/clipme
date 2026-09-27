"""Free/local text-generation provider adapters.

Worker A's slice of the free-local-providers work: registers the
``generate_text`` capability against local/free backends only (Ollama,
Claude CLI) — no paid API keys, no new hard dependency on `core/`.

Matches `core/providers.py`'s discipline:
- No printing, no `sys.exit`. Failures raise `core.providers.ProviderUnavailableError`
  (re-exported here for convenience) instead of failing deep inside a call.
- Heavy/optional imports (``urllib``, ``subprocess``, ``json``) are stdlib
  and cheap, but are still imported lazily inside methods so a missing
  external tool never breaks module import on CI.
- Adapters never fabricate output: on any failure they raise rather than
  returning a made-up "executed": True result.
- This module owns its own `register_defaults(registry)` entry point and
  never edits `core/providers.py`.
"""
from __future__ import annotations

import shutil
from typing import Any

from .providers import ProviderUnavailableError


# --------------------------------------------------------------------------- #
# Ollama-backed text adapter
# --------------------------------------------------------------------------- #

class OllamaTextAdapter:
    """Implements the "generate_text" capability via a local Ollama server.

    Uses `urllib` only (stdlib) so no new dependency is added. Availability
    is a cheap `GET /api/tags` call confirming the server responds AND the
    requested model is actually pulled — never assumed from the server
    merely being reachable.
    """

    def __init__(self, model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _list_models(self, timeout: float = 3.0) -> list[str]:
        import json
        import urllib.request

        url = f"{self.base_url}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderUnavailableError(f"ollama not reachable at {url}: {exc}") from exc
        return [m.get("name", "") for m in data.get("models", [])]

    def is_available(self) -> bool:
        try:
            names = self._list_models()
        except ProviderUnavailableError:
            return False
        return any(name == self.model or name.startswith(f"{self.model}:") or name.split(":")[0] == self.model.split(":")[0] for name in names)

    def _check_available(self) -> None:
        if not self.is_available():
            raise ProviderUnavailableError(
                f"ollama model '{self.model}' not available at {self.base_url} "
                "(server unreachable or model not pulled)"
            )

    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self._check_available()

        import json
        import urllib.request

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        payload.update({k: v for k, v in kwargs.items() if k not in ("model", "prompt", "stream")})
        body = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/api/generate"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        timeout = kwargs.get("timeout", 60.0)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderUnavailableError(f"ollama generate request failed: {exc}") from exc

        return {
            "executed": True,
            "provider": "ollama",
            "model": self.model,
            "text": data.get("response", ""),
        }


# --------------------------------------------------------------------------- #
# Claude CLI-backed text adapter
# --------------------------------------------------------------------------- #

class ClaudeCLITextAdapter:
    """Implements the "generate_text" capability by shelling out to the
    `claude` CLI in one-shot print mode. Availability is a cheap
    `shutil.which("claude")` check — never assumed from PATH alone at
    generate-time, since the binary could vanish between checks.
    """

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def _check_available(self) -> None:
        if not self.is_available():
            raise ProviderUnavailableError("claude CLI not found on PATH")

    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self._check_available()

        import subprocess

        timeout = kwargs.get("timeout", self.timeout)
        cmd = ["claude", "-p", prompt, "--output-format", "text"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except Exception as exc:
            raise ProviderUnavailableError(f"claude CLI invocation failed: {exc}") from exc

        if result.returncode != 0:
            raise ProviderUnavailableError(
                f"claude CLI exited {result.returncode}: {result.stderr.strip()}"
            )

        return {
            "executed": True,
            "provider": "claude_cli",
            "model": "claude-cli",
            "text": result.stdout.strip(),
        }


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

def register_defaults(registry: Any) -> None:
    """Registers the free/local text adapters on `registry`.

    Registers "generate_text" as the first available of [ollama, claude_cli]
    (falls back to the ollama adapter, unchecked, if neither is available —
    calling it will then raise `ProviderUnavailableError` at call time,
    which is correct: no provider means no silent fabrication). Also
    registers each backend explicitly under its own capability name so a
    caller can pick one deliberately.
    """
    ollama = OllamaTextAdapter()
    claude_cli = ClaudeCLITextAdapter()

    registry.register("generate_text:ollama", ollama)
    registry.register("generate_text:claude_cli", claude_cli)

    if ollama.is_available():
        registry.register("generate_text", ollama)
    elif claude_cli.is_available():
        registry.register("generate_text", claude_cli)
    else:
        registry.register("generate_text", ollama)
