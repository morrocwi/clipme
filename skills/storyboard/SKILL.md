# Skill: storyboard-previs

## Purpose
Test spatial, compositional, temporal, and transition decisions before expensive final asset generation.

## Inputs
- director shot list
- continuity entities/states
- visual bible
- dialogue/VO draft
- target aspect ratio/fps

## Outputs
- storyboard panel set
- panel-to-shot mapping
- blocking diagrams where needed
- camera path notes
- approximate timing
- animatic/previs plan
- expensive-shot risk list
- unresolved geography/continuity tickets

## Required panel information
- shot ID
- frame composition
- subject positions
- screen direction
- gaze direction if relevant
- camera move arrow/path
- principal action
- dialogue/VO cue
- transition cue
- approximate duration

## Synthetic-production optimization
Use low-cost vector/blocking renders first.
Do not spend final image/video-generation budget until:
- geography works,
- eyelines work,
- shot order works,
- transitions work,
- sequence timing is plausible.

## Gate
Fail if action geography is ambiguous when comprehension depends on it.
Fail if consecutive shots contradict screen direction without an intentional axis reset/cross.
