#!/usr/bin/env python3
"""clipme runtime and orchestration control plane.

Creative AI/provider execution is injected around a small deterministic kernel.
The kernel owns profiles, unit/skill graphs, task state, validation, assembly and
release gating so short work can stay small while long work can scale safely.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from core import (
    GraphValidator,
    Orchestrator,
    Planner,
    ProfileValidator,
    ReferenceValidator,
    SkillRegistry,
    Task,
    TaskGraphValidator,
    TaskState,
    UnitGraph,
)

ROOT = Path(__file__).resolve().parent
SCHEMAS = ROOT / "schemas"
PROFILES = ROOT / "profiles"
SKILLS = ROOT / "skills"


def die(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_data(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: Any) -> None:
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


def load_profile(profile_id: str) -> dict[str, Any]:
    path = PROFILES / f"{profile_id}.yaml"
    if not path.exists():
        die(f"unknown profile: {profile_id}")
    return load_data(path)


def load_unit_graph(project_dir: Path, project: dict[str, Any]) -> UnitGraph:
    path = project_dir / "manifests" / "unit_graph.json"
    if not path.exists():
        data = {"units": [{"id": project["id"], "kind": "project", "parent": None, "children": []}]}
        write_json(path, data)
    return UnitGraph.from_dict(load_data(path))


def load_docs(directory: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not directory.exists():
        return docs
    seen: set[Path] = set()
    for pattern in ("*.yaml", "*.yml", "*.json"):
        for path in sorted(directory.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            docs.append(load_data(path))
    return docs


def cmd_init(args) -> None:
    dest = Path(args.directory).resolve()
    if dest.exists() and any(dest.iterdir()):
        die(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    load_profile(args.profile)

    for rel in [
        "sources", "bibles", "story", "sequences", "scenes", "beats", "shots",
        "assets", "audio", "renders/shots", "renders/sequences", "renders/reels",
        "manifests", "qc", "masters"
    ]:
        (dest / rel).mkdir(parents=True, exist_ok=True)

    project_id = args.id or dest.name.upper().replace("-", "_")
    project = {
        "id": project_id,
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
        "duration": {"target_seconds": args.duration},
        "delivery": {
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "channels": 2
        },
        "features": {},
        "skill_overrides": {},
        "constraints": {},
        "source_refs": [],
        "bible_refs": []
    }
    write_yaml(dest / "project.yaml", project)
    write_json(dest / "manifests" / "unit_graph.json", {
        "units": [{"id": project_id, "kind": "project", "parent": None, "children": []}]
    })
    write_json(dest / "manifests" / "render_manifest.json", {
        "project_id": project_id,
        "segments": [],
        "output": "masters/master.mp4"
    })
    write_json(dest / "qc" / "qc_report.json", {"scope": "master", "status": "FAIL", "checks": []})
    print(f"Initialized clipme project: {dest}")
    print(f"Profile: {args.profile}")
    print("Next: edit project.yaml features/brief, then run 'clipme.py plan <project>'.")


def collect_fact_ids(project_dir: Path) -> set[str] | None:
    path = project_dir / "bibles" / "fact_ledger.json"
    if not path.exists():
        path = project_dir / "fact_ledger.json"
    if not path.exists():
        return None
    data = load_data(path)
    return {f.get("fact_id") for f in data.get("facts", []) if f.get("fact_id")}


def collect_asset_ids(project_dir: Path) -> set[str] | None:
    path = project_dir / "manifests" / "asset_manifest.json"
    if not path.exists():
        return None
    data = load_data(path)
    rows = data.get("assets", data if isinstance(data, list) else [])
    return {a.get("asset_id") for a in rows if isinstance(a, dict) and a.get("asset_id")}


def cmd_validate(args) -> None:
    project_dir = Path(args.project).resolve()
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        die(f"missing {project_path}")

    failures: list[str] = []
    project = load_data(project_path)
    for err in validate_json_schema(project, SCHEMAS / "project.schema.json"):
        failures.append(f"project.yaml: {err}")

    profile = load_profile(project["profile"])
    for issue in ProfileValidator().validate(project, profile):
        failures.append(f"{issue.code}: {issue.message}")

    graph_path = project_dir / "manifests" / "unit_graph.json"
    if graph_path.exists():
        graph_data = load_data(graph_path)
        for err in validate_json_schema(graph_data, SCHEMAS / "unit.schema.json"):
            failures.append(f"manifests/unit_graph.json: {err}")
        graph = UnitGraph.from_dict(graph_data)
        for issue in GraphValidator().validate(graph, profile):
            failures.append(f"{issue.code}: {issue.message}")
    else:
        graph = load_unit_graph(project_dir, project)

    registry = SkillRegistry.load(SKILLS)
    for skill_dir in sorted(SKILLS.iterdir()):
        manifest = skill_dir / "skill.yaml"
        if manifest.exists():
            for err in validate_json_schema(load_data(manifest), SCHEMAS / "skill.schema.json"):
                failures.append(f"{manifest.relative_to(ROOT)}: {err}")

    def validate_globs(directory: str, schema_name: str) -> list[dict[str, Any]]:
        docs = load_docs(project_dir / directory)
        for doc in docs:
            for err in validate_json_schema(doc, SCHEMAS / schema_name):
                failures.append(f"{directory}: {err}")
        return docs

    sequences = validate_globs("sequences", "sequence.schema.json")
    scenes = validate_globs("scenes", "scene.schema.json")
    shots = validate_globs("shots", "shot.schema.json")

    timeline_path = project_dir / "manifests" / "timeline.json"
    timeline = load_data(timeline_path) if timeline_path.exists() else None
    if timeline is not None:
        for err in validate_json_schema(timeline, SCHEMAS / "timeline.schema.json"):
            failures.append(f"manifests/timeline.json: {err}")

    for issue in ReferenceValidator().validate_documents(
        graph, sequences, scenes, shots, timeline,
        facts=collect_fact_ids(project_dir), assets=collect_asset_ids(project_dir)
    ):
        failures.append(f"{issue.code}: {issue.message}")

    tasks = Planner(registry).build_tasks(project, graph)
    for issue in TaskGraphValidator().validate(tasks, registry):
        failures.append(f"{issue.code}: {issue.message}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("PASS schemas, profile, unit graph, references, skill registry and task DAG")


def cmd_plan(args) -> None:
    project_dir = Path(args.project).resolve()
    project = load_data(project_dir / "project.yaml")
    profile = load_profile(project["profile"])
    graph = load_unit_graph(project_dir, project)
    graph_issues = GraphValidator().validate(graph, profile)
    if graph_issues:
        for issue in graph_issues:
            print(f"FAIL {issue.code}: {issue.message}")
        raise SystemExit(1)

    registry = SkillRegistry.load(SKILLS)
    planner = Planner(registry)
    plan = planner.plan(project, graph)
    task_objects = [Task.from_dict(t) for t in plan["tasks"]]
    task_issues = TaskGraphValidator().validate(task_objects, registry)
    if task_issues:
        for issue in task_issues:
            print(f"FAIL {issue.code}: {issue.message}")
        raise SystemExit(1)

    plan_path = project_dir / "manifests" / "production_plan.json"
    write_json(plan_path, plan)

    state_path = project_dir / "manifests" / "task_state.json"
    previous = load_data(state_path).get("tasks", {}) if state_path.exists() else {}
    states: dict[str, TaskState] = {}
    for task in task_objects:
        if task.id in previous:
            states[task.id] = TaskState.from_dict(previous[task.id])
        else:
            states[task.id] = TaskState(task_id=task.id)
    orch = Orchestrator(task_objects, states)
    write_json(state_path, orch.snapshot())

    counts: dict[str, int] = {}
    for status in plan["activation"].values():
        counts[status] = counts.get(status, 0) + 1
    print(f"Planned {len(task_objects)} executable tasks for {project['profile']}")
    print("Activation:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Plan: {plan_path}")
    print(f"State: {state_path}")


def load_orchestrator(project_dir: Path) -> tuple[Orchestrator, Path]:
    plan_path = project_dir / "manifests" / "production_plan.json"
    state_path = project_dir / "manifests" / "task_state.json"
    if not plan_path.exists():
        die("missing production plan; run 'plan' first")
    plan = load_data(plan_path)
    tasks = [Task.from_dict(t) for t in plan.get("tasks", [])]
    states: dict[str, TaskState] = {}
    if state_path.exists():
        raw = load_data(state_path).get("tasks", {})
        task_ids = {t.id for t in tasks}
        states = {task_id: TaskState.from_dict(data) for task_id, data in raw.items() if task_id in task_ids}
    orch = Orchestrator(tasks, states)
    return orch, state_path


def cmd_next(args) -> None:
    project_dir = Path(args.project).resolve()
    orch, state_path = load_orchestrator(project_dir)
    ready = [t.to_dict() for t in orch.ready_tasks()]
    write_json(state_path, orch.snapshot())
    print(json.dumps({"ready": ready, "complete": orch.is_complete()}, indent=2, ensure_ascii=False))


def cmd_complete(args) -> None:
    project_dir = Path(args.project).resolve()
    orch, state_path = load_orchestrator(project_dir)
    orch.complete_external(args.task_id, artifacts=args.artifact or [], message=args.message or "")
    write_json(state_path, orch.snapshot())
    print(f"PASS task {args.task_id}")
    print(f"New ready tasks: {len(orch.ready_tasks())}")


def cmd_fail(args) -> None:
    project_dir = Path(args.project).resolve()
    orch, state_path = load_orchestrator(project_dir)
    orch.mark_failed_external(args.task_id, args.message)
    write_json(state_path, orch.snapshot())
    print(f"FAIL task {args.task_id}: {args.message}")


def cmd_status(args) -> None:
    project_dir = Path(args.project).resolve()
    orch, state_path = load_orchestrator(project_dir)
    write_json(state_path, orch.snapshot())
    counts: dict[str, int] = {}
    for state in orch.states.values():
        counts[state.status.value] = counts.get(state.status.value, 0) + 1
    print(json.dumps({"counts": counts, "complete": orch.is_complete()}, indent=2))


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
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        check=True, capture_output=True, text=True
    )
    print(json.dumps(json.loads(proc.stdout), indent=2))


def ffconcat_quote(path: Path) -> str:
    s = str(path.resolve()).replace("'", "'\\''")
    return f"file '{s}'"


def cmd_assemble(args) -> None:
    ffmpeg = require_binary("ffmpeg")
    project_dir = Path(args.project).resolve()
    manifest_path = project_dir / args.manifest
    manifest = load_data(manifest_path)
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
        subprocess.run([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
            "-movflags", "+faststart", str(output)
        ], check=True)
    print(f"Master assembled: {output}")


def cmd_gate(args) -> None:
    project_dir = Path(args.project).resolve()
    qc_path = project_dir / args.qc
    data = load_data(qc_path)
    errors = validate_json_schema(data, SCHEMAS / "qc.schema.json")
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        raise SystemExit(1)

    project = load_data(project_dir / "project.yaml")
    profile = load_profile(project["profile"])
    required_gates = set((profile.get("qc") or {}).get("required_gates", []))
    if not required_gates:
        required_gates = {"STORY", "DIRECTION", "CONTINUITY", "READABILITY", "AUDIO", "VISUAL", "RIGHTS", "TECH"}
        if "factual" in {k for k, v in (project.get("features") or {}).items() if v} or project.get("source_refs"):
            required_gates.add("FACT")

    checks = data.get("checks", [])
    by_gate: dict[str, list[dict[str, Any]]] = {}
    for check in checks:
        by_gate.setdefault(check.get("gate"), []).append(check)

    missing = sorted(g for g in required_gates if g not in by_gate)
    failing = [c for c in checks if c.get("status") == "FAIL" and c.get("severity") in {"blocking", "major"}]
    unpassed = sorted(g for g in required_gates if g in by_gate and not all(c.get("status") in {"PASS", "NA"} for c in by_gate[g]))

    if data.get("status") != "PASS" or missing or failing or unpassed:
        print("FAIL master is not releasable")
        if missing:
            print("- missing required QC gates:", ", ".join(missing))
        if unpassed:
            print("- required QC gates not PASS/NA:", ", ".join(unpassed))
        for c in failing:
            print(f"- {c.get('gate')}: {c.get('repair', 'repair required')}")
        raise SystemExit(1)
    print("PASS master release gate")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clipme")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create a clipme project workspace")
    s.add_argument("directory")
    s.add_argument("--profile", default="short-90s", choices=["short-90s", "explainer", "longform", "film"])
    s.add_argument("--title")
    s.add_argument("--id")
    s.add_argument("--language", default="th")
    s.add_argument("--duration", type=float, default=60.0)
    s.add_argument("--width", type=int, default=1920)
    s.add_argument("--height", type=int, default=1080)
    s.add_argument("--fps", type=float, default=30.0)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("validate", help="validate schemas, graph, references, profile and task DAG")
    s.add_argument("project")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("plan", help="build adaptive skill activation and executable task DAG")
    s.add_argument("project")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("next", help="show tasks whose dependencies are satisfied")
    s.add_argument("project")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("complete", help="record an externally executed task as passed")
    s.add_argument("project")
    s.add_argument("task_id")
    s.add_argument("--artifact", action="append", default=[])
    s.add_argument("--message")
    s.set_defaults(func=cmd_complete)

    s = sub.add_parser("fail", help="record an externally executed task as failed")
    s.add_argument("project")
    s.add_argument("task_id")
    s.add_argument("--message", required=True)
    s.set_defaults(func=cmd_fail)

    s = sub.add_parser("status", help="show orchestration task-state summary")
    s.add_argument("project")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("probe", help="ffprobe a rendered media file")
    s.add_argument("media")
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("assemble", help="assemble ordered rendered segments into one master")
    s.add_argument("project")
    s.add_argument("--manifest", default="manifests/render_manifest.json")
    s.add_argument("--output")
    s.set_defaults(func=cmd_assemble)

    s = sub.add_parser("gate", help="require complete required QC gates before release")
    s.add_argument("project")
    s.add_argument("--qc", default="qc/qc_report.json")
    s.set_defaults(func=cmd_gate)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
