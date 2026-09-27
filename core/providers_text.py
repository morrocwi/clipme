"""Free/local text-generation provider adapters.

Worker A's slice of the free-local-providers work: registers the
``generate_text`` capability against local/free backends only (Ollama,
Claude CLI, Gemini CLI, Codex CLI) — no paid API keys, no new hard
dependency on `core/`. The CLI adapters (Claude, Gemini, Codex) all
authenticate via the CLI's own logged-in account/session; none of them
reads or requires an API key.

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
# Gemini CLI-backed text adapter
# --------------------------------------------------------------------------- #

class GeminiCLITextAdapter:
    """Implements the "generate_text" capability by shelling out to the
    `gemini` CLI in one-shot print mode. Availability is a cheap
    `shutil.which("gemini")` check — never assumed from PATH alone at
    generate-time, since the binary could vanish between checks.

    Authenticates via whatever the CLI's own logged-in account/session is
    configured to use (OAuth / Google Code Assist) — this adapter never
    sets, reads, or requires an API key. If the account is not authenticated
    (or is otherwise ineligible for the CLI's current tier), the `gemini`
    process itself fails and this adapter surfaces that as
    `ProviderUnavailableError` rather than papering over it.
    """

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def _check_available(self) -> None:
        if not self.is_available():
            raise ProviderUnavailableError("gemini CLI not found on PATH")

    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self._check_available()

        import subprocess

        timeout = kwargs.get("timeout", self.timeout)
        cmd = ["gemini", "-p", prompt]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except Exception as exc:
            raise ProviderUnavailableError(f"gemini CLI invocation failed: {exc}") from exc

        if result.returncode != 0:
            raise ProviderUnavailableError(
                f"gemini CLI exited {result.returncode}: {result.stderr.strip()}"
            )

        text = result.stdout.strip()
        if not text:
            raise ProviderUnavailableError(
                f"gemini CLI returned no text (stderr: {result.stderr.strip()})"
            )

        return {
            "executed": True,
            "provider": "gemini_cli",
            "model": "gemini-cli",
            "text": text,
        }


# --------------------------------------------------------------------------- #
# Codex CLI-backed text adapter
# --------------------------------------------------------------------------- #

class CodexCLITextAdapter:
    """Implements the "generate_text" capability by shelling out to the
    `codex` CLI's non-interactive `exec` mode with a read-only sandbox.
    Availability is a cheap `shutil.which("codex")` check — never assumed
    from PATH alone at generate-time, since the binary could vanish between
    checks.

    Uses the account's default model (no `-m` flag) and authenticates via
    whatever the CLI's own logged-in session is configured to use — this
    adapter never sets, reads, or requires an API key. `codex exec` also
    requires running inside a trusted (git) directory; if the caller's
    working directory is not trusted, or the account session is not usable,
    the `codex` process itself fails and this adapter surfaces that as
    `ProviderUnavailableError` rather than papering over it.
    """

    def __init__(self, timeout: float = 180.0) -> None:
        self.timeout = timeout

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def _check_available(self) -> None:
        if not self.is_available():
            raise ProviderUnavailableError("codex CLI not found on PATH")

    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self._check_available()

        import subprocess

        timeout = kwargs.get("timeout", self.timeout)
        cmd = ["codex", "exec", "--sandbox", "read-only", prompt]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"codex CLI invocation failed: {exc}") from exc

        if result.returncode != 0:
            raise ProviderUnavailableError(
                f"codex CLI exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
            )

        text = result.stdout.strip()
        if not text:
            raise ProviderUnavailableError(
                f"codex CLI returned no text (stderr: {result.stderr.strip()})"
            )

        return {
            "executed": True,
            "provider": "codex_cli",
            "model": "codex-cli",
            "text": text,
        }


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

def register_defaults(registry: Any) -> None:
    """Registers the free/local text adapters on `registry`.

    Registers "generate_text" as the first available of
    [ollama, claude_cli, gemini_cli, codex_cli] (falls back to the ollama
    adapter, unchecked, if none is available — calling it will then raise
    `ProviderUnavailableError` at call time, which is correct: no provider
    means no silent fabrication). Also registers each backend explicitly
    under its own capability name so a caller can pick one deliberately.
    """
    ollama = OllamaTextAdapter()
    claude_cli = ClaudeCLITextAdapter()
    gemini_cli = GeminiCLITextAdapter()
    codex_cli = CodexCLITextAdapter()

    registry.register("generate_text:ollama", ollama)
    registry.register("generate_text:claude_cli", claude_cli)
    registry.register("generate_text:gemini_cli", gemini_cli)
    registry.register("generate_text:codex_cli", codex_cli)

    for adapter in (ollama, claude_cli, gemini_cli, codex_cli):
        if adapter.is_available():
            registry.register("generate_text", adapter)
            break
    else:
        registry.register("generate_text", ollama)
