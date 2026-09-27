# Free/local providers

Extension modules over `core/providers.py`'s capability-based `ProviderRegistry`
that add free/local backends for real capabilities. Each module owns its own
`register_defaults(registry)` entry point and never edits `core/providers.py`
itself. An adapter never fabricates output: it checks availability cheaply
(binary on PATH / import / a lightweight HTTP ping) and raises
`ProviderUnavailableError` instead of failing deep inside a call, or
returning a made-up "executed": True result.

- `core/providers_text.py` — text generation (this section, below).
- `core/providers_media.py` — media-capability adapters (see that module's
  own section in this file).

## Text generation (`core/providers_text.py`)

Registers the `generate_text` capability against local/free backends only —
no paid API keys, no new hard dependency added to `core/`.

| Adapter | Capability name(s) | Availability check | Backend |
|---|---|---|---|
| `OllamaTextAdapter` | `generate_text`, `generate_text:ollama` | `GET /api/tags` on the local Ollama server succeeds AND the requested model is listed | Local Ollama server (default model `qwen2.5:3b`, `http://localhost:11434`) |
| `ClaudeCLITextAdapter` | `generate_text`, `generate_text:claude_cli` | `shutil.which("claude")` | `claude -p <prompt> --output-format text` subprocess, with a timeout |
| `GeminiCLITextAdapter` | `generate_text`, `generate_text:gemini_cli` | `shutil.which("gemini")` | `gemini -p <prompt>` subprocess, with a timeout |
| `CodexCLITextAdapter` | `generate_text`, `generate_text:codex_cli` | `shutil.which("codex")` | `codex exec --sandbox read-only <prompt>` subprocess, with a timeout |

`register_defaults(registry)` registers `generate_text` as the first
available of `[ollama, claude_cli, gemini_cli, codex_cli]` (falling back to
the Ollama adapter, unchecked, if none is available — calling it then
raises `ProviderUnavailableError` at call time rather than silently
fabricating a response). It also registers each backend explicitly under
its own `generate_text:<backend>` capability name so a caller can pick a
specific backend instead of the first-available default.

All four adapters import their heavy/optional pieces (`urllib`, `json`,
`subprocess`) lazily inside methods, so importing `core/providers_text.py`
never fails on a CI machine that lacks any of Ollama, `claude`, `gemini`,
or `codex`.

**Account-login only, no API keys.** `ClaudeCLITextAdapter`,
`GeminiCLITextAdapter`, and `CodexCLITextAdapter` all shell out to a CLI
binary and rely entirely on that CLI's own logged-in account/session (OAuth
/ Code Assist for `gemini`, the account session for `codex`). None of the
three adapters reads, sets, or requires an API key or an environment
variable such as `GEMINI_API_KEY`. If the account session is missing,
expired, or ineligible, the underlying CLI process itself fails and the
adapter surfaces that as `ProviderUnavailableError`.

Known account-state caveat (this machine, verified 2026-09-27): `gemini
--version` reports `0.46.0` and the binary is on PATH, but neither the
default (no-env) invocation nor `GOOGLE_GENAI_USE_GCA=true` produces a
working session — the no-env call fails with the standard "Please set an
Auth method..." message, and the GCA path fails with
`IneligibleTierError: This client is no longer supported for Gemini Code
Assist for individuals` (the CLI is asking for a migration to Antigravity).
`~/.gemini/settings.json` has no `selectedAuthType` and no API-key env vars
are set anywhere in the environment, consistent with "never configured /
no longer eligible" rather than a code bug in the adapter — Gemini's
real-call test is expected to skip on this machine until that account is
fixed. `codex exec` initially failed when probed from `$HOME` (not a git
repo) with "Not inside a trusted directory and --skip-git-repo-check was
not specified"; run from inside this repo (a trusted git checkout, as
`tests/test_providers_text.py` does), `codex exec --sandbox read-only`
succeeds using the account's already-logged-in session — verified with a
real call returning `"OK"`. Both adapters are still added and registered
per the project's account-login policy; their real-call tests are written
to skip (not fail) when the CLI itself reports the session/environment as
unusable, since that reflects account/trust state, not the adapter's
correctness.

Tests: `tests/test_providers_text.py`. Model/network-dependent assertions
are guarded with `unittest.skipUnless(<availability check>)` so CI without
Ollama/`claude`/`gemini`/`codex` still passes; when a tool IS present, its
real-call test attempts a live generate call and additionally skips (rather
than fails) if that live call raises `ProviderUnavailableError` — an
account/session/trust-state issue distinct from binary presence.

## Media adapters (`core/providers_media.py`)

Registers `generate_voice` (TTS), `transcribe` (STT), and `render_html`
(headless-browser screenshot) — all free/no-API-key, all optional
(`requirements-providers.txt`, not part of core `requirements.txt`).

| Adapter | Capability | Availability check | Backend |
|---|---|---|---|
| `EdgeTTSAdapter` | `generate_voice`, `generate_voice:edge_tts` | `import edge_tts` succeeds (network is still required at call time; a network failure at synthesis is also raised as `ProviderUnavailableError`, not a raw exception) | Free MS Edge cloud TTS voices, e.g. `th-TH-PremwadeeNeural` (default), `en-US-AriaNeural` |
| `PiperTTSAdapter` | `generate_voice:piper_tts` | `import piper` succeeds AND `models/piper/<voice>.onnx`(`.json`) exists | Fully offline neural TTS; this adapter never downloads voice models itself — only English (`en_US-lessac-medium`) was confirmed present on this machine as of the install-phase check, no Thai voice was found in `rhasspy/piper-voices` at that time |
| `FasterWhisperSTTAdapter` | `transcribe` | `import faster_whisper` succeeds | Offline Whisper STT, CPU `int8`; the model is loaded lazily on first `transcribe()` call and cached on the instance (never more than one loaded model per instance, for this machine's frugal-RAM constraint) |
| `BrowserRenderAdapter` | `render_html` | `import playwright.sync_api` succeeds (a missing Chromium browser binary is also raised as `ProviderUnavailableError` at render time, not a raw Playwright exception) | Headless Chromium via `playwright`; accepts either an HTML file path (`file://` navigation) or a raw HTML string (`page.set_content`) |

`register_defaults(registry)` registers `generate_voice` -> `EdgeTTSAdapter`
(always installable, no local model download required), `transcribe` ->
`FasterWhisperSTTAdapter`, and `render_html` -> `BrowserRenderAdapter`. It
also registers each `generate_voice` backend explicitly under its own
capability name — `generate_voice:edge_tts` and `generate_voice:piper_tts`
— mirroring `generate_text:<backend>` in `core/providers_text.py`, so a
caller can pick Piper's fully offline path deliberately (once a voice model
is downloaded locally) via the registry instead of importing
`PiperTTSAdapter` directly.

All four heavy imports (`edge_tts`, `piper`, `faster_whisper`,
`playwright`) are lazy, inside each method — importing
`core/providers_media.py` never fails on a CI machine that lacks
`requirements-providers.txt` or `playwright install chromium`.

Tests: `tests/test_providers_media.py`. Package-missing paths are guarded
with `unittest.skipUnless(<availability check>)`. When the tools ARE
present, the suite runs real integration assertions: a live `edge-tts`
synthesis to a real audio file (duration checked via `ffprobe` when
available), a live `piper-tts` synthesis to a real `.wav` (same duration
check), a live `playwright` Chromium render to a real `.png` from both a
raw HTML string and an HTML file, and a real TTS-to-STT round trip
(`edge-tts` -> `faster-whisper`) asserting at least 50% of the source
sentence's words reappear (case-insensitively) in the transcript.
