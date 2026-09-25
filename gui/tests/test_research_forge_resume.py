"""Research Forge adapter resume — fail-closed, live gate, HTTP mapping."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from agent_dashboard.adapters.research_forge import ResearchForgeAdapter
from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler, _resume_http_status

from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]
RF_ROOT = ROOT.parent / "research-forge"


class ResumeHttpStatusTests(unittest.TestCase):
    def test_status_mapping(self):
        self.assertEqual(_resume_http_status({"accepted": True}), 202)
        self.assertEqual(
            _resume_http_status({"accepted": False, "error": {"code": "NOT_FOUND", "message": "x"}}),
            404,
        )
        self.assertEqual(
            _resume_http_status({"accepted": False, "error": {"code": "POLICY_DENIED", "message": "x"}}),
            403,
        )
        self.assertEqual(_resume_http_status({"accepted": False, "error": "boom"}), 502)


class ResearchForgeResumeAdapterTests(unittest.TestCase):
    def _adapter(self, tmp: str, package_root: Path) -> ResearchForgeAdapter:
        return ResearchForgeAdapter(
            "research-forge",
            "RF",
            "test",
            {"package_root": str(package_root), "workspace_root": str(package_root)},
            Path(tmp) / "data",
        )

    def test_missing_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "pyproject.toml").write_text("[project]\nname='rf-test'\n", encoding="utf-8")
            adapter = self._adapter(tmp, pkg)
            out = adapter.resume("no-such-run")
            self.assertFalse(out["accepted"])
            self.assertEqual(out["error"]["code"], "NOT_FOUND")

    def test_persisted_state_mock_resume(self):
        from research_forge.wave1.orchestrator import RunState
        from research_forge.wave1.persistence import save_run_state

        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "pyproject.toml").write_text("[project]\nname='rf-test'\n", encoding="utf-8")
            run_id = "W1-resume-smoke"
            save_run_state(pkg, RunState(run_id=run_id, phase="clarify").to_dict(), live=False)
            adapter = self._adapter(tmp, pkg)
            with patch("research_forge.wave1.orchestrator.Wave1Orchestrator") as mock_orch_cls:
                mock_orch_cls.return_value.resume.return_value = {
                    "ok": True,
                    "paused": False,
                    "state": {"run_id": run_id, "phase": "search"},
                }
                out = adapter.resume(run_id)
            self.assertTrue(out["accepted"], msg=out)
            self.assertTrue(out.get("ok"))

    def test_live_gate_denied(self):
        from research_forge.wave1.orchestrator import RunState
        from research_forge.wave1.persistence import save_run_state

        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "pyproject.toml").write_text("[project]\nname='rf-test'\n", encoding="utf-8")
            run_id = "W1-live-deny"
            save_run_state(pkg, RunState(run_id=run_id, phase="clarify").to_dict(), live=True)
            adapter = self._adapter(tmp, pkg)
            out = adapter.resume(run_id)
            self.assertFalse(out["accepted"])
            self.assertEqual(out["error"]["code"], "POLICY_DENIED")


class ResumeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = load_config(ROOT / "config" / "agents.json")
        cls._tmpdir = tempfile.TemporaryDirectory()
        reg = Registry(cfg, ROOT / "config", Path(cls._tmpdir.name))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.httpd.ctx = make_server_ctx(reg, auth_required=False, token="")
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.httpd.server_address
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._tmpdir.cleanup()

    def test_http_missing_state_404(self):
        req = urllib.request.Request(
            self.base + "/api/agents/research-forge/runs/RF-missing-persist/resume",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 404)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertFalse(body.get("accepted"))
        self.assertEqual(body.get("error", {}).get("code"), "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
