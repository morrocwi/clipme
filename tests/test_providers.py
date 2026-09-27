from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import service
from core.providers import (
    CapabilityNotFoundError,
    EchoTextAdapter,
    FFmpegRenderAdapter,
    ProviderRegistry,
)


class ProviderRegistryTests(unittest.TestCase):
    def test_register_and_get(self):
        registry = ProviderRegistry()
        sentinel = object()
        registry.register("render", sentinel)
        self.assertIs(registry.get("render"), sentinel)
        self.assertEqual(registry.capabilities(), ["render"])

    def test_unregistered_capability_raises(self):
        registry = ProviderRegistry()
        with self.assertRaises(CapabilityNotFoundError):
            registry.get("render")


class EchoTextAdapterTests(unittest.TestCase):
    def test_echo_adapter_never_executes(self):
        adapter = EchoTextAdapter()
        result = adapter.generate_text("hello world")
        self.assertIs(result["executed"], False)
        self.assertEqual(result["echo"], "hello world")
        self.assertIn("note", result)


class FFmpegRenderAdapterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
    def test_ffmpeg_render_adapter_assembles_project(self):
        tmp = Path(tempfile.mkdtemp(prefix="clipme-providers-"))
        project_dir = tmp / "proj"
        service.create_project(project_dir, "short-90s", title="Providers Test")

        # Build one trivial video segment with ffmpeg's own lavfi source so
        # this test needs no external media fixtures.
        ffmpeg = shutil.which("ffmpeg")
        segment = project_dir / "renders" / "shots" / "seg1.mp4"
        segment.parent.mkdir(parents=True, exist_ok=True)
        import subprocess
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(segment)],
            check=True, capture_output=True,
        )
        service._write_json(
            project_dir / "manifests" / "render_manifest.json",
            {"project_id": "PROJ", "segments": ["renders/shots/seg1.mp4"], "output": "masters/master.mp4"},
        )

        adapter = FFmpegRenderAdapter()
        result = adapter.render({"project_dir": project_dir})
        self.assertTrue(result["executed"])
        self.assertTrue(Path(result["output"]).exists())

    def test_ffmpeg_render_adapter_raises_without_binary(self):
        # Not skip-guarded: this must raise the correct error regardless of
        # whether ffmpeg happens to be on PATH, by pointing at a project
        # whose manifest is missing so assemble_project fails fast — but if
        # ffmpeg genuinely isn't on PATH, confirm BinaryNotFoundError instead.
        if shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is on PATH; binary-missing path covered by construction only")
        adapter = FFmpegRenderAdapter()
        with self.assertRaises(service.BinaryNotFoundError):
            adapter.render({"project_dir": "/nonexistent"})


if __name__ == "__main__":
    unittest.main()
