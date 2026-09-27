<!-- Founder's Mission Letter for this project, received 2026-09-27. Reproduced verbatim below. -->

# CLIPME — Mission Letter to Claude and AI Developers

Repository:

`morrocwi/clipme`

You are entering this repository not merely as a coding assistant, but as an **AI systems architect, film-production systems designer, and implementation engineer**.

Before modifying anything, understand the purpose of this project.

---

# 1. What CLIPME is trying to become

CLIPME is intended to become a **model-agnostic AI Video and Film Production Operating System**.

Its purpose is simple:

> A human should be able to begin with an idea, source material, or creative brief and progressively produce one finished video — from a 15-second clip to a 90-second infographic, a documentary, a one-hour program, or a feature-length film.

The system must remain simple when the project is simple and become sophisticated only when the work actually requires sophistication.

Therefore:

**Small project → small workflow.**

**Large project → large but structured workflow.**

We explicitly do NOT want every short clip to run through an entire feature-film production bureaucracy.

Likewise, we do NOT want a two-hour film to be generated from one enormous prompt.

Complexity must emerge from the actual production graph.

---

# 2. Core architectural philosophy

CLIPME should behave like a **production compiler**.

The conceptual pipeline is:

```text
IDEA / SOURCES
        ↓
DEVELOPMENT
        ↓
RESEARCH / FACTS
        ↓
STORY
        ↓
DIRECTING
        ↓
STORYBOARD / PREVIS
        ↓
PRODUCTION DESIGN
        ↓
CINEMATOGRAPHY
        ↓
PERFORMANCE
        ↓
VISUAL / MOTION / VFX PRODUCTION
        ↓
VOICE / SOUND / MUSIC
        ↓
EDITORIAL
        ↓
CONTINUITY
        ↓
COLOR / FINISHING
        ↓
QC
        ↓
DELIVERY
        ↓
ONE MASTER VIDEO
```

However, these stages must be **conditionally activated**.

For example, a 20-second kinetic typography clip may only require:

```text
Brief
→ Micro Story
→ Director
→ Motion
→ Sound
→ Editor
→ QC
```

A feature film may require the complete production structure.

---

# 3. Unit hierarchy

CLIPME uses one scalable hierarchy:

```text
PROJECT
└── ACT / CHAPTER
    └── SEQUENCE
        └── SCENE
            └── BEAT
                └── SHOT
                    ├── FRAME
                    └── AUDIO EVENT
```

Do not replace this with a completely different architecture unless there is compelling technical evidence.

The hierarchy is deliberately duration-independent.

A short film may skip several layers.

A feature film may use all layers.

---

# 4. Current microkernel principle

The orchestration core should remain small.

Conceptually:

```text
CLIPME MICROKERNEL

Project
Profile
Feature Detector
Unit Graph
Skill Registry
Task DAG Planner
Task State
Locks
Dependency Tracking
Validation
Orchestrator
QC / Release Gate
```

Everything else should be extensible around this kernel.

Do not build a giant monolithic application.

Do not create complexity simply because it is possible.

---

# 5. Skills are professional production disciplines

CLIPME should contain reusable AI skills representing real production disciplines.

Current and expected skill domains include:

```text
Producer / Development
Research / Fact Verification
Screenwriting / Story
Director
Storyboard / Previsualization
Cinematography
Production Design / Art Direction
Performance Direction
Motion Design / Animation / VFX
Voice / TTS
Sound Design
Music
Editor
Continuity / Script Supervision
Color / Finishing
Rights / Provenance
Quality Control
Accessibility
Delivery
```

Each skill should have two layers.

## Human / AI-readable instruction

```text
skills/<skill>/SKILL.md
```

This explains:

- professional purpose
- production principles
- inputs
- outputs
- decision logic
- quality standards
- failure conditions

## Machine-readable contract

```text
skills/<skill>/skill.yaml
```

This should describe things such as:

```yaml
id:
layer:
scopes:
task_scope:
requires:
after_if_active:
consumes:
produces:
gates:
activation:
```

The Markdown explains the craft.

The YAML drives orchestration.

Keep these concerns separate.

---

# 6. Skill activation must remain adaptive

Every skill can conceptually be:

```text
REQUIRED
INLINE
OPTIONAL
SKIP
```

Meaning:

**REQUIRED**
Create an explicit production task.

**INLINE**
The work still matters but may be performed cheaply or within another lead-agent context.

**OPTIONAL**
Available to the production but should not automatically create overhead.

**SKIP**
Not needed.

The planner should determine activation from:

