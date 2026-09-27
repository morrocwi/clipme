# Production curriculum — the disciplines behind clipme

clipme treats professional video production as a collection of interoperable disciplines.

The goal is not to imitate job titles. The goal is to preserve the distinct **decision types** those disciplines developed over decades of film, television, animation, documentary, advertising, motion design, and post-production practice.

## Stage 1 — Development

### Producer / Development
Defines audience, scope, constraints, feasibility, rights, schedule, risks, and delivery.

### Research / Fact
Defines what is known, sourced, uncertain, current, and representable.

### Screenwriting / Narrative Design
Defines premise, theme, dramatic/expository progression, scenes, beats, dialogue, narration, setup/payoff.

**Lock:** project promise + evidence basis + story architecture.

---

## Stage 2 — Directorial design

### Director
Controls viewpoint, staging, performance intention, emphasis, scene objective, coverage, transition logic, and audience experience.

### Performance Direction
Controls playable intention, subtext, vocal behavior, reaction, timing, and character state.

### Production Design / Art Direction
Controls visible world: locations, sets, props, wardrobe, materials, graphics, motifs, cultural/period rules.

### Cinematography
Controls framing, field of view/lens semantics, camera position/movement, lighting, depth, visual continuity.

### Sound Direction
Controls what is heard, from what perspective, and how sound guides attention/emotion/space.

**Lock:** director vision + visual/sound/world/character bibles.

---

## Stage 3 — Visualization before final production

### Storyboard
Tests shot composition, geography, screen direction, eyelines, action readability, coverage, and transitions.

### Previsualization / Animatic
Adds approximate timing, camera motion, blocking, dialogue, sound, and edit order.

This stage is disproportionately valuable for AI production because it lets the system discover errors before expensive image/video generation.

**Lock:** sequence/scene/shot plan for production.

---

## Stage 4 — Production / Generation

Depending on the work, a shot may be created through:

- live-action capture
- code/SVG/Canvas/WebGL
- motion graphics
- 2D animation
- 3D
- compositing
- generated image
- generated video
- archival/licensed media
- hybrid workflows

### Motion / Animation / VFX
Builds controlled movement, composites layers, creates simulations/effects, and realizes synthetic shots.

### Audio production
Records/synthesizes voice, dialogue, ambience, Foley/SFX, music.

**Lock:** approved shot assets + provenance.

---

## Stage 5 — Editorial

### Picture Editor
Controls selection, order, duration, rhythm, juxtaposition, information release, and dramatic/comprehension timing.

### Sound Editor / Mixer
Shapes dialogue clarity, ambience continuity, SFX, music, perspective, dynamics, and final balance.

### Color / Finishing
Normalizes and shapes the image, matches shots/scenes, protects continuity and readability.

**Lock:** picture, sound, grade.

---

## Stage 6 — Supervision and assurance

### Script Supervisor / Continuity
Maintains spatial, temporal, performance, wardrobe, prop, factual, and terminology consistency across independently produced material.

### Rights / Provenance
Tracks origin, license/permission, model/tool/version, prompts/recipes, hashes, and usage.

### QC
Separates "rendered" from "finished": fact, story, direction, continuity, readability, audio, visual, rights, technical.

### Accessibility / Delivery
Creates captions/subtitles and platform/master encodes; verifies actual distribution specifications.

---

# Mapping disciplines to duration

## 15–90 seconds
All disciplines still exist, but many are compressed:
- producer brief
- fact check
- 3–8 beats
- director shot logic
- storyboard/previs only for risk shots
- direct shot render
- edit/sound/color/QC
- one master

## 1–10 minutes
Scene structure becomes explicit and storyboard/animatic becomes more valuable.

## 10–60+ minutes
Sequence structure, bibles, continuity state, and sequence masters become mandatory for reliable scaling.

## Feature / film
The system must treat the work as a hierarchy:
- act
- sequence
- scene
- beat
- shot

The feature is assembled from locally validated units while global bibles preserve identity.

# Why this matters for AI

A powerful model can generate text, code, images, sound, or video, but output quality becomes unstable when distinct professional decisions are collapsed into one instruction.

clipme therefore asks:
- **Producer:** should we make this?
- **Research:** what is true?
- **Writer:** what is the progression?
- **Director:** what should the viewer experience?
- **Storyboard:** does the plan work spatially and temporally?
- **Cinematography/Design/Sound:** what audiovisual language realizes it?
- **Production:** how is each asset made?
- **Editor:** what exact experience emerges over time?
- **Continuity:** does the world remain coherent?
- **QC:** is it actually finished?
