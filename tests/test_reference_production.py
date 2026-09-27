"""Reference production 01 (examples/reference-production-01-infographic)
end-to-end test. Skipped entirely if ffmpeg/ffprobe are not on PATH, so the
suite stays green on a machine where scripts/bootstrap.sh has not been run.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "examples" / "reference-production-01-infographic" / "run.py"


def _load_run_module():
    spec = importlib.util.spec_from_file_location("reference_production_run", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "ffmpeg/ffprobe not on PATH; run scripts/bootstrap.sh first",
)
class ReferenceProductionInfographicTest(unittest.TestCase):
    def test_produces_a_real_playable_mp4(self):
        module = _load_run_module()
        with tempfile.TemporaryDirectory(prefix="clipme-ref-prod-test-") as td:
            output = module.main(Path(td) / "project")

            self.assertTrue(output.exists(), f"expected output MP4 at {output}")
            self.assertGreater(output.stat().st_size, 0, "output MP4 must be non-empty")

            ffprobe = shutil.which("ffprobe")
            proc = subprocess.run(
                [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(output)],
                check=True, capture_output=True, text=True,
            )
            probe = json.loads(proc.stdout)

            duration = float(probe["format"]["duration"])
            self.assertGreaterEqual(duration, 25.0, f"duration too short: {duration}")
            self.assertLessEqual(duration, 65.0, f"duration too long: {duration}")

            codec_types = {s["codec_type"] for s in probe["streams"]}
            self.assertIn("video", codec_types, "expected at least one video stream")
            self.assertIn("audio", codec_types, "expected at least one audio stream")


if __name__ == "__main__":
    unittest.main()
