#!/usr/bin/env python3
"""Reference production 01 — infographic.

Drives clipme's real service + provider stack end to end and produces one
actual, playable MP4 file, with no AI/LLM provider involved:

    create_project -> validate_project -> plan_project
    -> complete_task (loop until the plan is done)
    -> synthesize N deterministic "infographic" video segments with ffmpeg
       (lavfi `color` source + `subtitles` text overlay — see NOTE below)
    -> populate the render manifest
    -> core.providers.FFmpegRenderAdapter (wraps core.service.assemble_project)
       to concatenate the segments into one master MP4.

NOTE on drawtext vs subtitles: the Mission Letter's own wording suggested
ffmpeg's `drawtext` filter for the text overlay. On THIS machine's ffmpeg
build (the static binary installed by scripts/bootstrap.sh, see
`ffmpeg -h filter=drawtext`) drawtext is genuinely unavailable ("Unknown
filter 'drawtext'") even though libfreetype is compiled in — this was
verified by actually running it, not assumed. `subtitles` (libass, which
IS compiled in) produces the same deterministic text-over-color-card result
and is used instead. If a different ffmpeg build with drawtext is ever used
here, swapping SEGMENT_FILTER back to a drawtext expression is a one-line
change (see `_segment_filter`).

Fully reproducible: run this script alone, nothing else required, as long
as ffmpeg/ffprobe are on PATH (see scripts/bootstrap.sh).

Usage:
    python3 examples/reference-production-01-infographic/run.py
    # or, with a specific project workspace:
    python3 examples/reference-production-01-infographic/run.py /path/to/workdir
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core import service  # noqa: E402
from core.providers import FFmpegRenderAdapter  # noqa: E402

PROFILE = "short-90s"
TITLE = "Reference Infographic"
LANGUAGE = "en"
WIDTH, HEIGHT, FPS = 640, 360, 24  # kept small deliberately: this pipeline runs
# on shared, memory-constrained dev machines; nothing here needs HD frames to
# prove the service+provider stack produces a real MP4.

# Three color-card "slides" -> one real MP4, 15s each = 45s total (within the
# short-90s profile's 15-90s window and the Mission Letter's 30-60s target).
SEGMENTS = [
    {"id": "shot-01", "color": "0x2E5EAA", "text": "clipme reference production\\nInfographic 01", "seconds": 15},
    {"id": "shot-02", "color": "0x2E9E5B", "text": "Service layer -> Provider registry\\n-> FFmpegRenderAdapter", "seconds": 15},
    {"id": "shot-03", "color": "0xAA4A2E", "text": "Real MP4, no AI provider needed\\nverify with ffprobe", "seconds": 15},
]


def _segment_filter(srt_path: Path) -> str:
    """The video filter used for each segment. See module docstring NOTE:
    `subtitles` is used instead of `drawtext` because this machine's ffmpeg
    build does not have drawtext compiled in (verified with
    `ffmpeg -h filter=drawtext` -> "Unknown filter 'drawtext'")."""
    escaped = str(srt_path).replace("\\", "\\\\").replace(":", "\\:")
    return f"subtitles={escaped}"


def _write_srt(path: Path, text: str, seconds: int) -> None:
    # single subtitle cue spanning the whole segment
    end = f"00:00:{seconds:02d},000"
    path.write_text(
        "1\n00:00:00,000 --> " + end + "\n" + text.replace("\\n", "\n") + "\n",
        encoding="utf-8",
    )


def _run_pipeline_until_complete(project_dir: Path, max_iterations: int = 50) -> int:
    """Drive the orchestrator to completion purely through core.service.*
    calls, standing in for real per-skill AI/tool execution (there is no real
    executor wired for producer/story tasks in this repo yet — see the Gap
    Analysis's blocks_provider_execution section) by recording each ready
    task complete with a message that says so explicitly. Returns the number
    of tasks completed."""
    completed = 0
    for _ in range(max_iterations):
        ready = service.get_ready_tasks(project_dir)
        if ready["complete"] or not ready["ready"]:
            break
        for task in ready["ready"]:
            service.complete_task(
                project_dir,
                task["id"],
                message="reference-production-01: mock completion, no AI provider called for this task kind",
            )
            completed += 1
    return completed


def _synthesize_segments(project_dir: Path) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise service.BinaryNotFoundError("ffmpeg not found in PATH")
    shots_dir = project_dir / "renders" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="clipme-ref-prod-") as td:
        for seg in SEGMENTS:
            srt_path = Path(td) / f"{seg['id']}.srt"
            _write_srt(srt_path, seg["text"], seg["seconds"])
            out_path = shots_dir / f"{seg['id']}.mp4"
            import subprocess

            subprocess.run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i",
                    f"color=c={seg['color']}:s={WIDTH}x{HEIGHT}:d={seg['seconds']}:r={FPS}",
                    "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
                    "-vf", _segment_filter(srt_path),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000",
                    "-shortest", "-t", str(seg["seconds"]),
                    str(out_path),
                ],
                check=True,
            )
            outputs.append(out_path)
    return outputs


def main(project_dir: str | Path | None = None) -> Path:
    workdir = Path(project_dir) if project_dir else EXAMPLE_DIR / "work" / "project"
    if workdir.exists():
        shutil.rmtree(workdir)

    total_seconds = sum(s["seconds"] for s in SEGMENTS)
    service.create_project(
        workdir, PROFILE, title=TITLE, language=LANGUAGE,
        duration=float(total_seconds), width=WIDTH, height=HEIGHT, fps=float(FPS),
    )
    service.validate_project(workdir)
    plan = service.plan_project(workdir)
    print(f"planned {plan['task_count']} task(s): {plan['activation_counts']}")

    completed = _run_pipeline_until_complete(workdir)
    print(f"completed {completed} task(s) via mock completion (no AI provider called)")

    segment_paths = _synthesize_segments(workdir)
    print(f"synthesized {len(segment_paths)} deterministic segment(s) via ffmpeg")

    manifest_path = workdir / "manifests" / "render_manifest.json"
    manifest = service._load_data(manifest_path)  # noqa: SLF001 - example glue, not core logic
    manifest["segments"] = [str(p.relative_to(workdir)) for p in segment_paths]
    manifest["output"] = "masters/master.mp4"
    service._write_json(manifest_path, manifest)  # noqa: SLF001

    adapter = FFmpegRenderAdapter()
    result = adapter.render({"project_dir": workdir})
    output_path = Path(result["output"])
    print(f"assembled master: {output_path} (executed={result['executed']})")
    return output_path


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    out = main(arg)
    print(f"\nDone. Verify with:\n  ffprobe -v error -show_format -show_streams {out}")