```text
PROJECT PROFILE
+
PROJECT FEATURES
+
UNIT GRAPH
+
SKILL DEPENDENCIES
+
EXPLICIT OVERRIDES
```

Example project features:

```yaml
features:
  factual: true
  narration: true
  infographic: true
  characters: false
  dialogue: false
  generated_video: false
  complex_action: false
  music: true
  captions: true
```

Examples of expected behavior:

```text
factual
→ research becomes required

characters/dialogue
→ performance direction becomes relevant

generated_video
→ cinematography becomes relevant

complex_action
→ storyboard/previs becomes required

captions
→ accessibility/delivery becomes relevant
```

Do not hard-code every possible workflow.

Use capability and feature composition.

---

# 7. Progressive production is essential

A project should not need its entire hierarchy at initialization.

For example:

```text
PROJECT
```

may initially exist alone.

Then:

```text
Producer
→ Story
```

may produce:

```text
ACT
SEQUENCE
SCENE
BEAT
```

Later:

```text
Director
```

may produce detailed shot structure.

The planner must therefore support **re-planning** as the Unit Graph expands.

Existing valid work should be preserved.

Affected downstream work should be invalidated when its structural dependencies change.

Do not reset the entire project when one scene changes.

---

# 8. Context must be bounded

For feature-length work, never load the complete project into every AI task.

A task working on:

```text
SHOT_0372
```

should normally receive only the relevant context packet:

```text
project intent
sequence objective
scene objective
current beat
shot contract
relevant characters
relevant props
relevant world state
previous shot
next shot
visual bible subset
sound bible subset
continuity state
relevant facts
open QC issues
```

This is critical for long productions.

CLIPME should scale through **hierarchical context retrieval**, not gigantic prompts.

---

# 9. We want APIs as first-class citizens

CLIPME should not only contain skills.

It should also develop a clean **API layer** so external agents, applications, web interfaces, automation systems, and AI models can operate the production system.

Design an API architecture around the existing kernel.

Potential logical API resources include:

```text
/projects
/profiles
/features
/units
/skills
/plans
/tasks
/artifacts
/assets
/providers
/renders
/qc
/deliveries
```

Possible operations:

```text
POST   /projects
GET    /projects/{id}

GET    /projects/{id}/graph
PATCH  /projects/{id}/graph

POST   /projects/{id}/plan

GET    /projects/{id}/tasks
GET    /projects/{id}/tasks/ready

POST   /tasks/{task_id}/start
POST   /tasks/{task_id}/complete
POST   /tasks/{task_id}/fail

POST   /projects/{id}/validate

POST   /projects/{id}/render
POST   /projects/{id}/assemble

GET    /projects/{id}/qc
POST   /projects/{id}/release
```

Do not implement endpoints merely for completeness.

The API should expose real domain operations from the kernel.

The CLI and API should ultimately be two interfaces to the same underlying application services.

Avoid duplicating business logic.

Preferred conceptual structure:

```text
                CLIPME CORE
                    │
        ┌───────────┴───────────┐
        │                       │
       CLI                     API
        │                       │
        └───────────┬───────────┘
                    │
                 Skills
                    │
                 Providers
```

---

# 10. Provider APIs must be interchangeable

CLIPME must not depend permanently on one AI company.

Claude may be the recommended initial Lead Director / Orchestrator, but the production architecture must remain model-agnostic.

Provider adapters may include:

```text
LLM
Vision LLM
TTS
Speech-to-text
Image generation
Video generation
Music generation
SFX
Embedding/search
Web research
Code rendering
Browser rendering
3D
Compositing
FFmpeg
```

Potential examples may include providers from Anthropic, OpenAI, Google, or others.

But provider-specific logic must sit behind adapters.

A production skill should request a capability:

```text
generate_voice
generate_image
generate_video
render_svg
verify_fact
```

rather than becoming tightly coupled to a specific vendor whenever possible.

---

# 11. Claude's recommended role

When available, a strong Claude Opus-family model is our preferred initial candidate for:

```text
Lead Production Orchestrator
Development
Story architecture
Directing
Cross-discipline reasoning
Repair planning
Long-form production supervision
Code/system coordination
```

But Claude must use CLIPME's contracts rather than becoming the architecture itself.

In other words:

```text
Claude ≠ CLIPME
```

Claude is an excellent operator of CLIPME.

The production system must survive model replacement.

---

# 12. APIs need capability discovery

Providers and agents should describe their capabilities.

For example:

```yaml
provider: example
capabilities:
  llm: true
  vision: true
  image_generation: false
  video_generation: true
  tts:
    languages:
      - th
      - en
  max_video_seconds: 8
```

