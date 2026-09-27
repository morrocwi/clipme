# clipme architecture

## 1. What clipme is

clipme is a **production compiler**.

Human/AI creative decisions are expressed as structured artifacts. Those artifacts are compiled into audiovisual assets, assembled into sequences, checked, repaired, and delivered as one master.

This is deliberately different from "prompt → video model → accept whatever appears".

## 2. Four planes

### A. Creative plane
Development, writing, directing, performance, visual language.

### B. Production plane
Asset generation/acquisition, layout, animation, shooting/simulation, TTS/recording, music, SFX.

### C. Timeline plane
Exact temporal assembly: shots, transitions, dialogue, ambience, music, graphics, captions.

### D. Assurance plane
Facts, continuity, rights/provenance, accessibility, technical QC, reproducibility.

The four planes exchange data through manifests rather than hidden assumptions.

## 3. Duration-independent hierarchy

```text
PROJECT
  ACT / CHAPTER
    SEQUENCE
      SCENE
        BEAT
          SHOT
            VIDEO FRAME RANGE
            AUDIO EVENT RANGE
```

### Project
The whole deliverable and its promise to the audience.

### Act / Chapter
A major phase of dramatic or explanatory development.

### Sequence
A self-contained run of scenes/shots pursuing one local narrative goal.

### Scene
A coherent unit of time/place/action or conceptual presentation.

### Beat
The smallest meaningful change in intention, information, emotion, or action.

### Shot
One continuous camera/view/timeline unit.

This hierarchy is the central scaling mechanism.

## 4. Compilation strategy by duration

### 15–90 seconds
Compile at shot/beat level directly.

Typical:
- 1 premise
- 1 sequence
- 3–8 beats
- 5–20 shots

### 1–10 minutes
Compile scene-by-scene, then assemble.

Typical:
- 1–3 sequences
- 3–15 scenes
- 15–100 shots

### 10–60+ minutes
Compile sequence-by-sequence.

Each sequence gets:
- intent
- setup/payoff
- local continuity packet
- scene list
- shot plan
- audio plan
- sequence QC
- sequence master

Then assemble sequence masters and perform global passes.

### Film scale
Use hierarchical locking and feature-wide bibles.

```text
story bible
+ character bible
+ world bible
+ continuity bible
+ visual bible
+ sound bible
          ↓
act maps
          ↓
sequence cards
          ↓
scene cards
          ↓
coverage / shot plans
          ↓
sequence production
          ↓
reels / acts
          ↓
feature assembly
          ↓
feature-wide picture + sound + continuity QC
```

## 5. The bibles

### Story bible
Premise, theme, audience contract, tone, genre, structure, ending promise.

### Character bible
Identity, goal, need, contradiction, voice, relationships, appearance, arc, forbidden drift.

### World bible
Places, rules, geography, era, technology, social/cultural facts, recurring environment logic.

### Continuity bible
Current state of wardrobe, props, injuries, object positions, time of day, weather, screen direction, terminology.

### Visual bible
Aspect ratio, framing tendencies, lens language, camera movement, lighting logic, palette, typography, texture, graphic style.

### Sound bible
Dialogue perspective, ambience philosophy, leitmotifs, music rules, SFX density, silence rules, loudness target.

These are not prose decorations; scenes and shots reference them by stable IDs.

## 6. Roles and skills

A single AI may perform multiple roles, but the roles remain distinct.

### Development Producer
Tests feasibility, scope, sources, rights, target audience, delivery constraints.

### Research Editor
Builds fact ledger and evidence package.

### Screenwriter / Narrative Designer
Turns information/premise into dramatic or explanatory progression.

### Director
Controls viewpoint, staging, performance intent, time, emphasis, and emotional logic.

### Storyboard / Previs Artist
Externalizes spatial/temporal decisions before expensive rendering.

### Cinematographer
Defines image capture language: lens, position, movement, exposure/lighting intention, depth, composition.

### Production Designer / Art Director
Defines world appearance, sets, props, wardrobe, graphics, recurring visual motifs.

### Animation / Motion / VFX
Creates impossible, explanatory, synthetic, or composited visuals.

### Sound Director
Plans dialogue/VO, ambience, perspective, silence, SFX, music.

### Editor
Controls selection, order, duration, juxtaposition, transitions, rhythm, information release.

### Color / Finishing
Normalizes and shapes final image response while protecting continuity/readability.

### Script Supervisor / Continuity
Checks spatial, temporal, object, wardrobe, performance, and dialogue continuity.

