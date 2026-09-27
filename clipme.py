#!/usr/bin/env python3
"""clipme minimal production runtime.

This runtime does not choose creative AI providers. It creates/validates the
shared project workspace and assembles already-rendered units into one master.
Provider adapters can be added without changing the core project contracts.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
PROFILES = ROOT / "profiles"


def die(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_data(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def validate_json_schema(data, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(x) for x in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


def cmd_init(args) -> None:
    dest = Path(args.directory).resolve()
    if dest.exists() and any(dest.iterdir()):
        die(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    profile_path = PROFILES / f"{args.profile}.yaml"
    if not profile_path.exists():
        die(f"unknown profile: {args.profile}")

    for rel in [
        "sources", "bibles", "story", "sequences", "scenes", "shots",
        "assets", "audio", "renders/shots", "renders/sequences",
        "renders/reels", "manifests", "qc", "masters"
    ]:
        (dest / rel).mkdir(parents=True, exist_ok=True)

    project = {
        "id": args.id or dest.name.upper().replace("-", "_"),
        "title": args.title or dest.name,
        "profile": args.profile,
        "language": args.language,
        "audience": "",
        "intent": {
            "promise": "",
            "core_question": "",
            "desired_viewer_change": "",
            "tone": "",
            "genre": ""
        },
        "duration": {
            "target_seconds": args.duration
        },
        "delivery": {
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "channels": 2
        },
        "constraints": {},
        "source_refs": [],
        "bible_refs": []
    }
    write_yaml(dest / "project.yaml", project)

    (dest / "manifests" / "render_manifest.json").write_text(
        json.dumps({
            "project_id": project["id"],
            "segments": [],
            "output": "masters/master.mp4"
        }, indent=2),
        encoding="utf-8"
    )
    (dest / "qc" / "qc_report.json").write_text(
        json.dumps({"scope": "master", "status": "FAIL", "checks": []}, indent=2),
        encoding="utf-8"
    )
    print(f"Initialized clipme project: {dest}")
    print(f"Profile: {args.profile}")


def cmd_validate(args) -> None:
    project_dir = Path(args.project).resolve()
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        die(f"missing {project_path}")

    project = load_data(project_path)
    errors = validate_json_schema(project, SCHEMAS / "project.schema.json")

    shot_errors = []
    for shot_path in sorted((project_dir / "shots").glob("*.json")):
        data = load_data(shot_path)
        for err in validate_json_schema(data, SCHEMAS / "shot.schema.json"):
            shot_errors.append(f"{shot_path.name}: {err}")

    if errors or shot_errors:
        for e in errors + shot_errors:
            print(f"FAIL {e}")
        raise SystemExit(1)

    print("PASS project and shot contracts")


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"{name} not found in PATH")
    return path


def cmd_probe(args) -> None:
    ffprobe = require_binary("ffprobe")
    media = Path(args.media).resolve()
    if not media.exists():
        die(f"media not found: {media}")
    proc = subprocess.run(
        [
            ffprobe, "-v", "error",
            "-show_format", "-show_streams",
            "-of", "json", str(media)
        ],
        check=True,
        capture_output=True,
        text=True
    )
    info = json.loads(proc.stdout)
    print(json.dumps(info, indent=2))


def ffconcat_quote(path: Path) -> str:
    # concat demuxer single-quote escaping
    s = str(path.resolve()).replace("'", "'\\''")
    return f"file '{s}'"


def cmd_assemble(args) -> None:
    ffmpeg = require_binary("ffmpeg")
    project_dir = Path(args.project).resolve()
    manifest_path = project_dir / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    segments = manifest.get("segments") or []
    if not segments:
        die("render manifest has no segments")

    paths = []
    for item in segments:
        rel = item["path"] if isinstance(item, dict) else item
        p = (project_dir / rel).resolve()
        if not p.exists():
            die(f"missing segment: {p}")
        paths.append(p)

    output_rel = args.output or manifest.get("output") or "masters/master.mp4"
    output = (project_dir / output_rel).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="clipme-") as td:
        listfile = Path(td) / "concat.txt"
        listfile.write_text("\n".join(ffconcat_quote(p) for p in paths) + "\n", encoding="utf-8")
        cmd = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000",
            "-movflags", "+faststart",
            str(output)
        ]
        subprocess.run(cmd, check=True)

    print(f"Master assembled: {output}")


def cmd_gate(args) -> None:
    project_dir = Path(args.project).resolve()
    qc_path = project_dir / args.qc
    data = json.loads(qc_path.read_text(encoding="utf-8"))
    errors = validate_json_schema(data, SCHEMAS / "qc.schema.json")
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        raise SystemExit(1)
    blocking = [
        c for c in data.get("checks", [])
        if c.get("status") == "FAIL" and c.get("severity") == "blocking"
    ]
    if data.get("status") != "PASS" or blocking:
        print("FAIL master is not releasable")
        for c in blocking:
            print(f"- {c.get('gate')}: {c.get('repair','repair required')}")
        raise SystemExit(1)
    print("PASS master release gate")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clipme")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create a clipme project workspace")
    s.add_argument("directory")
    s.add_argument("--profile", default="short-90s",
                   choices=["short-90s", "explainer", "longform", "film"])
    s.add_argument("--title")
    s.add_argument("--id")
    s.add_argument("--language", default="th")
    s.add_argument("--duration", type=float, default=60.0)
    s.add_argument("--width", type=int, default=1920)
    s.add_argument("--height", type=int, default=1080)
    s.add_argument("--fps", type=float, default=30.0)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("validate", help="validate project and shot contracts")
    s.add_argument("project")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("probe", help="ffprobe a rendered media file")
    s.add_argument("media")
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("assemble", help="assemble ordered rendered segments into one master")
    s.add_argument("project")
    s.add_argument("--manifest", default="manifests/render_manifest.json")
    s.add_argument("--output")
    s.set_defaults(func=cmd_assemble)

    s = sub.add_parser("gate", help="require a valid PASS QC report before release")
    s.add_argument("project")
    s.add_argument("--qc", default="qc/qc_report.json")
    s.set_defaults(func=cmd_gate)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
