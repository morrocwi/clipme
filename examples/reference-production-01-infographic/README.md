# Reference production 01 — infographic

Demonstrates the full `core.service` + `core.providers` pipeline producing a
real, playable MP4 — no AI/LLM provider call is used or needed for this
example.

## What it does

`run.py` drives the stack end to end using nothing but public functions from
`core.service` and `core.providers` (no argparse, no CLI subprocess calls):

1. `service.create_project(...)` — scaffolds a fresh project using the
   `short-90s` profile (`profiles/short-90s.yaml`, 15-90s duration window).
2. `service.validate_project(...)` — runs the full schema/profile/graph/
   reference/skill-registry/task-DAG validation chain.
3. `service.plan_project(...)` — builds the adaptive task DAG. On a bare
   project root only the producer/story tasks activate (see the Gap
   Analysis's `executable_now` section).
4. `service.complete_task(...)` in a loop until the plan is done — there is
   no real AI/tool executor wired for producer/story task kinds yet (see the
   Gap Analysis's `blocks_provider_execution`), so each ready task is
   recorded complete with a message that says explicitly no provider was
   called. This is example glue standing in for real per-skill execution,
   not a claim that these tasks were "really" done.
5. Three deterministic video segments (15s each, 45s total) are synthesized
   directly with `ffmpeg` (`color` lavfi source + `subtitles` text overlay +
   a silent `anullsrc` audio track) into `renders/shots/shot-0{1,2,3}.mp4`.
6. The render manifest (`manifests/render_manifest.json`) is populated with
   those three segments.
7. `core.providers.FFmpegRenderAdapter().render({"project_dir": ...})` is
   called — this wraps `core.service.assemble_project`'s existing ffmpeg
   concat logic (no duplicate ffmpeg command-building code) — producing
   `masters/master.mp4`.

## Note: drawtext vs subtitles (verified, not assumed)

The Mission Letter's wording pointed at ffmpeg's `drawtext` filter for the
text overlay. On this machine's ffmpeg build (the static binary
`scripts/bootstrap.sh` installs), `drawtext` is genuinely unavailable —
confirmed by actually running `ffmpeg -h filter=drawtext`, which reports
`Unknown filter 'drawtext'`, even though `libfreetype` is compiled in.
`subtitles` (backed by `libass`, which IS compiled in) produces the same
deterministic text-over-color-card effect and is used instead. If a
different ffmpeg build with `drawtext` support is used, swapping the filter
back is a one-line change in `run.py`'s `_segment_filter()`.

## Running it

```bash
PATH="$(pwd)/bin:$PATH" python3 examples/reference-production-01-infographic/run.py
```

(Requires `ffmpeg`/`ffprobe` on PATH — run `scripts/bootstrap.sh` first if
they are not yet available; see the repo's `bin/` shim.)

The project workspace is created fresh under
`examples/reference-production-01-infographic/work/project/` (gitignored —
`work/`, `renders/` and `masters/` are all in `.gitignore`) each time the
script runs, so it is fully reproducible from the script alone. The
committed `project.yaml` in this directory is a documentation-only reference
copy of the config `create_project` generates at runtime; `run.py` does not
read it.

## Expected output

```
work/project/masters/master.mp4
```

- Duration: ~45 seconds (three 15s segments)
- Resolution: 640x360 (kept small deliberately for memory-constrained dev
  machines — nothing about this example needs HD frames to prove the
  pipeline works end to end)
- Video codec: h264, audio codec: aac (silent track)

Verify with:

```bash
ffprobe -v error -show_format -show_streams \
  examples/reference-production-01-infographic/work/project/masters/master.mp4
```

**VERIFIED** (run on this machine, this session): the produced file reported
`duration=45.041667`, `width=640`, `height=360`, one h264 video stream and
one aac audio stream.

## Prerequisites

This example requires `core/service.py`, `core/providers.py` and
`scripts/bootstrap.sh` (ffmpeg/ffprobe on PATH) to already exist in this
repo. If any of those are missing, this example cannot run.
