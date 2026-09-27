# Provider adapters

clipme separates **creative semantics** from **provider execution**.

A provider can be replaced without changing the story/shot/QC contracts.

## Adapter classes

### LLM
Consumes skill packet and structured project artifacts.
Returns structured artifacts/repair actions.

### TTS / voice
Input:
- text
- language
- voice direction
- segment ID

Output:
- audio file
- measured duration
- provider/model/version
- optional voice ID
- asset manifest record

### Image
Input:
- shot/asset purpose
- art/continuity packet
- dimensions
- prompt/negative constraints

Output:
- image
- generation metadata
- provenance record

### Video
Input:
- shot contract
- start/end visual state
- motion/blocking
- duration
- continuity packet

Output:
- shot clip
- generation metadata
- provenance record

### Music/SFX
Must return provenance/license metadata and intended cue range.

### Renderer
Examples:
- HTML/SVG/Canvas/WebGL
- Remotion
- Blender
- NLE scripting
- FFmpeg compositing

Renderer output must be deterministic where practical and must conform to project delivery specs.

## Environment variables
Secrets belong in environment variables or secret stores.
Never write API keys into project artifacts or prompts committed to git.

## Provider quality rule
Provider convenience never overrides:
- continuity
- factual integrity
- asset rights
- delivery specs
- QC gates
