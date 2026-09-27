"""clipme application-service layer.

This module is the ONE place that builds domain objects (UnitGraph, SkillRegistry,
Planner, Orchestrator), does file I/O (loading/writing project.yaml and the
manifests under a project directory) and validates against the JSON schemas.
`clipme.py` (the CLI) and any future API adapter are both thin callers of the
plain functions defined here.

Design rules for this module, deliberately kept:
- No argparse awareness. Functions take/return plain values, dicts or small
  dataclasses (see `core.planner.Task`, `core.state.TaskState`) — never an
  argparse Namespace.
- No printing. Formatting/printing output is the CLI's job (or an API
  adapter's, in a future work item); these functions only return data.
- No `sys.exit`/`SystemExit`. Every error path raises a `ClipmeError`
  subclass; a CLI adapter maps that to an exit code, an HTTP adapter would
  map it to a status code.
- Still synchronous and local-filesystem-backed — no DB, no async queue, no
  network. Multi-tenancy, auth and concurrent-writer locking are explicitly
  OUT OF SCOPE for this module today (see the Gap Analysis's `blocks_api`
  items 3 and 5) and are not silently pretended to exist here.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .graph import UnitGraph
from .orchestrator import Orchestrator
from .planner import Planner, Task
from .registry import SkillRegistry
from .state import TaskState
from .validator import GraphValidator, ProfileValidator, ReferenceValidator, TaskGraphValidator

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
PROFILES = ROOT / "profiles"
SKILLS = ROOT / "skills"


# --------------------------------------------------------------------------- #
# Exception hierarchy — the only way a service function signals failure.
# --------------------------------------------------------------------------- #

class ClipmeError(Exception):
    """Base class for every error this service layer raises. Never a
    SystemExit/sys.exit — callers (CLI, API, tests) translate this into their
    own signaling."""


class ProjectNotFoundError(ClipmeError):
    """A required project file/directory does not exist."""


class ProfileNotFoundError(ClipmeError):
    """The named profile has no matching profiles/<id>.yaml."""


class PlanNotFoundError(ClipmeError):
    """No production_plan.json exists yet for this project (run plan first)."""


class TaskNotFoundError(ClipmeError):
    """The task id is not part of this project's task graph."""


class IllegalTransitionError(ClipmeError):
    """The orchestrator's state machine rejected the requested transition."""


class BinaryNotFoundError(ClipmeError):
    """A required external binary (ffmpeg/ffprobe) is not on PATH."""


class ValidationError(ClipmeError):
    """One or more validation failures were found. `failures` holds each
    failure message exactly as the CLI has always printed it (one per line,
    without the leading 'FAIL ' prefix, which is a presentation concern)."""

    def __init__(self, message: str, failures: list[str] | None = None):
        super().__init__(message)
        self.failures = failures or []


