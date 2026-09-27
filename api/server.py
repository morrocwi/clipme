#!/usr/bin/env python3
"""Minimal stdlib HTTP API over core/service.py.

Uses ONLY Python's standard library (http.server, json, urllib.parse) — no
fastapi/flask/other web framework dependency, matching the dependency policy
in the plan (`plan_md`'s "Dependency policy" section): this API is
single-project, low-QPS, local/self-hosted, and stdlib fully covers routing +
JSON for the handful of routes below.

LOCAL-DEV-ONLY DESIGN, READ BEFORE DEPLOYING ANYWHERE ELSE:
  - `{project}` in every route below is a clipme project *directory path* on
    THIS machine's filesystem, percent-encoded into a single URL path segment
    (so a literal "/" inside the path must be sent as "%2F"). It is passed
    straight to core.service.* functions, which resolve it with
    `Path(...).resolve()`. There is NO path-traversal hardening, NO sandboxing
    to a project root, and NO check that the caller is allowed to touch that
    directory.
  - There is NO authentication, NO authorization, and NO multi-tenancy. Any
    client that can reach this port can create, read, mutate or assemble any
    project reachable from this filesystem.
  - This is acceptable ONLY for local development / same-machine tooling. Do
    not expose this server on a network interface other than localhost
    without adding auth + path confinement first. This limitation is
    intentional and documented, not an oversight (see the Gap Analysis's
    `blocks_api` item 5).

Route table (all bodies/responses are JSON; empty body is treated as `{}`):

  POST   /projects                                  -> create_project
  POST   /projects/{project}/validate                -> validate_project
  POST   /projects/{project}/plan                     -> plan_project
  POST   /projects/{project}/replan                   -> replan_project
  GET    /projects/{project}/tasks/ready              -> get_ready_tasks
  POST   /projects/{project}/tasks/{task_id}/complete -> complete_task
  POST   /projects/{project}/tasks/{task_id}/fail     -> fail_task
  POST   /projects/{project}/tasks/{task_id}/review   -> review_task (approve;
                                                          service.py's actual
                                                          verb name is
                                                          `review_task`, which
                                                          approves a REVIEW-
                                                          state task through to
                                                          LOCKED/PASSED — see
                                                          its docstring)
  POST   /projects/{project}/tasks/{task_id}/reject   -> reject_task (service.py
                                                          has no separate
                                                          `approve_task`; the
                                                          CLI/service verbs are
                                                          `review`/`reject`,
                                                          matched here 1:1
                                                          rather than inventing
                                                          an `/approve` alias)
  POST   /projects/{project}/assemble                 -> assemble_project
  GET    /projects/{project}/release                  -> evaluate_release

Every core.service.ClipmeError subclass is caught and mapped to a JSON error
body `{"error": "<ClassName>", "message": "...", ...extra fields...}` with an
appropriate HTTP status code (see `_STATUS_BY_ERROR` below).
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import service  # noqa: E402

DEFAULT_PORT = 8420

# Maps each ClipmeError subclass to the HTTP status code it should produce.
# Order matters: more specific subclasses are checked before ClipmeError.
_STATUS_BY_ERROR: list[tuple[type[Exception], int]] = [
    (service.ProjectNotFoundError, 404),
    (service.ProfileNotFoundError, 404),
    (service.PlanNotFoundError, 404),
    (service.TaskNotFoundError, 404),
    (service.IllegalTransitionError, 409),
    (service.BinaryNotFoundError, 503),
    (service.ReleaseBlockedError, 422),
    (service.ValidationError, 422),
    (service.ClipmeError, 500),
]


def _status_for(exc: Exception) -> int:
    for cls, status in _STATUS_BY_ERROR:
        if isinstance(exc, cls):
            return status
    return 500


def _error_body(exc: Exception) -> dict[str, Any]:
    body: dict[str, Any] = {"error": type(exc).__name__, "message": str(exc)}
    failures = getattr(exc, "failures", None)
    if failures:
        body["failures"] = failures
    for attr in ("missing", "unpassed", "failing"):
        value = getattr(exc, attr, None)
        if value:
            body[attr] = value
    return body


def _jsonable(value: Any) -> Any:
    """Recursively coerce values core.service.* returns (which may include
    pathlib.Path) into something json.dumps can serialize."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


# --------------------------------------------------------------------------- #
# Route table: (method, compiled path pattern, handler taking (match, body))
# --------------------------------------------------------------------------- #

