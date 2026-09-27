import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.server import make_server  # noqa: E402


class ApiTests(unittest.TestCase):
    """Exercises api/server.py end to end over real HTTP (stdlib client only,
    no `requests` dependency), against a fresh server bound to an ephemeral
    port per test so the suite can run without a fixed-port conflict."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="clipme-api-")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.project_dir = Path(self._tmp) / "proj"

        self.httpd = make_server(port=0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            payload = json.dumps(body).encode("utf-8") if body is not None else b""
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            parsed = json.loads(data.decode("utf-8")) if data else {}
            return resp.status, parsed
        finally:
            conn.close()

    def _project_segment(self) -> str:
        return quote(str(self.project_dir), safe="")

    def test_create_validate_plan_ready_complete_happy_path(self):
        status, created = self._request(
            "POST", "/projects",
            {"directory": str(self.project_dir), "profile": "short-90s", "title": "API Test"},
        )
        self.assertEqual(status, 201, created)
        self.assertEqual(created["profile"], "short-90s")

        seg = self._project_segment()

        status, validated = self._request("POST", f"/projects/{seg}/validate")
        self.assertEqual(status, 200, validated)
        self.assertTrue(validated["passed"])

        status, planned = self._request("POST", f"/projects/{seg}/plan")
        self.assertEqual(status, 200, planned)
        self.assertGreater(planned["task_count"], 0)

        status, ready = self._request("GET", f"/projects/{seg}/tasks/ready")
        self.assertEqual(status, 200, ready)
        self.assertTrue(ready["ready"], "expected at least one ready task on a bare root plan")

        first_id = sorted(t["id"] for t in ready["ready"])[0]
        task_seg = quote(first_id, safe="")
        status, completed = self._request(
            "POST", f"/projects/{seg}/tasks/{task_seg}/complete", {"message": "done via API"}
        )
        self.assertEqual(status, 200, completed)
        self.assertEqual(completed["task_id"], first_id)

    def test_unknown_project_returns_404(self):
        missing = self.project_dir / "does-not-exist"
        seg = quote(str(missing), safe="")
        status, body = self._request("POST", f"/projects/{seg}/validate")
        self.assertEqual(status, 404, body)
        self.assertEqual(body["error"], "ProjectNotFoundError")

    def test_fail_task_on_unknown_task_returns_404(self):
        self._request(
            "POST", "/projects", {"directory": str(self.project_dir), "profile": "short-90s", "title": "T"}
        )
        seg = self._project_segment()
        self._request("POST", f"/projects/{seg}/plan")
        status, body = self._request(
            "POST", f"/projects/{seg}/tasks/{quote('NOPE')}/fail", {"message": "boom"}
        )
        self.assertEqual(status, 404, body)
        self.assertEqual(body["error"], "TaskNotFoundError")

    def test_release_gate_reports_release_blocked(self):
        self._request(
            "POST", "/projects", {"directory": str(self.project_dir), "profile": "short-90s", "title": "T"}
        )
        seg = self._project_segment()
        status, body = self._request("GET", f"/projects/{seg}/release")
        self.assertEqual(status, 422, body)
        self.assertEqual(body["error"], "ReleaseBlockedError")

    def test_unknown_route_returns_404(self):
        status, body = self._request("GET", "/nonexistent")
        self.assertEqual(status, 404, body)
        self.assertEqual(body["error"], "NotFound")


if __name__ == "__main__":
    unittest.main()
