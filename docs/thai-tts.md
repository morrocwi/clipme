# Thai voices (offline TTS)

Two offline (no-network-at-synthesis-time) Thai text-to-speech backends are
wired into `core/providers_media.py`. Both were evaluated 2026-09-27 on this
machine (RAM-constrained, CPU-only, `free -m` gated before any load).

## What exists

| Backend | Registry key | Model | Format | License | Size | Phonemizer |
|---|---|---|---|---|---|---|
| Piper (Thai, MMS re-export) | `generate_voice:piper_th` | `th_TH-mms_female-medium` (converted from `VIZINTZOR/MMS-TTS-THAI-FEMALEV2`) | ONNX (`piper-tts`) | **CC-BY-NC-4.0** (non-commercial) | 114 MB | none — `phoneme_type: "text"`, one Unicode codepoint per phoneme |
| MMS-TTS (Meta) | `generate_voice:mms_tts` | `facebook/mms-tts-tha` (VITS) | HF `transformers` (`VitsModel`) | **CC-BY-NC-4.0** (non-commercial) | ~145 MB (HF cache) | none — same codepoint-level tokenizer as the base model |

Both are **CC-BY-NC-4.0: non-commercial only.** Do not ship either through a
paying clipme customer's output without the founder explicitly clearing that
first — this is a licensing gate, not a technical one.

VERIFIED (measured on this machine, 2026-09-27):
- Piper Thai voice loaded and synthesized `"สวัสดีครับ นี่คือการทดสอบเสียงภาษาไทยของระบบคลิปมี"`
  to a 5.03s, 22050Hz mono WAV via the existing `PiperTTSAdapter` — no code
  change needed, just `voice="th_TH-mms_female-medium"`.
- `facebook/mms-tts-tha` loaded via `transformers.VitsModel` +
  `AutoTokenizer`, synthesized the same sentence to a 5.15s, 16000Hz mono WAV.
  Peak RSS ≈745 MB, wall time ≈17.8s (model load + one synthesis, CPU-only,
  `/usr/bin/time -v` "Maximum resident set size" 762,756 KB).
- Round-trip check: `FasterWhisperSTTAdapter.transcribe(..., language="th")`
  on the MMS output returned `"สวัสดีครับปันนี้ คือกันทดสอบสิ่งภาษาไทยก่อนรับบูกคิดดี"`
  — recognizably Thai and roughly on-topic but noticeably garbled next to the
  source sentence (whisper `base` model, no fine-tuning for Thai). This is a
  rough intelligibility signal only, not a WER benchmark — nobody ran a real
  WER evaluation here.

## Why no espeak-ng install was needed

The task brief flagged a real risk: Piper voices for low-resource languages
often need `espeak-ng`'s phoneme rules, and `espeak-ng`'s own Thai support is
known to be weak (INSTINCT, relayed from `piper/phonemize_thai.py`'s own
docstring in the installed `piper-tts==1.8.0` package — not independently
re-verified against espeak-ng upstream here): it describes espeak-ng's Thai
voice as a placeholder copied from Shan phoneme/tone data, with no lexicon
for word segmentation and ~11% of tokens (measured by that docstring's
author, not by us) losing their vowel entirely.

That risk turned out not to apply to the voice actually used here. The
`th_TH-mms_female-medium` Piper voice's `.onnx.json` declares
`"phoneme_type": "text"` — Piper treats each Unicode codepoint as its own
phoneme, exactly matching how the underlying MMS-TTS model was trained
(intersperse-with-blank over a 71-character Thai vocabulary). No espeak-ng,
no phonemizer of any kind, is invoked for this voice. Synthesis ran cleanly
with `piper-tts==1.8.0` already installed in this repo's `.venv` — no error,
nothing to fall back on, no sudo install attempted or needed.

Separately (OPEN — not exercised in this pass): the installed `piper-tts`
package also ships a dedicated `piper.phonemize_thai` module (TLTK-based
grapheme-to-phoneme with explicit tone digits, BSD-3-Clause), used by the
official `rhasspy/piper-voices` `th_TH-tsync2-medium` voice
(`"phoneme_type": "thai"`). That voice's training dataset is licensed
CC-BY-NC-SA-3.0 (non-commercial **and** share-alike — a stricter condition
than the two backends above) and needs `pip install tltk unicode-rbnf` (the
piper `th` extra) at runtime. Not installed or evaluated here since the
`text`-phoneme MMS re-export already worked with zero extra dependencies;
noted for completeness in case a different voice/quality tradeoff is wanted
later.

## Training a Piper Thai voice from scratch (OPEN — not done here, relaying secondhand)

Everything in this section is relayed from public Piper/`piper1-gpl`
documentation and dataset pages, not personally verified by running a
training job in this session:

1. **Dataset**: Mozilla Common Voice `th` split (permissively licensed,
   CC0, but read-aloud sentences of variable quality/mic), or NECTEC TSync2
   (via `dubbing-ai/vaja-thai` on HF, CC-BY-NC-SA-3.0 — non-commercial), or
   a purpose-recorded single-speaker corpus if commercial use is the goal.
2. **Text normalization / segmentation**: Thai script has no spaces between
   words. Two documented approaches:
   - `pythainlp` word segmentation feeding into `espeak-ng`'s (weak, per
     above) Thai phonemes — the older/more common community recipe, but
     inherits `espeak-ng`'s Thai weaknesses (no tone, vowel-reordering
     issues).
   - `piper`'s own `phonemize_thai.py` (TLTK-based, explicit tones) — newer,
     used for the official `tsync2` voice; needs `tltk` + `unicode-rbnf`.
3. **Training**: `piper-train` (part of `piper1-gpl` / `piper-tts`'s `train`
   extra), typically warm-started from an existing checkpoint (the official
   `tsync2` voice was finetuned from a LibriTTS-R English base). VITS
   training is GPU-memory-bound; the piper project's own guidance puts a
   single-speaker medium-quality voice within reach of a 4GB GPU (e.g. this
   machine's GTX 1650 Ti) with small batch sizes, but expect it to be slow
   (many hours) and this has not been attempted or timed in this repo.
4. **Export**: `piper-train`'s export step produces the `.onnx` +
   `.onnx.json` pair `PiperTTSAdapter` already expects — no adapter code
   change needed for a home-trained voice, only a new `voice="..."` value.

## Adapters in this repo

- `core/providers_media.py::PiperTTSAdapter` — unchanged code, now also
  documented/tested against `voice="th_TH-mms_female-medium"`. Registered
  as `generate_voice:piper_th` (in addition to the existing
  `generate_voice:piper_tts` alias, same class, same default English voice
  unless a Thai `voice=` is passed).
- `core/providers_media.py::MMSTTSAdapter` (new) — wraps
  `facebook/mms-tts-tha` via `transformers.VitsModel` +
  `AutoTokenizer`. Lazy imports; `importlib.util.find_spec` availability
  check so importing `core/providers_media.py` never fails when
  `transformers`/`torch` aren't installed. One model instance per adapter
  instance (never two heavy models loaded at once). Registered as
  `generate_voice:mms_tts`. `edge_tts` remains the default
  `"generate_voice"` — neither Thai backend overrides it.

`transformers`, `torch` (CPU wheel) and `soundfile` are listed in
`requirements-providers.txt` under a commented-out "optional Thai offline
TTS (heavy)" block, not in `requirements.txt` or the default
`requirements-providers.txt` install set — install them explicitly if this
backend is needed.
