# Adaptive orchestration

clipme uses a small microkernel so the production system grows with the work instead of forcing every project through a feature-film pipeline.

## 1. Two graphs

### Unit graph

The creative hierarchy:

Project → Act/Chapter → Sequence → Scene → Beat → Shot → Frame/Audio Event

Stored in:

\`manifests/unit_graph.json\`

Units may skip levels when the profile allows it. A short may go directly from Project to Sequence/Scene/Beat/Shot. A film can use the full hierarchy.

### Task DAG

The executable production workflow created from:

- project profile
- project features
- unit graph
- skill manifests
- hard dependencies
- optional ordering constraints

Stored in:

\`manifests/production_plan.json\`

Runtime state is stored in:

\`manifests/task_state.json\`

## 2. Skill activation

Every skill has one of four states:

- \`required\` — scheduled as an explicit task
- \`inline\` — scheduled, but expected to be lightweight and may share the lead model/context
- \`optional\` — available but not scheduled automatically
- \`skip\` — disabled unless another active skill requires it

Only \`required\` and \`inline\` become executable tasks by default.

This is the main mechanism that keeps small work small.

## 3. Features

Projects can explicitly describe production needs:

\`\`\`yaml
features:
  factual: true
  narration: true
  infographic: true
  characters: false
  dialogue: false
  complex_action: false
  generated_video: false
  captions: true
\`\`\`

Skill manifests upgrade themselves when relevant features are present.

Examples:

- \`factual\` activates research
- \`characters\` / \`dialogue\` activates performance
- \`generated_video\` activates cinematography and motion/VFX
- \`captions\` activates accessibility/delivery

## 4. Overrides

A project can override activation without changing global skills:

\`\`\`yaml
skill_overrides:
  storyboard: required
  color-finishing: skip
\`\`\`

A hard dependency cannot be forced to skip while a dependent skill remains active.

## 5. Progressive planning

A new project initially contains only the Project unit.

Therefore only tasks that can operate at that stage are scheduled.

Typical bootstrap:

\`\`\`text
Producer
  ↓
Story
\`\`\`

Story creates/updates the unit graph. Run \`plan\` again.

Then new tasks appear only where units now exist:

\`\`\`text
Sequence
  ↓
Director
  ├─ Storyboard
  ├─ Cinematography
  ├─ Production Design
  └─ Sound
       ↓
Shot production
       ↓
Editor
       ↓
Continuity
       ↓
QC
\`\`\`

Re-planning preserves state for task IDs that still exist.

## 6. Hard vs soft dependencies

Skill manifests use:

\`requires\`
: hard dependency. If its task cannot yet exist, downstream work is deferred.

\`after_if_active\`
: ordering dependency only when that other skill is active.

This prevents optional skills from forcing themselves into small projects.

Example:

Editor can wait for Motion/VFX and Sound **if those skills are active**, without forcing them to exist for every silent/simple project.

## 7. CLI

Create:

\`\`\`bash
python clipme.py init work/demo --profile short-90s --duration 60
\`\`\`

Edit \`project.yaml\`, then:

\`\`\`bash
python clipme.py validate work/demo
python clipme.py plan work/demo
python clipme.py next work/demo
\`\`\`

An external AI/provider runner completes the ready task and records its artifacts:

\`\`\`bash
python clipme.py complete work/demo producer@DEMO --artifact bibles/brief.yaml
\`\`\`

\`complete\`/\`fail\` on an unknown task id print \`ERROR: unknown task: <id>\`
to stderr and exit \`2\` (via \`core/service.py\`'s \`TaskNotFoundError\`, caught
at the CLI boundary). This is an intentional fix: prior to the service-layer
refactor this path raised an unhandled \`KeyError\` traceback and exited \`1\`.
Any caller (script, CI, or the HTTP API's own client) matching on the old
traceback text or exit code \`1\` for this specific case should be updated.

Inspect state:

\`\`\`bash
python clipme.py status work/demo
\`\`\`

After structural artifacts expand the unit graph, run:

\`\`\`bash
python clipme.py plan work/demo
\`\`\`

again.

## 8. Assurance separation

Creator skills generate.

Assurance skills check.

The master must not rely only on the creator's self-review.

Research, continuity and QC are marked as assurance skills in their manifests.

## 9. Scaling principle

The kernel remains small.

Complexity comes from the graph, not from adding a new orchestration system for every duration.

\`\`\`text
small job
→ few units
→ few active skills
→ few tasks

large job
→ many hierarchical units
→ more required skills
→ many bounded tasks
→ local QC + global assembly
\`\`\`