Handler = Callable[[re.Match, dict[str, Any]], tuple[int, Any]]


def _route(pattern: str) -> re.Pattern:
    # {name} -> a single URL path segment, percent-decoded by the caller of
    # match.group(name) below (see _decode_segment).
    regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
    return re.compile(f"^{regex}$")


def _decode_segment(match: re.Match, name: str) -> str:
    return unquote(match.group(name))


def _handle_create_project(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    directory = body.get("directory") or body.get("project")
    if not directory:
        raise service.ValidationError("body must include 'directory'")
    result = service.create_project(
        directory,
        body.get("profile", "short-90s"),
        title=body.get("title"),
        project_id=body.get("id"),
        language=body.get("language", "th"),
        duration=float(body.get("duration", 60.0)),
        width=int(body.get("width", 1920)),
        height=int(body.get("height", 1080)),
        fps=float(body.get("fps", 30.0)),
    )
    return 201, result


def _handle_validate(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    return 200, service.validate_project(project)


def _handle_plan(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    return 200, service.plan_project(project)


def _handle_replan(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    return 200, service.replan_project(project)


def _handle_ready_tasks(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    return 200, service.get_ready_tasks(project)


def _handle_complete_task(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    task_id = _decode_segment(match, "task_id")
    result = service.complete_task(
        project, task_id, artifacts=body.get("artifacts") or [], message=body.get("message", "")
    )
    return 200, result


def _handle_fail_task(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    task_id = _decode_segment(match, "task_id")
    message = body.get("message", "")
    return 200, service.fail_task(project, task_id, message)


def _handle_review_task(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    task_id = _decode_segment(match, "task_id")
    return 200, service.review_task(project, task_id, body.get("notes", ""))


def _handle_reject_task(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    task_id = _decode_segment(match, "task_id")
    reason = body.get("reason", "")
    return 200, service.reject_task(project, task_id, reason)


def _handle_assemble(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    result = service.assemble_project(
        project, manifest_rel=body.get("manifest", "manifests/render_manifest.json"),
        output_rel=body.get("output"),
    )
    return 200, result


def _handle_release(match: re.Match, body: dict[str, Any]) -> tuple[int, Any]:
    project = _decode_segment(match, "project")
    return 200, service.evaluate_release(project)


ROUTES: list[tuple[str, re.Pattern, Handler]] = [
    ("POST", _route("/projects"), _handle_create_project),
    ("POST", _route("/projects/{project}/validate"), _handle_validate),
    ("POST", _route("/projects/{project}/plan"), _handle_plan),
    ("POST", _route("/projects/{project}/replan"), _handle_replan),
    ("GET", _route("/projects/{project}/tasks/ready"), _handle_ready_tasks),
    ("POST", _route("/projects/{project}/tasks/{task_id}/complete"), _handle_complete_task),
    ("POST", _route("/projects/{project}/tasks/{task_id}/fail"), _handle_fail_task),
    ("POST", _route("/projects/{project}/tasks/{task_id}/review"), _handle_review_task),
    ("POST", _route("/projects/{project}/tasks/{task_id}/reject"), _handle_reject_task),
    ("POST", _route("/projects/{project}/assemble"), _handle_assemble),
    ("GET", _route("/projects/{project}/release"), _handle_release),
]


class ClipmeAPIHandler(BaseHTTPRequestHandler):
    server_version = "clipme-api/0.1"

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        body: dict[str, Any] = {}
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            except json.JSONDecodeError as exc:
                self._send(400, {"error": "BadRequest", "message": f"invalid JSON body: {exc}"})
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "BadRequest", "message": "JSON body must be an object"})
                return

        for route_method, pattern, handler in ROUTES:
            if route_method != method:
                continue
            match = pattern.match(path)
            if not match:
                continue
            try:
                status, result = handler(match, body)
            except service.ClipmeError as exc:
                self._send(_status_for(exc), _error_body(exc))
            except Exception as exc:  # last-resort fallback per the route table's contract
                self._send(500, {"error": type(exc).__name__, "message": str(exc)})
            else:
                self._send(status, _jsonable(result))
            return

        self._send(404, {"error": "NotFound", "message": f"no route for {method} {path}"})

    def _send(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
        pass


def make_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ClipmeAPIHandler)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", DEFAULT_PORT))
    httpd = make_server(port=port)
    print(f"clipme API listening on http://127.0.0.1:{port}  (local dev only, no auth — see api/server.py docstring)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
