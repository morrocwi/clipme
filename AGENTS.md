# AGENTS.md — clipme execution protocol

This file is the cross-model entrypoint. Every AI working in this repository must follow it.

## Mission

Produce one coherent finished video from an idea/source package while preserving story intent, factual integrity, continuity, technical reproducibility, and professional audiovisual quality.

## Default lead model

If the environment allows model choice, prefer the strongest available **Anthropic Opus 5.x family** model as the first-pass Lead Director / Orchestrator.

Do not assume Opus is available. Fall back to any capable model. The contracts and gates below remain identical.

## Rule 0 — do not jump from idea to render

A valid production passes through:

```text
brief
→ development
→ story
→ direction
→ storyboard/previs
→ shot design
→ audio plan
→ timeline
→ render
→ editorial
→ finishing
→ QC
→ repair
→ master
```

For very short work, stages may be compressed but not skipped semantically.

## Required thinking layers

Separate these concerns. Never collapse them into one vague "creative prompt".

### Truth layer
What claims are factual? What source supports each claim? What is uncertain?

### Story layer
What should the viewer understand, feel, anticipate, and remember?

### Directing layer
What is the viewer shown, from where, for how long, and why?

### Production layer
How are the required visual/audio assets obtained or generated?

### Editorial layer
How are time, rhythm, juxtaposition, and sound shaped?

### Verification layer
What must pass before the result can be called finished?

## Project hierarchy

```text
Project
├── Act / Chapter
│   ├── Sequence
│   │   ├── Scene
│   │   │   ├── Beat
│   │   │   │   └── Shot
│   │   │   │       ├── video frames
│   │   │   │       └── audio events
```

Use only the hierarchy needed for the chosen duration profile, but preserve IDs so larger projects can be assembled without ambiguity.

## Progressive lock protocol

Long productions are compiled, not improvised as one giant prompt.

Lock in this order:

1. brief
2. fact ledger
3. premise/theme
4. story bible
5. act/chapter map
6. sequence cards
7. scene cards
8. continuity bible
9. visual language
10. shot plans
11. audio plan
12. asset manifest
13. timeline
14. sequence masters
15. final assembly

A locked artifact may be changed only with an impact report naming affected downstream artifacts.

## Context budgeting

For long-form/film work, an agent must load:

- project intent,
- current act/sequence/scene,
- local predecessors/successors,
- continuity entries referenced by the current scene,
- relevant facts,
- visual/audio rules,
- unresolved QC items.

Do not repeatedly load the entire project when a bounded context packet is enough.

## Shot contract

Every non-trivial shot must answer:

- purpose: why this shot exists
- subject: what carries attention
- shot size
- angle
- lens / field-of-view intent
- camera position and movement
- blocking / object motion
- start state
- end state
- dialogue / narration
- sound events
- lighting intent
- color intent
- transition in/out
- continuity dependencies
- duration
- asset dependencies
- generation/render method

If an item does not apply, mark it N/A rather than silently omitting it.

## Causal visual design

Prefer transitions where a visual action motivates the next shot:

```text
object moves
→ movement reveals information
→ revealed element becomes next subject
→ camera follows / cut is motivated
```

Avoid slide-deck behavior:
- title card
- fade
- unrelated card
- fade
- unrelated card

unless the chosen style intentionally calls for it.

## Audio-first timing

For narration-led work:

1. write approved narration,
2. synthesize/record,
3. measure actual audio duration,
4. fit shot timing to speech and comprehension,
5. mix music/SFX around dialogue.

Never assume a TTS sentence length from word count alone.

## Determinism

Whenever possible:
- use explicit frame/time values,
- pin fonts and dependencies,
- record seeds/model/provider/version,
- record media hashes,
- render at defined resolution/fps,
- use reproducible FFmpeg commands,
- avoid uncontrolled real-time animation capture.

## Provider neutrality

A provider adapter may implement:
- LLM,
- TTS,
- image generation,
- video generation,
- music,
- transcription,
- renderer.

But all providers must return assets into the same manifests and obey the same rights/provenance/QC requirements.

## Independent review

For significant productions, the same agent that created an artifact should not be the only reviewer.

Preferred pattern:

```text
creator pass
→ independent critic/QC pass
→ targeted repair pass
```

If only one model is available, use separated prompts/contexts and explicit adversarial review.

## Quality gates

Blocking gates:

- FACT: unsupported factual claim
- STORY: incoherent or missing causal/narrative link
- CONTINUITY: contradictory character/object/location/screen-direction state
- READABILITY: required text not legible long enough
- AUDIO: unintelligible dialogue/narration, clipping, broken sync
- VISUAL: broken frame, missing asset, severe artifact
- RIGHTS: unknown/disallowed asset provenance
- TECH: wrong duration/profile/resolution/fps/codec or render failure

Non-blocking gates can include:
- stylistic polish
- micro-rhythm
- alternate color preference
- optional embellishment

## Repair policy

When a gate fails:
1. identify the smallest affected production unit,
2. identify its upstream dependency,
3. repair the source artifact,
4. regenerate only downstream dependencies,
5. rerun local QC,
6. rerun film-wide QC if continuity can be affected.

Do not patch a symptom in the final MP4 when the source contract is wrong.

## Scale policies

### Short
Optimize for one idea, rapid comprehension, strong hook, high visual density without overload.

### Long-form
Optimize for chapter/sequence structure, recap/foreshadow balance, cognitive pacing, motif consistency.

### Film
Optimize for dramatic progression, performance, spatial continuity, scene objectives, visual grammar, sound perspective, emotional pacing, and feature-wide continuity.

## Completion response

An execution agent must report:

- master output path
- duration
- resolution/fps
- profile
- tools/providers actually used
- QC result
- unresolved limitations
- reproducibility manifest location

Never report "done" if blocking QC items remain.


## Machine-readable orchestration

The prose in this file and each `SKILL.md` explains professional intent. Runtime orchestration is defined by:

- `manifests/unit_graph.json` — project hierarchy
- `skills/*/skill.yaml` — scope, hard dependencies, conditional ordering, outputs and activation
- `project.yaml.features` — project-specific production needs
- `project.yaml.skill_overrides` — explicit per-project activation overrides
- `manifests/production_plan.json` — generated task DAG
- `manifests/task_state.json` — persistent execution state

Use `python clipme.py plan <project>` whenever the unit graph materially changes.

Only `required` and `inline` skills are scheduled automatically. `optional` skills remain available without adding task overhead. A hard dependency whose required unit does not yet exist defers downstream tasks until a later re-plan.

Creator skills generate; assurance skills verify. Do not collapse assurance into creator self-approval for master release.
