# Skill: qc

## Purpose
Decide whether a production unit is fit to advance, and create precise repair tickets when it is not.

## Inputs
- creative contracts
- rendered media
- fact ledger
- manifests
- delivery spec
- continuity state

## Outputs
- qc_report.json
- pass/fail by gate
- timestamps/frame ranges
- severity
- likely root cause
- smallest affected unit
- repair instruction
- rerender scope

## Blocking gates
### FACT
Unsupported or contradicted factual claim.

### STORY
Missing logic, broken setup/payoff, incoherent scene/sequence.

### DIRECTION
Unmotivated/contradictory shot grammar severe enough to harm comprehension.

### CONTINUITY
Contradictory persistent state or geography.

### READABILITY
Required text cannot be read reliably.

### AUDIO
Unintelligible speech, clipping, dropout, broken sync.

### VISUAL
Missing asset, corrupted frame, severe generation artifact.

### RIGHTS
Unknown or disallowed provenance.

### TECH
Wrong dimensions/fps/codec/channel layout, broken timestamps, frozen/black output, mux/render failure.

## Non-blocking polish
- micro timing
- minor aesthetic alternatives
- optional embellishment

## Review strategy
Prefer a reviewer independent from the generating pass.
For long works, run:
1. shot/scene QC
2. sequence QC
3. act/reel QC
4. master-wide QC

## Gate
Only QC may issue final PASS for the master.
