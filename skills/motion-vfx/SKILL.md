# Skill: motion-animation-vfx

## Purpose
Create explanatory motion, animation, compositing, simulation, visual effects, and synthetic shot construction.

## Inputs
- shot contract
- art/visual bible
- storyboard/previs
- continuity state
- asset manifest

## Outputs
- animation plan
- layer/composite plan
- simulation/generation plan
- key timing
- masks/tracks where applicable
- rendered shot
- effect-specific QC notes

## Preference order
Use the simplest controllable method that communicates correctly:
1. typography/vector/code
2. 2D compositing/animation
3. 3D/simulation
4. generated still + motion
5. generated video
6. hybrid

Do not use a generative-video model for deterministic charts, labels, maps, UI, diagrams, or precise text when code/vector tools are better.

## Motion meaning
Movement should encode:
- causality
- sequence
- comparison
- quantity
- hierarchy
- transformation
- focus
- transition

## Gate
Fail for unreadable motion, temporal aliasing, broken masks/composites, geometry/text corruption, or continuity-breaking generated motion.
