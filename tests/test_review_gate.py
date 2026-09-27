import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.graph import UnitGraph
from core.registry import SkillRegistry
from core.planner import Planner
from core.state import TaskStatus
from core.orchestrator import Orchestrator, TaskResult


class ReviewExecutor:
    """Leaves a task in REVIEW (requires_review defaults to True on TaskResult),
    mirroring how a real external creator/AI hands off work for human approval."""

    def execute(self, task, context):
        return TaskResult(True, [f"artifacts/{task.id}.json"])


class ReviewGateOrchestratorTests(unittest.TestCase):
    """Exercises Orchestrator.approve()/fail_review() directly, following the
    same object-construction pattern as tests/test_kernel.py."""

    @classmethod
    def setUpClass(cls):
        cls.registry = SkillRegistry.load(ROOT / "skills")
        cls.planner = Planner(cls.registry)

    def _project(self, **features):
        return {
            "id": "TEST", "title": "Test", "profile": "short-90s", "language": "th",
            "intent": {"promise": "test"},
            "delivery": {"width": 1920, "height": 1080, "fps": 30},
            "features": features,
            "source_refs": []
        }

    def _graph(self):
        return UnitGraph.from_dict({"units": [
            {"id": "P", "kind": "project", "parent": None, "children": ["SEQ1"]},
            {"id": "SEQ1", "kind": "sequence", "parent": "P", "children": ["SC1"]},
            {"id": "SC1", "kind": "scene", "parent": "SEQ1", "children": ["B1"]},
            {"id": "B1", "kind": "beat", "parent": "SC1", "children": ["SH1", "SH2"]},
            {"id": "SH1", "kind": "shot", "parent": "B1", "children": []},
            {"id": "SH2", "kind": "shot", "parent": "B1", "children": []},
        ]})

    def _orch_with_ready_task(self):
        tasks = self.planner.build_tasks(self._project(infographic=True, narration=True), self._graph())
        orch = Orchestrator(tasks)
        ready = orch.ready_tasks()
        self.assertTrue(ready, "expected at least one ready task on a fresh short-90s plan")
        return orch, ready[0].id

    def test_approve_drives_review_task_to_locked_then_passed(self):
        orch, task_id = self._orch_with_ready_task()
        orch.run_one(task_id, ReviewExecutor(), {})
        self.assertEqual(orch.states[task_id].status, TaskStatus.REVIEW)
        # Orchestrator.approve() itself performs REVIEW -> LOCKED -> PASSED in
        # one call (see core/orchestrator.py); no separate follow-up call needed.
        orch.approve(task_id, "looks good")
        self.assertEqual(orch.states[task_id].status, TaskStatus.PASSED)

    def test_fail_review_drives_review_task_to_failed(self):
        orch, task_id = self._orch_with_ready_task()
        orch.run_one(task_id, ReviewExecutor(), {})
        self.assertEqual(orch.states[task_id].status, TaskStatus.REVIEW)
        orch.fail_review(task_id, "needs another pass")
        self.assertEqual(orch.states[task_id].status, TaskStatus.FAILED)
        self.assertEqual(orch.states[task_id].message, "needs another pass")

    def test_approve_on_non_review_task_raises_value_error(self):
        orch, task_id = self._orch_with_ready_task()
        # task_id is READY, not REVIEW, at this point.
        self.assertEqual(orch.states[task_id].status, TaskStatus.READY)
        with self.assertRaises(ValueError):
            orch.approve(task_id, "premature")

    def test_fail_review_on_non_review_task_raises_value_error(self):
        orch, task_id = self._orch_with_ready_task()
        self.assertEqual(orch.states[task_id].status, TaskStatus.READY)
        with self.assertRaises(ValueError):
            orch.fail_review(task_id, "premature")


class ReviewGateCLITests(unittest.TestCase):
    """Drives the new `clipme.py review`/`clipme.py reject` subcommands as a
    subprocess, confirming an illegal transition surfaces as a clean CLI
    error (non-zero exit, ERROR: message, no Python traceback)."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "clipme.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True,
        )

    def _init_and_plan(self, project_dir: Path) -> str:
        init = self._run("init", str(project_dir), "--profile", "short-90s", "--title", "T")
        self.assertEqual(init.returncode, 0, init.stderr)
        plan = self._run("plan", str(project_dir))
        self.assertEqual(plan.returncode, 0, plan.stderr)
        nxt = self._run("next", str(project_dir))
        self.assertEqual(nxt.returncode, 0, nxt.stderr)
        ready = json.loads(nxt.stdout)["ready"]
        self.assertTrue(ready, "expected at least one ready task after plan")
        return ready[0]["id"]

    def test_review_on_ready_task_is_clean_cli_error(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj"
            task_id = self._init_and_plan(project_dir)
            # task_id is READY (never completed/reviewed yet), so approving it
            # via the CLI must fail cleanly, not with a Python traceback.
            result = self._run("review", str(project_dir), task_id, "--notes", "x")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERROR", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_reject_on_ready_task_is_clean_cli_error(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "proj"
            task_id = self._init_and_plan(project_dir)
            result = self._run("reject", str(project_dir), task_id, "--reason", "x")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ERROR", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