### QC Supervisor
Runs objective gates and produces repair tickets.

## 7. Director system

The Director converts story intent into viewer experience.

For each scene:

```yaml
scene_objective: what must change
viewer_question: what should the audience be asking
dramatic_value_before: ...
dramatic_value_after: ...
point_of_view: ...
performance_intent: ...
spatial_strategy: ...
coverage_strategy: ...
visual_motif: ...
sound_strategy: ...
entry: ...
exit: ...
```

For each shot:

```yaml
purpose: reveal / conceal / compare / orient / intensify / release / transition
subject: ...
shot_size: EWS / WS / MS / MCU / CU / ECU / insert
angle: eye / high / low / top / dutch / profile / POV
lens_intent: wide / normal / long / macro / orthographic-like
camera_move: static / pan / tilt / dolly / truck / crane / handheld / orbit / follow
blocking: ...
focus_strategy: ...
lighting_intent: ...
duration: ...
cut_motivation: action / gaze / dialogue / graphic / sound / idea / emotion
```

## 8. Storyboard and previs

Storyboard is not "make pretty sketches".

Its job is to test:
- geography
- eyelines
- screen direction
- composition
- coverage
- visual causality
- action readability
- transition logic
- shot economy
- expensive asset needs

Previs adds approximate timing, camera motion, blocking, dialogue and sound.

For synthetic production, storyboard/previs can be generated as low-cost vector/blocking renders before high-cost image/video generation.

## 9. Continuity graph

Every persistent entity gets an ID:

```text
CHAR_001
LOC_004
PROP_021
WARD_003
GRAPHIC_012
MOTIF_005
```

Shots declare:
- entities entering,
- entities visible,
- state before,
- state after.

The continuity checker can therefore detect:
- object reappears after destruction,
- wardrobe changes without transition,
- time-of-day inconsistency,
- left/right screen direction flip,
- character location contradiction,
- terminology drift,
- factual number mismatch.

## 10. Timeline model

The timeline is an executable contract.

```text
video tracks:
  base picture
  overlays
  titles/graphics
  captions
  transitions

audio tracks:
  dialogue/VO
  production/room tone
  ambience
  SFX
  music
  optional stems
```

Every event uses explicit start/end frames or timestamps.

For long projects, timelines are nested:
- shot timelines
- scene timelines
- sequence timelines
- act/reel timelines
- master timeline

## 11. Render architecture

Preferred order:

1. deterministic code/vector renderer where suitable
2. generated stills + controlled animation
3. generated video shots where motion realism adds value
4. compositing
5. captions/graphics
6. audio assembly
7. sequence render
8. master assembly
9. finishing

Do not use an expensive generative-video call for a chart, title, icon, timeline, map, or diagram that code can render more accurately.

## 12. Asset provenance

Every external or generated asset records:

```json
{
  "asset_id": "ASSET_001",
  "type": "image",
  "source": "generated|licensed|user|public-domain|code",
  "provider": "...",
  "model_or_tool": "...",
  "prompt_or_recipe_ref": "...",
  "seed": null,
  "license": "...",
  "hash": "...",
  "used_in": ["SHOT_001"]
}
```

## 13. Quality model

Quality is multi-dimensional, not one score.

### Story
Comprehension, causality, pacing, setup/payoff, emotional progression.

### Direction
Purposeful viewpoint, staging, shot economy, motivated transitions, coherent visual grammar.

### Image
Composition, continuity, legibility, artifact control, color consistency.

### Sound
Intelligibility, perspective, dynamics, ambience continuity, music/SFX balance.

### Truth
Support for factual claims, uncertainty handling, numbers/names/dates consistency.

### Technical
Resolution, fps, codec, channel layout, sync, missing frames, black/frozen frames, delivery spec.

### Reproducibility
Recorded providers, versions, seeds, commands, manifests, hashes.

A project may pass technical QC and still fail story/directing QC.

## 14. Repair graph

Each artifact records dependencies.

Example:

```text
FACT_007
  ↓
SCRIPT_LINE_043
  ↓
SCENE_012
  ↓
SHOT_098, SHOT_099
  ↓
SEQ_06_MASTER
  ↓
FILM_MASTER
```

If FACT_007 changes, clipme knows what must be reconsidered.

## 15. One-video guarantee as a system property

The top-level output is always one master deliverable, even when production is distributed.

```text
many bounded creative units
→ individually validated sequence masters
→ deterministic assembly
→ global continuity/editorial/sound/color pass
→ one master
```

This is how clipme can use the same production system for a 30-second reel and a two-hour film.
