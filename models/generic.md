# Generic model adapter

Any AI model may operate clipme if it follows this contract.

## Read order
1. AGENTS.md
2. selected profile
3. relevant skill/SKILL.md
4. docs/architecture.md
5. docs/directing-language.md
6. current project packet only

## Requirements
The model must:
- preserve stable IDs
- write structured artifacts before expensive generation
- distinguish facts from creative invention
- respect locked artifacts
- emit dependency impact when changing locked work
- use manifests for external/generated assets
- pass work to QC instead of self-declaring quality

## Capability fallback
If a model cannot:
- inspect images/video → assign visual QC elsewhere
- browse/verify → mark claims unverified and request a verification pass
- call tools → produce tool-ready manifests, not fabricated execution reports
- maintain long context → work sequence-by-sequence with bounded context packets

## Forbidden behavior
- claiming a file/render/API call exists when it was not executed
- silently changing locked story/continuity
- inventing sources or licenses
- skipping blocking QC
