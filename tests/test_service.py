import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import service


class ServiceLayerTests(unittest.TestCase):
    """Exercises core/service.py functions directly — no argparse, no
    subprocess — against a temp project directory."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="clipme-service-")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.project_dir = Path(self._tmp) / "proj"

    def test_create_project_then_validate_succeeds(self):
        result = service.create_project(self.project_dir, "short-90s", title="Test")
        self.assertEqual(result["profile"], "short-90s")
        self.assertTrue((self.project_dir / "project.yaml").exists())

        validated = service.validate_project(self.project_dir)
        self.assertTrue(validated["passed"])

    def test_plan_project_on_bare_root_produces_two_tasks(self):
        service.create_project(self.project_dir, "short-90s", title="Test")
        result = service.plan_project(self.project_dir)
        skills = {t["skill_id"] for t in result["tasks"]}
        self.assertIn("producer", skills)
        self.assertIn("story", skills)
        self.assertNotIn("editor", skills)
        self.assertNotIn("qc", skills)
        self.assertEqual(result["task_count"], len(result["tasks"]))

    def test_complete_task_then_get_ready_tasks_reflects_new_ready_task(self):
        service.create_project(self.project_dir, "short-90s", title="Test")
        plan = service.plan_project(self.project_dir)
        before = service.get_ready_tasks(self.project_dir)
        ready_ids_before = {t["id"] for t in before["ready"]}
        self.assertTrue(ready_ids_before, "expected at least one ready task on a bare root plan")

        first_id = sorted(ready_ids_before)[0]
        completed = service.complete_task(self.project_dir, first_id, message="done")
        self.assertEqual(completed["task_id"], first_id)

        after = service.get_ready_tasks(self.project_dir)
        ready_ids_after = {t["id"] for t in after["ready"]}
        self.assertNotIn(first_id, ready_ids_after)

    def test_validate_project_raises_validation_error_with_failures(self):
        service.create_project(self.project_dir, "short-90s", title="Test")
        # Corrupt the unit graph so GraphValidator/ReferenceValidator find a
        # real failure — the project's root unit id no longer matches
        # project.yaml's id, which schema/reference validation should catch.
        import json
        graph_path = self.project_dir / "manifests" / "unit_graph.json"
        data = json.loads(graph_path.read_text())
        data["units"][0]["kind"] = "not-a-real-kind"
        graph_path.write_text(json.dumps(data))

        with self.assertRaises(service.ValidationError) as ctx:
            service.validate_project(self.project_dir)
        self.assertTrue(ctx.exception.failures, "ValidationError should carry at least one failure message")

    def test_validate_project_missing_project_yaml_raises_project_not_found(self):
        self.project_dir.mkdir(parents=True)
        with self.assertRaises(service.ProjectNotFoundError):
            service.validate_project(self.project_dir)

    def test_create_project_unknown_profile_raises_profile_not_found(self):
        with self.assertRaises(service.ProfileNotFoundError):
            service.create_project(self.project_dir, "not-a-real-profile")

    def test_complete_task_unknown_task_raises_task_not_found(self):
        service.create_project(self.project_dir, "short-90s", title="Test")
        service.plan_project(self.project_dir)
        with self.assertRaises(service.TaskNotFoundError):
            service.complete_task(self.project_dir, "not-a-real-task", message="x")

    def test_review_task_on_ready_task_raises_illegal_transition(self):
        service.create_project(self.project_dir, "short-90s", title="Test")
        service.plan_project(self.project_dir)
        ready = service.get_ready_tasks(self.project_dir)["ready"]
        self.assertTrue(ready)
        with self.assertRaises(service.IllegalTransitionError):
            service.review_task(self.project_dir, ready[0]["id"], notes="premature")


if __name__ == "__main__":
    unittest.main()
