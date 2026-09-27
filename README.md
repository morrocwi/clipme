# clipme

**clipme** is a model-agnostic AI production operating system for making **one finished video** from an idea and source material — from a 15–90 second short, to long-form explainers/documentaries, to hour-scale and film-scale productions.

The AI is not the renderer. It acts as a production team operating through explicit contracts.

## Default recommendation

Start with the strongest available **Anthropic Opus 5.x family** model as the lead Director/Orchestrator when available.

That is a default recommendation, **not a dependency**. Any AI can work in clipme if it can read the project contracts, produce valid structured artifacts, call the required production tools, and pass the same quality gates.

## Core idea

```text
IDEA / SOURCES
    ↓
DEVELOPMENT
    ↓
FACT LEDGER + STORY INTENT
    ↓
SCRIPT / TREATMENT
    ↓
DIRECTOR'S VISION
    ↓
STORYBOARD / SHOT DESIGN / PREVIS
    ↓
CINEMATOGRAPHY + PRODUCTION DESIGN + MOTION/VFX
    ↓
VOICE / MUSIC / SOUND
    ↓
DETERMINISTIC TIMELINE + RENDER
    ↓
EDIT + MIX + COLOR
    ↓
QC / CONTINUITY / FACT / TECHNICAL GATES
    ↓
REPAIR LOOP
    ↓
MASTER VIDEO
```

## Scale without changing the system

clipme uses the same hierarchy at every duration:

```text
Project
└── Act / Chapter
    └── Sequence
        └── Scene
            └── Beat
                └── Shot
                    └── Frame / Audio Event
```

A 30-second short may contain one sequence and 6–12 shots.

A 90-minute film may contain multiple acts, dozens of sequences, hundreds of scenes/beats, and 700+ shots.

The system does **not** ask one model to hold the entire film in working memory at once. It compiles, validates, locks, and renders bounded units while preserving shared continuity contracts.

## Production modes

| Mode | Typical duration | Planning unit | Primary optimization |
|---|---:|---|---|
| Short | 15–90 s | shot/beat | clarity, hook, compression |
| Explainer | 1–10 min | scene | teaching and visual causality |
| Long-form | 10–60+ min | sequence/chapter | sustained narrative and continuity |
| Film | 60–180+ min | act/sequence/scene | dramatic structure, visual language, performance, continuity |

Profiles live in `profiles/`.

## Professional production disciplines

clipme treats these as independent but coordinated skills:

1. Development / research
2. Producer / production planning
3. Screenwriting / narrative design
4. Directing
5. Storyboard / shot design / previs
6. Cinematography
7. Production design / art direction
8. Performance / voice direction
9. Motion design / animation / VFX
10. Sound design / music / dialogue
11. Editing
12. Color / finishing
13. Continuity / script supervision
14. Fact & rights verification
15. Technical QC / delivery

See `docs/architecture.md` and `skills/`.

## Non-negotiable contracts

Every production creates machine-readable artifacts for:

- `project.yaml` — intent, audience, duration, format, constraints
- `story_bible.yaml` — premise, theme, tone, world, characters, visual rules
- `fact_ledger.json` — every factual claim and its evidence status
- `continuity_bible.yaml` — persistent people, props, locations, wardrobe, terminology
- `sequence/*.yaml` — sequence goals and transitions
- `scene/*.yaml` — scene objective, conflict/change, required assets
- `shots/*.json` — camera, blocking, action, dialogue, timing, sound, transition
- `timeline.json` — exact frame/audio schedule
- `asset_manifest.json` — provenance, rights, generation source, versions
- `qc_report.json` — pass/fail gates and repair actions
- `render_manifest.json` — renderer, fps, codecs, hashes, versions

## The quality principle

**A render is not a finished video.**

A production is only complete when its mandatory gates pass:

- narrative coherence
- shot-to-shot continuity
- factual integrity
- typography/readability
- dialogue/voice intelligibility
- edit rhythm
- audio mix
- visual consistency
- technical delivery
- source/asset provenance

Failed gates create a targeted repair task and rerender only the affected unit whenever possible.

## Model interoperability

Model adapters live in `models/`.

The shared skills and schemas are the source of truth. A model adapter may explain tool syntax or strengths, but it must never redefine project semantics or lower quality gates.

Recommended routing:

```text
Lead Director / Orchestrator → Opus 5.x family by default
Research / verification       → any model + web/source tools
Writing                       → any model passing story/script gates
Storyboard / visual planning  → any vision-capable model
Code / render engineering     → any capable coding model
Voice / TTS                   → provider selected per language
Image / video generation      → swappable provider adapters
QC                            → preferably independent model/pass
```

## Golden rule for long productions

Never expand a long film as one giant prompt.

Use **progressive locking**:

```text
Premise LOCK
→ Story bible LOCK
→ Act structure LOCK
→ Sequence cards LOCK
→ Scene cards LOCK
→ Shot plans LOCK
→ Assets LOCK
→ Sequence renders
→ Assembly
→ Film-wide continuity pass
→ Final mix/color/QC
```

Any change after a lock produces an explicit dependency impact list.

## Repository map

```text
AGENTS.md
README.md
docs/
  architecture.md
  directing-language.md
skills/
  director/SKILL.md
  story/SKILL.md
  storyboard/SKILL.md
  cinematography/SKILL.md
  sound/SKILL.md
  editor/SKILL.md
  continuity/SKILL.md
  qc/SKILL.md
schemas/
  project.schema.json
  shot.schema.json
profiles/
  short-90s.yaml
  longform.yaml
  film.yaml
models/
  opus-5.md
  generic.md
examples/
  one-shot-infographic/
```

## Definition of Done

A project is done only when:

1. the master file exists,
2. required deliverables exist,
3. all blocking QC gates pass,
4. factual and asset provenance is recorded,
5. no unresolved continuity blockers remain,
6. audio/video sync is verified,
7. the project can be reproduced from its manifests.

See `AGENTS.md` for the AI execution protocol.


## Quick start

```bash
pip install -r requirements.txt

python clipme.py init work/my-video \
  --profile short-90s \
  --title "My Video" \
  --language th \
  --duration 60

python clipme.py validate work/my-video
```

When rendered sequence masters exist:

```bash
python clipme.py assemble work/my-video
python clipme.py probe work/my-video/masters/master.mp4
python clipme.py gate work/my-video
```

For a one-prompt AI handoff, start from `prompts/ONE_SHOT.md`.

## Expanded production disciplines

The repository now includes skills for:

- producer/development
- research/fact
- story/screenwriting
- directing
- storyboard/previs
- cinematography
- production design
- performance direction
- motion/animation/VFX
- sound
- editing
- continuity
- color/finishing
- QC
- accessibility/delivery

The conceptual map is in `docs/production-curriculum.md`.
