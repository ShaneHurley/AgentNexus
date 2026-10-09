"""Execute launcher with deterministic uv/Python stubs; no network."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
class MacLauncherTests(unittest.TestCase):
    def run_launcher(self, fail=False, gui=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy2(ROOT / "start_mac.sh", root / "start_mac.sh")
            tools = root / "tools"
            tools.mkdir()
            venv = root / ".venv"
            (venv / "bin").mkdir(parents=True)
            marker = venv / "preserve-me"
            marker.write_text("original")
            py = venv / "bin/python"
            py.write_text('#!/bin/sh\nprintf "python %s\\n" "$*" >> "$LAUNCH_TRACE"\nexit 0\n')
            py.chmod(0o755)
            uv = tools / "uv"
            uv.write_text('#!/bin/sh\nprintf "uv %s\\n" "$*" >> "$LAUNCH_TRACE"\nexit ' + ('23' if fail else '0') + '\n')
            uv.chmod(0o755)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"], LAUNCH_TRACE=str(root / "trace"))
            result = subprocess.run(["bash", str(root / "start_mac.sh")] + (["--gui"] if gui else []), env=env, text=True, capture_output=True)
            trace = (root / "trace").read_text() if (root / "trace").exists() else ""
            return result, trace, marker.exists()
    def test_locked_install_and_gui(self):
        result, trace, preserved = self.run_launcher(gui=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uv sync --locked --all-packages", trace)
        self.assertIn("gui/start.py", trace)
        self.assertTrue(preserved)
    def test_install_failure_stops_and_preserves_venv(self):
        result, trace, preserved = self.run_launcher(fail=True, gui=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("gui/start.py", trace)
        self.assertNotIn("sync_ide_agents", trace)
        self.assertTrue(preserved)