class ReleaseBlockedError(ClipmeError):
    """The release gate (`gate`/`evaluate_release`) refused to pass the
    master. Carries the same structured detail the CLI has always printed."""

    def __init__(
        self,
        message: str,
        missing: list[str] | None = None,
        unpassed: list[str] | None = None,
        failing: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.missing = missing or []
        self.unpassed = unpassed or []
        self.failing = failing or []


# --------------------------------------------------------------------------- #
# Small file-I/O helpers (private to this module).
# --------------------------------------------------------------------------- #

def _load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _validate_json_schema(data: Any, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(x) for x in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


def _load_profile(profile_id: str) -> dict[str, Any]:
    path = PROFILES / f"{profile_id}.yaml"
    if not path.exists():
        raise ProfileNotFoundError(f"unknown profile: {profile_id}")
    return _load_data(path)


def _load_unit_graph(project_dir: Path, project: dict[str, Any]) -> UnitGraph:
    path = project_dir / "manifests" / "unit_graph.json"
    if not path.exists():
        data = {"units": [{"id": project["id"], "kind": "project", "parent": None, "children": []}]}
        _write_json(path, data)
    return UnitGraph.from_dict(_load_data(path))


def _load_docs(directory: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not directory.exists():
        return docs
    seen: set[Path] = set()
    for pattern in ("*.yaml", "*.yml", "*.json"):
        for path in sorted(directory.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            docs.append(_load_data(path))
    return docs


def _collect_fact_ids(project_dir: Path) -> set[str] | None:
    path = project_dir / "bibles" / "fact_ledger.json"
    if not path.exists():
        path = project_dir / "fact_ledger.json"
    if not path.exists():
        return None
    data = _load_data(path)
    return {f.get("fact_id") for f in data.get("facts", []) if f.get("fact_id")}


def _collect_asset_ids(project_dir: Path) -> set[str] | None:
    path = project_dir / "manifests" / "asset_manifest.json"
    if not path.exists():
        return None
    data = _load_data(path)
    rows = data.get("assets", data if isinstance(data, list) else [])
    return {a.get("asset_id") for a in rows if isinstance(a, dict) and a.get("asset_id")}


def _ffconcat_quote(path: Path) -> str:
    s = str(path.resolve()).replace("'", "'\\''")
    return f"file '{s}'"


def _load_orchestrator(project_dir: Path) -> tuple[Orchestrator, Path]:
    plan_path = project_dir / "manifests" / "production_plan.json"
    state_path = project_dir / "manifests" / "task_state.json"
    if not plan_path.exists():
        raise PlanNotFoundError("missing production plan; run 'plan' first")
    plan = _load_data(plan_path)
    tasks = [Task.from_dict(t) for t in plan.get("tasks", [])]
    states: dict[str, TaskState] = {}
    if state_path.exists():
        raw = _load_data(state_path).get("tasks", {})
        task_ids = {t.id for t in tasks}
        states = {task_id: TaskState.from_dict(data) for task_id, data in raw.items() if task_id in task_ids}
    orch = Orchestrator(tasks, states)
    return orch, state_path


# --------------------------------------------------------------------------- #
# Public service functions — one per CLI verb.
# --------------------------------------------------------------------------- #

def create_project(
    directory: str | Path,
    profile: str,
    *,
    title: str | None = None,
    project_id: str | None = None,
    language: str = "th",
    duration: float = 60.0,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
) -> dict[str, Any]:
    """Scaffold a new clipme project workspace. Raises ValidationError if the
    destination directory exists and is non-empty, ProfileNotFoundError if
    `profile` has no matching profiles/<profile>.yaml."""
    dest = Path(directory).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValidationError(f"destination is not empty: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    _load_profile(profile)

    for rel in [
        "sources", "bibles", "story", "sequences", "scenes", "beats", "shots",
        "assets", "audio", "renders/shots", "renders/sequences", "renders/reels",
        "manifests", "qc", "masters",
    ]:
        (dest / rel).mkdir(parents=True, exist_ok=True)

    pid = project_id or dest.name.upper().replace("-", "_")
    project = {
        "id": pid,
        "title": title or dest.name,
        "profile": profile,
        "language": language,
        "audience": "",
        "intent": {
            "promise": "",
            "core_question": "",
            "desired_viewer_change": "",
            "tone": "",
            "genre": "",
        },
        "duration": {"target_seconds": duration},
        "delivery": {
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "channels": 2,
        },
        "features": {},
        "skill_overrides": {},
        "constraints": {},
        "source_refs": [],
        "bible_refs": [],
    }
    _write_yaml(dest / "project.yaml", project)
    _write_json(dest / "manifests" / "unit_graph.json", {
        "units": [{"id": pid, "kind": "project", "parent": None, "children": []}]
    })
    _write_json(dest / "manifests" / "render_manifest.json", {
        "project_id": pid,
        "segments": [],
        "output": "masters/master.mp4",
    })
    _write_json(dest / "qc" / "qc_report.json", {"scope": "master", "status": "FAIL", "checks": []})
    return {"dest": dest, "project_id": pid, "profile": profile}


def validate_project(project_dir: str | Path) -> dict[str, Any]:
    """Run the full schema + profile + graph + reference + skill-registry +
    task-DAG validation chain. Raises ProjectNotFoundError if project.yaml is
    missing, ValidationError (carrying `.failures`, one string per failure)
    if anything fails. Returns {"passed": True, "message": ...} on success."""
    project_dir = Path(project_dir).resolve()
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        raise ProjectNotFoundError(f"missing {project_path}")

    failures: list[str] = []
    project = _load_data(project_path)
    for err in _validate_json_schema(project, SCHEMAS / "project.schema.json"):
        failures.append(f"project.yaml: {err}")

    profile = _load_profile(project["profile"])
    for issue in ProfileValidator().validate(project, profile):
        failures.append(f"{issue.code}: {issue.message}")

    graph_path = project_dir / "manifests" / "unit_graph.json"
    if graph_path.exists():
        graph_data = _load_data(graph_path)
        for err in _validate_json_schema(graph_data, SCHEMAS / "unit.schema.json"):
            failures.append(f"manifests/unit_graph.json: {err}")
        graph = UnitGraph.from_dict(graph_data)
        for issue in GraphValidator().validate(graph, profile):
            failures.append(f"{issue.code}: {issue.message}")
    else:
        graph = _load_unit_graph(project_dir, project)

    registry = SkillRegistry.load(SKILLS)
    for skill_dir in sorted(SKILLS.iterdir()):
        manifest = skill_dir / "skill.yaml"
        if manifest.exists():
            for err in _validate_json_schema(_load_data(manifest), SCHEMAS / "skill.schema.json"):
                failures.append(f"{manifest.relative_to(ROOT)}: {err}")

    def validate_globs(directory: str, schema_name: str) -> list[dict[str, Any]]:
        docs = _load_docs(project_dir / directory)
        for doc in docs:
            for err in _validate_json_schema(doc, SCHEMAS / schema_name):
                failures.append(f"{directory}: {err}")
        return docs

    sequences = validate_globs("sequences", "sequence.schema.json")
    scenes = validate_globs("scenes", "scene.schema.json")
    shots = validate_globs("shots", "shot.schema.json")

    timeline_path = project_dir / "manifests" / "timeline.json"
    timeline = _load_data(timeline_path) if timeline_path.exists() else None
    if timeline is not None:
        for err in _validate_json_schema(timeline, SCHEMAS / "timeline.schema.json"):
            failures.append(f"manifests/timeline.json: {err}")

    for issue in ReferenceValidator().validate_documents(
        graph, sequences, scenes, shots, timeline,
        facts=_collect_fact_ids(project_dir), assets=_collect_asset_ids(project_dir)
    ):
        failures.append(f"{issue.code}: {issue.message}")

    tasks = Planner(registry).build_tasks(project, graph)
    for issue in TaskGraphValidator().validate(tasks, registry):
        failures.append(f"{issue.code}: {issue.message}")

    if failures:
        raise ValidationError("project failed validation", failures=failures)
    return {"passed": True, "message": "schemas, profile, unit graph, references, skill registry and task DAG"}


def plan_project(project_dir: str | Path) -> dict[str, Any]:
    """Build the adaptive skill-activation + executable task DAG, persist
    production_plan.json and task_state.json (preserving prior TaskState for
    any task whose plan signature is unchanged), and return a summary dict.
    Raises ValidationError (carrying `.failures`) if the graph or task DAG do
    not validate."""
    project_dir = Path(project_dir).resolve()
    project = _load_data(project_dir / "project.yaml")
    profile = _load_profile(project["profile"])
    graph = _load_unit_graph(project_dir, project)
    graph_issues = GraphValidator().validate(graph, profile)
    if graph_issues:
        raise ValidationError(
            "graph validation failed",
            failures=[f"{issue.code}: {issue.message}" for issue in graph_issues],
        )

    registry = SkillRegistry.load(SKILLS)
    planner = Planner(registry)
    plan = planner.plan(project, graph)
    task_objects = [Task.from_dict(t) for t in plan["tasks"]]
    task_issues = TaskGraphValidator().validate(task_objects, registry)
    if task_issues:
        raise ValidationError(
            "task graph validation failed",
            failures=[f"{issue.code}: {issue.message}" for issue in task_issues],
        )

    plan_path = project_dir / "manifests" / "production_plan.json"
    _write_json(plan_path, plan)

    state_path = project_dir / "manifests" / "task_state.json"
    previous = _load_data(state_path).get("tasks", {}) if state_path.exists() else {}
    states: dict[str, TaskState] = {}
    for task in task_objects:
        signature = task.signature()
        if task.id in previous:
            prior = TaskState.from_dict(previous[task.id])
            if prior.metadata.get("plan_signature") == signature:
                states[task.id] = prior
            else:
                states[task.id] = TaskState(task_id=task.id, metadata={"plan_signature": signature})
        else:
            states[task.id] = TaskState(task_id=task.id, metadata={"plan_signature": signature})
    orch = Orchestrator(task_objects, states)
    _write_json(state_path, orch.snapshot())

    counts: dict[str, int] = {}
    for status in plan["activation"].values():
        counts[status] = counts.get(status, 0) + 1

    return {
        "task_count": len(task_objects),
        "profile": project["profile"],
        "activation_counts": counts,
        "plan_path": plan_path,
        "state_path": state_path,
        "tasks": plan["tasks"],
        "activation": plan["activation"],
    }


def replan_project(project_dir: str | Path) -> dict[str, Any]:
    """Re-run planning against the current project/graph state. Identical to
    plan_project — re-running `plan` IS how this kernel replans, carrying
    over prior TaskState via signature matching."""
    return plan_project(project_dir)


def get_ready_tasks(project_dir: str | Path) -> dict[str, Any]:
    """Return the tasks whose dependencies are satisfied. Raises
    PlanNotFoundError if `plan_project` has not been run yet."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    ready = [t.to_dict() for t in orch.ready_tasks()]
    _write_json(state_path, orch.snapshot())
    return {"ready": ready, "complete": orch.is_complete()}


def start_task(project_dir: str | Path, task_id: str) -> dict[str, Any]:
    """Query-only. The current kernel has no state-changing 'start' verb
    distinct from checking readiness — a task becomes RUNNING only as a side
    effect of `complete_task`/`fail_task` (see Orchestrator.complete_external/
    mark_failed_external). This returns the ready-task detail for `task_id`
    without transitioning any state, matching what `clipme.py next` already
    reports for a ready task. Raises TaskNotFoundError if `task_id` is not
    currently ready."""
    result = get_ready_tasks(project_dir)
    for task in result["ready"]:
        if task.get("id") == task_id:
            return task
    raise TaskNotFoundError(f"task {task_id} is not ready")


def complete_task(
    project_dir: str | Path, task_id: str, artifacts: list[str] | None = None, message: str = ""
) -> dict[str, Any]:
    """Record a task completed by an external AI/tool runner. Raises
    TaskNotFoundError for an unknown task id, IllegalTransitionError if the
    task is not currently READY."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    if task_id not in orch.tasks:
        raise TaskNotFoundError(f"unknown task: {task_id}")
    try:
        orch.complete_external(task_id, artifacts=artifacts or [], message=message)
    except ValueError as exc:
        raise IllegalTransitionError(str(exc)) from exc
    _write_json(state_path, orch.snapshot())
    return {"task_id": task_id, "ready_count": len(orch.ready_tasks())}


def fail_task(project_dir: str | Path, task_id: str, message: str) -> dict[str, Any]:
    """Record a task as failed. Raises TaskNotFoundError for an unknown task
    id, IllegalTransitionError if the task cannot fail from its current
    state."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    if task_id not in orch.tasks:
        raise TaskNotFoundError(f"unknown task: {task_id}")
    try:
        orch.mark_failed_external(task_id, message)
    except ValueError as exc:
        raise IllegalTransitionError(str(exc)) from exc
    _write_json(state_path, orch.snapshot())
    return {"task_id": task_id, "message": message}


def review_task(project_dir: str | Path, task_id: str, notes: str = "") -> dict[str, Any]:
    """Approve a task in REVIEW state, passing it to LOCKED then PASSED
    (mirrors clipme.py's `review` CLI verb, which calls Orchestrator.approve()
    — the maker-checker gate closed by WI-1). Raises TaskNotFoundError for an
    unknown task id, IllegalTransitionError if the task is not in REVIEW."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    if task_id not in orch.tasks:
        raise TaskNotFoundError(f"unknown task: {task_id}")
    try:
        orch.approve(task_id, notes or "")
    except ValueError as exc:
        raise IllegalTransitionError(str(exc)) from exc
    _write_json(state_path, orch.snapshot())
    return {"task_id": task_id, "ready_count": len(orch.ready_tasks())}


def reject_task(project_dir: str | Path, task_id: str, reason: str) -> dict[str, Any]:
    """Reject a task in REVIEW state, sending it to FAILED (mirrors
    clipme.py's `reject` CLI verb, which calls Orchestrator.fail_review()).
    Raises TaskNotFoundError for an unknown task id, IllegalTransitionError
    if the task is not in REVIEW."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    if task_id not in orch.tasks:
        raise TaskNotFoundError(f"unknown task: {task_id}")
    try:
        orch.fail_review(task_id, reason)
    except ValueError as exc:
        raise IllegalTransitionError(str(exc)) from exc
    _write_json(state_path, orch.snapshot())
    return {"task_id": task_id, "reason": reason}


def get_status(project_dir: str | Path) -> dict[str, Any]:
    """Return an orchestration task-state summary. Raises PlanNotFoundError
    if `plan_project` has not been run yet."""
    project_dir = Path(project_dir).resolve()
    orch, state_path = _load_orchestrator(project_dir)
    _write_json(state_path, orch.snapshot())
    counts: dict[str, int] = {}
    for state in orch.states.values():
        counts[state.status.value] = counts.get(state.status.value, 0) + 1
    return {"counts": counts, "complete": orch.is_complete()}


def probe_media(media_path: str | Path) -> dict[str, Any]:
    """Run ffprobe against a media file and return the parsed JSON. Raises
    BinaryNotFoundError if ffprobe is not on PATH, ValidationError if the
    media file does not exist."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise BinaryNotFoundError("ffprobe not found in PATH")
    media = Path(media_path).resolve()
    if not media.exists():
        raise ValidationError(f"media not found: {media}")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(proc.stdout)


def assemble_project(
    project_dir: str | Path,
    manifest_rel: str = "manifests/render_manifest.json",
    output_rel: str | None = None,
) -> dict[str, Any]:
    """Concatenate the ordered rendered segments listed in the render
    manifest into one master file via ffmpeg. Raises BinaryNotFoundError if
    ffmpeg is not on PATH, ValidationError if the manifest has no segments or
    a referenced segment file is missing."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise BinaryNotFoundError("ffmpeg not found in PATH")
    project_dir = Path(project_dir).resolve()
    manifest_path = project_dir / manifest_rel
    manifest = _load_data(manifest_path)
    segments = manifest.get("segments") or []
    if not segments:
        raise ValidationError("render manifest has no segments")

    paths = []
    for item in segments:
        rel = item["path"] if isinstance(item, dict) else item
        p = (project_dir / rel).resolve()
        if not p.exists():
            raise ValidationError(f"missing segment: {p}")
        paths.append(p)

    final_output_rel = output_rel or manifest.get("output") or "masters/master.mp4"
    output = (project_dir / final_output_rel).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="clipme-") as td:
        listfile = Path(td) / "concat.txt"
        listfile.write_text("\n".join(_ffconcat_quote(p) for p in paths) + "\n", encoding="utf-8")
        subprocess.run([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
            "-movflags", "+faststart", str(output)
        ], check=True)
    return {"output": output}


def evaluate_release(project_dir: str | Path, qc_rel: str = "qc/qc_report.json") -> dict[str, Any]:
    """Require complete required QC gates before release (the `gate`
    command's logic). Raises ValidationError if the QC report fails schema
    validation, ReleaseBlockedError (carrying `.missing`/`.unpassed`/
    `.failing`) if the master is not releasable."""
    project_dir = Path(project_dir).resolve()
    qc_path = project_dir / qc_rel
    data = _load_data(qc_path)
    errors = _validate_json_schema(data, SCHEMAS / "qc.schema.json")
    if errors:
        raise ValidationError("qc report failed schema validation", failures=errors)

    project = _load_data(project_dir / "project.yaml")
    profile = _load_profile(project["profile"])
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
        raise ReleaseBlockedError("master is not releasable", missing=missing, unpassed=unpassed, failing=failing)
    return {"passed": True}
