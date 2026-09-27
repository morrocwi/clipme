#!/usr/bin/env python3
"""clipme runtime and orchestration control plane.

Creative AI/provider execution is injected around a small deterministic kernel.
The kernel owns profiles, unit/skill graphs, task state, validation, assembly and
release gating so short work can stay small while long work can scale safely.

This module is a thin CLI adapter: every cmd_* function parses argparse args,
calls exactly one core.service.* function, and formats/prints the result (or
maps a core.service.ClipmeError subclass to a clean CLI error via die()). All
object-building, file I/O and validation logic lives in core/service.py so a
future API adapter can share the same boundary.
"""
from __future__ import annotations

import argparse
import json
import sys

from core import service


def die(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def cmd_init(args) -> None:
    try:
        result = service.create_project(
            args.directory, args.profile,
            title=args.title, project_id=args.id, language=args.language,
            duration=args.duration, width=args.width, height=args.height, fps=args.fps,
        )
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"Initialized clipme project: {result['dest']}")
    print(f"Profile: {result['profile']}")
    print("Next: edit project.yaml features/brief, then run 'clipme.py plan <project>'.")


def cmd_validate(args) -> None:
    try:
        service.validate_project(args.project)
    except service.ValidationError as exc:
        for failure in exc.failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print("PASS schemas, profile, unit graph, references, skill registry and task DAG")


def cmd_plan(args) -> None:
    try:
        result = service.plan_project(args.project)
    except service.ValidationError as exc:
        for failure in exc.failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"Planned {result['task_count']} executable tasks for {result['profile']}")
    print("Activation:", ", ".join(f"{k}={v}" for k, v in sorted(result["activation_counts"].items())))
    print(f"Plan: {result['plan_path']}")
    print(f"State: {result['state_path']}")


def cmd_next(args) -> None:
    try:
        result = service.get_ready_tasks(args.project)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(json.dumps({"ready": result["ready"], "complete": result["complete"]}, indent=2, ensure_ascii=False))


def cmd_complete(args) -> None:
    try:
        result = service.complete_task(args.project, args.task_id, artifacts=args.artifact or [], message=args.message or "")
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"PASS task {args.task_id}")
    print(f"New ready tasks: {result['ready_count']}")


def cmd_fail(args) -> None:
    try:
        service.fail_task(args.project, args.task_id, args.message)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"FAIL task {args.task_id}: {args.message}")


def cmd_review(args) -> None:
    try:
        result = service.review_task(args.project, args.task_id, args.notes or "")
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"PASS task {args.task_id} approved")
    print(f"New ready tasks: {result['ready_count']}")


def cmd_reject(args) -> None:
    try:
        service.reject_task(args.project, args.task_id, args.reason)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"FAIL task {args.task_id}: {args.reason}")


def cmd_status(args) -> None:
    try:
        result = service.get_status(args.project)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(json.dumps({"counts": result["counts"], "complete": result["complete"]}, indent=2))


def cmd_probe(args) -> None:
    try:
        data = service.probe_media(args.media)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(json.dumps(data, indent=2))


def cmd_assemble(args) -> None:
    try:
        result = service.assemble_project(args.project, manifest_rel=args.manifest, output_rel=args.output)
    except service.ClipmeError as exc:
        die(str(exc))
        return
    print(f"Master assembled: {result['output']}")


def cmd_gate(args) -> None:
    try:
        service.evaluate_release(args.project, qc_rel=args.qc)
    except service.ReleaseBlockedError as exc:
        print("FAIL master is not releasable")
        if exc.missing:
            print("- missing required QC gates:", ", ".join(exc.missing))
        if exc.unpassed:
            print("- required QC gates not PASS/NA:", ", ".join(exc.unpassed))
        for c in exc.failing:
            print(f"- {c.get('gate')}: {c.get('repair', 'repair required')}")
        raise SystemExit(1)
    except service.ValidationError as exc:
        for failure in exc.failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    except service.ClipmeError as exc:
        die(str(exc))
        return
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

    s = sub.add_parser("review", help="approve a task in REVIEW state, passing it to LOCKED/PASSED")
    s.add_argument("project")
    s.add_argument("task_id")
    s.add_argument("--notes")
    s.set_defaults(func=cmd_review)

    s = sub.add_parser("reject", help="reject a task in REVIEW state, sending it to FAILED")
    s.add_argument("project")
    s.add_argument("task_id")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_reject)

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