The orchestration layer should eventually be capable of choosing an implementation based on:

```text
required skill
required capability
quality
cost
latency
availability
language
duration
rights/privacy constraints
```

Do not prematurely build a complicated optimization engine.

First define the contract correctly.

---

# 13. Artifacts must be explicit

AI agents should never communicate important production state only through conversation.

Important decisions must become artifacts.

Examples:

```text
project.yaml
unit_graph.json
story_bible.yaml
character_bible.yaml
world_bible.yaml
visual_bible.yaml
sound_bible.yaml
continuity_bible.yaml
fact_ledger.json
shot contracts
timeline.json
asset_manifest.json
production_plan.json
task_state.json
qc_report.json
render_manifest.json
delivery_manifest.json
```

Conversations are transient.

Artifacts are production state.

---

# 14. Referential integrity is mandatory

IDs must be verifiable.

Examples:

```text
SEQ_002
SCENE_017
BEAT_044
SHOT_219
CHAR_003
PROP_014
FACT_029
ASSET_108
```

The validator should catch:

```text
missing refs
duplicate IDs
orphan units
cycles
invalid parents
parent/child disagreement
scene/shot disagreement
fact references that do not exist
asset references that do not exist
timeline references that do not exist
```

JSON Schema alone is not sufficient.

Graph validation is required.

---

# 15. Editing and time are first-class concepts

The final product is temporal.

Therefore CLIPME needs an executable timeline abstraction.

Do not treat video as merely a collection of generated clips.

We care about:

```text
duration
cut points
J cuts
L cuts
dialogue timing
voice timing
SFX timing
music timing
transitions
overlays
titles
captions
mixing
frame rate
```

For narration-led work:

```text
approved narration
→ record/TTS
→ measure actual duration
→ adjust picture timeline
```

Do not estimate final TTS timing only from word count.

---

# 16. Different visual production methods must coexist

Do not assume every shot should use a text-to-video model.

CLIPME should choose the simplest controllable method appropriate to the visual problem.

Preference may often be:

```text
Code / HTML / SVG / Canvas
↓
2D Motion / Compositing
↓
Generated still + controlled motion
↓
3D / Simulation
↓
Generated video
↓
Hybrid
```

Examples:

Charts, maps, typography, UI, timelines and precise diagrams should generally not be delegated to probabilistic video generation when deterministic graphics are more reliable.

---

# 17. Quality Assurance is independent from creation

This is non-negotiable.

Separate:

```text
CREATOR SKILLS
```

from:

```text
ASSURANCE SKILLS
```

Examples:

Creators:

```text
Writer
Director
Cinematography
Motion/VFX
Sound
Editor
Color
```

Assurance:

```text
Research Verification
Continuity
Rights/Provenance
Technical QC
Master QC
```

A creator should not be the sole authority declaring its own work correct.

Use an independent agent/model/pass when practical.

---

# 18. Rendered does not mean Finished

The system philosophy is:

> Rendered ≠ Finished

A production is finished only after the required gates pass.

Potential gates include:

```text
FACT
STORY
DIRECTION
CONTINUITY
READABILITY
AUDIO
VISUAL
RIGHTS
TECH
```

Do not blindly trust a field such as:

```json
"status": "PASS"
```

Compute release eligibility from required gates and actual validation.

---

# 19. Repair should be targeted

When a failure occurs:

```text
identify smallest affected unit
↓
find root dependency
↓
repair source artifact
↓
invalidate affected downstream tasks
↓
rerender affected units
↓
rerun local QC
↓
rerun global QC only when needed
```

Avoid rebuilding an entire film because one shot or fact changed.

This principle is central to practical long-form production.

---

# 20. Skills and APIs should converge on the same contracts

The API should not invent a second CLIPME domain model.

Skills, CLI, API, and provider adapters should all refer to the same concepts:

```text
Project
Unit Graph
Skill
Task
Artifact
Provider
Asset
Timeline
QC
Delivery
```

If the API needs a concept that does not exist in the kernel, first determine whether the kernel itself is missing a real production concept.

Do not create API-only semantics.

---

# 21. Please audit before changing

Before modifying this repository:

1. Read `README.md`.
2. Read `AGENTS.md`.
3. Read `docs/architecture.md`.
4. Read `docs/orchestration.md`.
5. Read `docs/production-curriculum.md`.
6. Read all current schemas.
7. Inspect all `skills/*/SKILL.md`.
8. Inspect all `skills/*/skill.yaml`.
9. Inspect `core/`.
10. Inspect current tests and CI.

