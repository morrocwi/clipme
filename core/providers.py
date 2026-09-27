"""clipme provider interface — a small, capability-based registry.

This is the extension point for real external AI/tool execution, sitting
above `core/orchestrator.py`'s `TaskExecutor` Protocol rather than replacing
it. Kept deliberately small: a dict-backed registry, not a plugin-loading
framework.

Design rules for this module, matching `core/service.py`'s discipline:
- No new dependency is added to `core/` — the one real adapter
  (`FFmpegRenderAdapter`) reuses `core.service.assemble_project`'s existing
  ffmpeg invocation rather than re-implementing it.
- No printing, no `sys.exit`. Errors are raised as `ProviderError` subclasses.
"""
from __future__ import annotations

import shutil
from typing import Any, Protocol

from . import service


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class ProviderError(Exception):
    """Base class for every error this module raises."""


class CapabilityNotFoundError(ProviderError):
    """No provider is registered for the requested capability."""


# --------------------------------------------------------------------------- #
# Capability protocols
# --------------------------------------------------------------------------- #

class RenderProvider(Protocol):
    def render(self, spec: dict[str, Any]) -> dict[str, Any]: ...


class TextProvider(Protocol):
    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

class ProviderRegistry:
    """Maps a capability name (e.g. "render", "text") to a provider instance.

    Deliberately minimal: no auto-discovery/plugin loading, just an
    in-memory dict a caller populates explicitly."""

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}

    def register(self, capability: str, provider: Any) -> None:
        self._providers[capability] = provider

    def get(self, capability: str) -> Any:
        try:
            return self._providers[capability]
        except KeyError as exc:
            raise CapabilityNotFoundError(f"no provider registered for capability: {capability}") from exc

    def capabilities(self) -> list[str]:
        return sorted(self._providers)


# --------------------------------------------------------------------------- #
# Real adapter: ffmpeg-backed render
# --------------------------------------------------------------------------- #

class FFmpegRenderAdapter:
    """Implements the "render" capability by wrapping the existing
    `core.service.assemble_project` ffmpeg invocation. Does not duplicate
    ffmpeg command-building logic.

    `spec` is expected to carry the same arguments `assemble_project` takes:
    {"project_dir": ..., "manifest_rel": ... (optional), "output_rel": ... (optional)}
    """

    def render(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not shutil.which("ffmpeg"):
            raise service.BinaryNotFoundError("ffmpeg not found in PATH")
        project_dir = spec["project_dir"]
        kwargs: dict[str, Any] = {}
        if "manifest_rel" in spec:
            kwargs["manifest_rel"] = spec["manifest_rel"]
        if "output_rel" in spec:
            kwargs["output_rel"] = spec["output_rel"]
        result = service.assemble_project(project_dir, **kwargs)
        return {"executed": True, "output": result["output"]}


# --------------------------------------------------------------------------- #
# Dry-run adapter: text
# --------------------------------------------------------------------------- #

class EchoTextAdapter:
    """Implements the "text" capability WITHOUT calling any real LLM. Always
    returns a result whose `executed: False` field makes clear nothing
    downstream should mistake this for real generated content — mirrors what
    `tests/test_kernel.py`'s `EchoExecutor` already does for task completion,
    scoped here to the capability-based registry instead of the
    `TaskExecutor` Protocol directly."""

    def generate_text(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "executed": False,
            "note": "dry-run echo adapter, no model was called",
            "echo": prompt,
        }
