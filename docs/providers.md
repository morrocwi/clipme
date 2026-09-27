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
available of `[ollama, claude_cli, codex_cli, gemini_cli]` (falling back to
the Ollama adapter, unchecked, if none is available — calling it then
raises `ProviderUnavailableError` at call time rather than silently
fabricating a response). It also registers each backend explicitly under
its own `generate_text:<backend>` capability name so a caller can pick a
specific backend instead of the first-available default.

Gemini is last in that fallback order, after Codex: if Codex can already do
the job it is preferred, since Codex authenticates via its own logged-in
CLI session while Gemini's auth (below) draws on paid API quota — Gemini is
only reached once Ollama, Claude CLI, and Codex CLI are all unavailable.

All four adapters import their heavy/optional pieces (`urllib`, `json`,
`subprocess`) lazily inside methods, so importing `core/providers_text.py`
never fails on a CI machine that lacks any of Ollama, `claude`, `gemini`,
or `codex`.

**Account-login for Claude/Codex; API-key env var for Gemini.**
`ClaudeCLITextAdapter` and `CodexCLITextAdapter` shell out to a CLI binary
and rely entirely on that CLI's own logged-in account/session. Neither
reads, sets, or requires an API key. If the account session is missing,
expired, or ineligible, the underlying CLI process itself fails and the
adapter surfaces that as `ProviderUnavailableError`.

`GeminiCLITextAdapter` is different: the `gemini` CLI's free/OAuth Code
Assist tier is not reliably usable on this machine (see below), so its
adapter instead relies on the standard `GEMINI_API_KEY` environment
variable that the `gemini` CLI itself reads. The adapter does not read,
set, inspect, or hardcode that key anywhere in its own code — it passes the
parent process's environment through to the `gemini` subprocess unchanged
(`subprocess.run(..., env=os.environ.copy())`) and lets the CLI pick up
whatever auth is already in the caller's environment. To use it: export
`GEMINI_API_KEY` from a secrets file outside the repo (chmod 600); never
commit it. If the key is absent or invalid, the `gemini` CLI process itself
fails and the adapter surfaces that as `ProviderUnavailableError`, same as
the other CLI adapters.

Known account-state note (this machine, verified 2026-09-27): `gemini
--version` reports `0.46.0` and the binary is on PATH; the OAuth/Code
Assist path (`GOOGLE_GENAI_USE_GCA=true`, no key) fails with
`IneligibleTierError: This client is no longer supported for Gemini Code
Assist for individuals` (the CLI is asking for a migration to Antigravity),
so that path is not usable here — but with `GEMINI_API_KEY` exported into
the environment (from `~/.config/araya/gemini.env`, never printed or
committed) the same CLI succeeds and `test_real_gemini_cli_generate` passes
with a real call. `codex exec` initially failed when probed from `$HOME`
(not a git repo) with "Not inside a trusted directory and
--skip-git-repo-check was not specified"; run from inside this repo (a
trusted git checkout, as `tests/test_providers_text.py` does), `codex exec
--sandbox read-only` succeeds using the account's already-logged-in
session — verified with a real call returning `"OK"`. Both adapters are
still added and registered; their real-call tests are written to skip (not
fail) when the CLI itself reports the session/environment as unusable,
since that reflects account/key/trust state, not the adapter's
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
| `GeminiTTSAdapter` | `generate_voice:gemini_tts` | `GEMINI_API_KEY` present in `os.environ` (network call is still required at synthesis time; an HTTP/network failure is also raised as `ProviderUnavailableError`) | Gemini API native TTS (`generateContent`, `responseModalities: ["AUDIO"]`), stdlib `urllib` only, no `google-genai`/`google-generativeai` SDK dependency |

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

### Gemini TTS (`generate_voice:gemini_tts`) — commercial-licensed Thai voice

Unlike every other backend in this module (all free/local/non-commercial),
`GeminiTTSAdapter` calls the paid Gemini API's native TTS
(`gemini-2.5-flash-preview-tts` by default; both model and voice are
constructor/call parameters). It exists specifically to give clipme a
Thai voice that is cleared for commercial output, not just evaluation.

- **License**: Gemini API Terms of Service — commercial use of generated
  output is allowed. Google's paid tier is recommended when "no training on
  submitted data" matters for a customer's content; the free tier's terms
  may differ on data use. Read the current terms at
  https://ai.google.dev/gemini-api/terms before relying on this for a real
  customer deliverable — this doc summarizes, it is not the terms.
- **Auth**: `GEMINI_API_KEY` read from `os.environ` at call time (not
  cached, not logged). The key is sent only via the `x-goog-api-key` HTTP
  header, never in the URL query string. Export it from a gitignored
  secrets file (`.env`, loaded with `set -a; . .env; set +a`, or
  `~/.config/araya/gemini.env`) — never commit it, never put it in a
  command-line argv where it would land in shell history / `ps`.
- **Cost**: pay-per-character/audio-second on Google's standard Gemini API
  pricing (not free-tier-safe for high volume) — check current pricing at
  https://ai.google.dev/gemini-api/docs/pricing before batch use; this
  adapter does not track or cap spend itself.
- **Availability check**: key presence only, not validity — an invalid or
  quota-exhausted key surfaces as an HTTP 401/403/429
  `ProviderUnavailableError` at call time, never a fabricated result.
- **Audio format**: Gemini TTS returns raw base64 PCM (24kHz, 16-bit mono),
  which this adapter decodes and writes to a proper WAV via the stdlib
  `wave` module. Duration is measured via `ffprobe` when available, else
  computed from the raw PCM sample count (never left unmeasured).
- **Thai**: VERIFIED on this machine, 2026-09-27 — synthesized
  `"สวัสดีครับ นี่คือการทดสอบเสียงภาษาไทย"` via the `Kore` voice (the
  adapter's default; picked from a proof-of-concept script in
  `.scratch/commercial/gemini_tts_test.py` that confirmed good Thai
  output), producing an audible, well-formed Thai WAV file.
- Registered under `generate_voice:gemini_tts` only — `edge_tts` remains
  the bare `generate_voice` default; a caller opts into the paid,
  commercial-cleared backend explicitly.