Then produce a short architecture assessment.

Specifically identify:

```text
what should remain
what is duplicated
what is missing
what can be simplified
what is documentation-only
what is actually executable
what blocks API implementation
what blocks real provider execution
```

Do not refactor merely for aesthetics.

---

# 22. Improve incrementally

Prefer:

```text
small coherent commits
tests first or tests with each feature
backward-compatible contracts where practical
explicit migrations when contracts change
```

Avoid:

```text
huge rewrites
renaming everything
introducing frameworks without need
adding dozens of abstractions before execution exists
```

CLIPME's value should come from strong production semantics, not framework complexity.

---

# 23. Priority development roadmap

Unless repository inspection shows a stronger dependency ordering, prioritize roughly:

## Phase A — Kernel hardening

- validate Skill manifests automatically
- harden Unit Graph consistency
- improve dependency invalidation
- artifact dependency graph
- lock/unlock semantics
- profile validation
- task provenance
- task/event history

## Phase B — Application service layer

Extract reusable application operations from the CLI.

For example:

```text
create_project()
validate_project()
plan_project()
get_ready_tasks()
start_task()
complete_task()
fail_task()
replan_project()
assemble_project()
evaluate_release()
```

The CLI should call these services.

## Phase C — API

Implement a minimal stable API over those services.

Prefer a small API framework only if justified.

Include:

```text
OpenAPI specification
versioned schemas
clear errors
idempotency where appropriate
task state transitions
```

## Phase D — Provider interface

Define capability-based interfaces for:

```text
LLM
TTS
image
video
music
rendering
research
```

Implement one or two real adapters first.

Do not implement ten empty provider shells.

## Phase E — End-to-end reference production

Create at least:

### Example 1
30–60 second infographic.

### Example 2
3–5 minute explainer.

### Example 3
multi-sequence long-form skeleton.

Demonstrate that the same kernel scales without forcing identical workflows.

---

# 24. Tests that must continue to exist

Protect at minimum these properties:

```text
short work stays small
optional skills are not automatically scheduled
film activates deeper production disciplines
bootstrap does not jump ahead before units exist
unit graph has no broken hierarchy
task DAG has no cycles
re-plan preserves unaffected work
graph changes invalidate affected downstream work
QC cannot release an incomplete master
provider substitution does not change production semantics
```

Add regression tests whenever you discover a structural failure.

---

# 25. Security and reliability

Never:

```text
commit API keys
write secrets to prompts/artifacts
claim provider execution occurred when it did not
claim media exists when it was not rendered
invent source provenance
invent licenses
invent QC results
```

Use environment variables or secret management.

Execution logs should distinguish:

```text
planned
requested
executed
validated
passed
```

These states must not be conflated.

---

# 26. What success looks like

A successful CLIPME architecture should allow this:

```text
Human:
"Create a 45-second Thai infographic explaining X."

CLIPME:
small graph
small active skill set
few tasks
provider execution
QC
one MP4
```

And without changing the core architecture:

```text
Human:
"Create a 90-minute documentary."

CLIPME:
project
chapters
sequences
scenes
beats
shots
bounded context packets
many skill tasks
local renders
sequence masters
continuity management
global edit
sound
color
master QC
one finished film
```

The difference should be **graph size and activated production needs**, not an entirely different software system.

---

# 27. Your immediate assignment

Please now inspect the repository as it actually exists.

Do not assume this document is perfectly synchronized with the code.

Treat repository reality as authoritative.

Then:

1. Produce an architecture gap analysis.
2. Identify the smallest changes needed to strengthen the current design.
3. Create a concrete Skills + API architecture plan.
4. Implement the highest-value missing layer.
5. Add tests.
6. Run tests.
7. Review your own changes adversarially.
8. Fix the problems you find.
9. Document the resulting architecture.
10. Leave the repository simpler or equally simple at the core, even if its capabilities increase.

Do not stop at recommendations if implementation is possible.

The objective is not to make CLIPME look sophisticated.

The objective is to make it capable of reliably coordinating AI systems and audiovisual production tools to create finished video at any practical scale.

---

## Final principle

When making architectural decisions, keep returning to this equation:

```text
CLIPME =
Small Stable Kernel
+
Professional Skills
+
Explicit Production Units
+
Adaptive Task Graph
+
Replaceable AI / Media APIs
+
Persistent Artifacts
+
Independent Quality Assurance
```

And the scaling rule:

```text
small work → small graph → few tasks

large work → large graph → many bounded tasks

both → same production architecture → one finished video
```

Please preserve this principle while improving the repository.
