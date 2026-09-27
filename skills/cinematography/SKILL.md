# Skill: cinematography

## Purpose
Create a coherent image language for generated, animated, composited, or captured footage.

## Inputs
- director shot contract
- visual bible
- locations/world bible
- continuity state
- render/generation capabilities

## Outputs
- framing/composition
- lens/FOV intent
- camera height/angle/distance
- camera movement
- depth/focus strategy
- lighting description
- exposure/contrast intention
- color temperature/palette relation
- texture/image-character notes
- continuity anchors for adjacent shots

## Synthetic lens semantics
Even without a physical camera, preserve photographic semantics:
- wide = spatial inclusion / perspective exaggeration
- normal = natural spatial relation
- long = compression / isolation
- macro = tactile detail
- shallow focus = attention isolation
- deep focus = simultaneous relationships

## Continuity checks
Track:
- key-light direction
- time of day
- weather
- dominant palette
- background geography
- subject orientation
- shot/reverse-shot eyelines
- motion direction

## Gate
Fail when adjacent shots unintentionally change world lighting, geography, or subject orientation.
