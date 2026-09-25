"""Smoke tests for registry + unified API shapes (no external servers)."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from agent_dashboard.adapters.daily_coder import DailyCoderAdapter
from agent_dashboard.adapters.research_forge import ResearchForgeAdapter
from agent_dashboard.adapters.daily_task import DailyTaskAdapter
from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler, _limit

from tests.test_server_ctx import make_server_ctx


ROOT = Path(__file__).resolve().parents[1]


class RegistryTests(unittest.TestCase):
    def test_loads_registered_agents(self):
        cfg = load_config(ROOT / "config" / "agents.json")
        with tempfile.TemporaryDirectory() as tmp:
            reg = Registry(cfg, ROOT / "config", Path(tmp))
            ids = set(reg.adapters)
            self.assertIn("daily-coder", ids)
            self.assertIn("research-forge", ids)
            self.assertIn("daily-task", ids)
            agents = reg.list_agents()
            self.assertEqual(len(agents), 3)
            self.assertTrue(all("capabilities" in a for a in agents))

    def test_data_dir_never_inside_project(self):
        from agent_dashboard.paths import resolve_data_dir, is_under_project
        for configured in (None, ".agent-dashboard", ".", "./runtime"):
            path = resolve_data_dir(configured, project=ROOT)
            self.assertFalse(is_under_project(path, project=ROOT), msg=str(path))


class LimitHelperTests(unittest.TestCase):
    def test_limit_clamps_and_rejects_bad(self):
        self.assertEqual(_limit({"limit": ["10"]}), 10)
        self.assertEqual(_limit({"limit": ["0"]}), 1)
        self.assertEqual(_limit({"limit": ["9999"]}), 500)
        self.assertEqual(_limit({}), 50)
        with self.assertRaises(ValueError):
            _limit({"limit": ["abc"]})


class HealthAdapterTests(unittest.TestCase):

    def test_daily_task_offline_missing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = DailyTaskAdapter(
                "daily-task", "Daily Task", "desc",
                {"package_root": str(Path(tmp) / "missing")},
                Path(tmp),
            )
            health = adapter.health()
            self.assertFalse(health.get("online"))

    def test_research_forge_offline_missing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = ResearchForgeAdapter(
                "research-forge",
                "RF",
                "test",
                {"package_root": str(Path(tmp) / "missing-pkg")},
                Path(tmp),
            )
            health = adapter.health()
            self.assertFalse(health["online"])

    def test_research_forge_doctor_exception_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "pkg"
            pkg.mkdir()
            (pkg / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
            adapter = ResearchForgeAdapter(
                "research-forge",
                "RF",
                "test",
                {"package_root": str(pkg), "workspace_root": str(pkg)},
                Path(tmp),
            )

            rf = types.ModuleType("research_forge")
            settings_mod = types.ModuleType("research_forge.settings")
            settings_mod.load_settings = lambda *_a, **_k: object()
            wave0 = types.ModuleType("research_forge.wave0")
            doctor_mod = types.ModuleType("research_forge.wave0.doctor")

            def raise_doctor(*_a, **_k):
                raise RuntimeError("doctor failed")

            doctor_mod.run_doctor = raise_doctor

            with patch.dict(
                sys.modules,
                {
                    "research_forge": rf,
                    "research_forge.settings": settings_mod,
                    "research_forge.wave0": wave0,
                    "research_forge.wave0.doctor": doctor_mod,
                },
            ):
                health = adapter.health()
            self.assertFalse(health["online"])

    def test_daily_coder_python_prefers_sys_executable(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {"base_url": "http://127.0.0.1:9"},
        )
        with patch.object(sys, "version_info", (3, 10, 11, "final", 0)):
            with patch.object(sys, "executable", "C:\\fake\\python.exe"):
                self.assertEqual(adapter._python(), ["C:\\fake\\python.exe"])

    def test_daily_coder_python_skips_old_path_python(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {"base_url": "http://127.0.0.1:9"},
        )

        def fake_which(name):
            if name == "python":
                return "C:\\old\\python.exe"
            return None

        def fake_check_call(cmd, **_kwargs):
            joined = " ".join(str(c) for c in cmd)
            if "C:\\old\\python.exe" in joined:
                raise subprocess.CalledProcessError(1, cmd)
            if sys.executable in joined:
                return 0
            raise subprocess.CalledProcessError(1, cmd)

        with patch.object(sys, "version_info", (3, 8, 10, "final", 0)):
            with patch("agent_dashboard.adapters.daily_coder.shutil.which", side_effect=fake_which):
                with patch("agent_dashboard.adapters.daily_coder.subprocess.check_call", side_effect=fake_check_call):
                    with patch("agent_dashboard.adapters.daily_coder.sys.platform", "linux"):
                        self.assertEqual(adapter._python(), [sys.executable])

    def test_daily_coder_set_provider(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {"base_url": "http://127.0.0.1:9"},
        )
        self.assertEqual(adapter.provider, "mock")
        out = adapter.set_provider("gemini")
        self.assertTrue(out["ok"])
        self.assertEqual(adapter.provider, "gemini")
        with self.assertRaises(ValueError):
            adapter.set_provider("copilot-primary")
        with self.assertRaises(ValueError):
            adapter.set_provider("command")
        with self.assertRaises(ValueError):
            adapter.set_provider("http")

    def test_daily_coder_bridge_availability_and_serve_args(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {
                "base_url": "http://127.0.0.1:8765",
                "provider_command": "my-bridge-cmd",
                "provider_endpoint": "http://127.0.0.1:9999/v1",
            },
        )
        self.assertEqual(
            adapter.bridge_availability(),
            {"command": True, "http": True},
        )
        status = adapter.backend_status()
        self.assertEqual(status["bridges"]["command"], True)
        self.assertEqual(status["bridges"]["http"], True)

        adapter.set_provider("command")
        cmd = adapter._serve_command("secret-tok", "command")
        self.assertIn("--provider-command", cmd)
        self.assertEqual(cmd[cmd.index("--provider-command") + 1], "my-bridge-cmd")

        adapter.set_provider("http")
        cmd = adapter._serve_command("secret-tok", "http")
        self.assertIn("--provider-endpoint", cmd)
        self.assertEqual(cmd[cmd.index("--provider-endpoint") + 1], "http://127.0.0.1:9999/v1")

    def test_dashboard_live_confirm_markup(self):
        agent_js = (ROOT / "agent_dashboard" / "web" / "tabs" / "agent.js").read_text(encoding="utf-8")
        picker_js = (ROOT / "agent_dashboard" / "web" / "composer-picker.js").read_text(encoding="utf-8")
        self.assertIn('id="liveConfirm"', picker_js)
        self.assertIn("Start LIVE provider (may spend API credits)", picker_js)
        self.assertIn("requireLiveStartConfirm", agent_js)
        self.assertIn("providerRestartWarn", picker_js)

    def test_dashboard_shell_tabs_and_static_modules(self):
        html = (ROOT / "agent_dashboard" / "web" / "index.html").read_text(encoding="utf-8")
        for tab in ("home", "agent", "docs", "apis", "usage", "ide"):
            self.assertIn(f'data-tab="{tab}"', html, msg=f"missing tab {tab}")
        self.assertIn('id="viewport"', html)
        self.assertIn('role="tablist"', html)

        static_paths = (
            "/router.js",
            "/state.js",
            "/app.js",
            "/tabs/agent.js",
            "/tabs/home.js",
            "/tabs/docs.js",
            "/tabs/apis.js",
            "/tabs/usage.js",
            "/tabs/ide.js",
        )
        for rel in static_paths:
            file_path = ROOT / "agent_dashboard" / "web" / rel.lstrip("/")
            self.assertTrue(file_path.is_file(), msg=f"missing module file {rel}")

    def test_daily_coder_serve_command_live_flag(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {"base_url": "http://127.0.0.1:8765"},
        )
        mock_cmd = adapter._serve_command("secret-tok", "mock")
        self.assertNotIn("--live", mock_cmd)
        self.assertIn("--provider", mock_cmd)
        self.assertEqual(mock_cmd[mock_cmd.index("--provider") + 1], "mock")

        for live in ("gemini", "openrouter", "openai", "anthropic", "local", "command", "http"):
            cmd = adapter._serve_command("secret-tok", live)
            self.assertIn("--live", cmd, msg=live)
            self.assertEqual(cmd[cmd.index("--provider") + 1], live)

    def test_daily_coder_backend_status_degraded_unauthorized_ready(self):
        adapter = DailyCoderAdapter(
            "daily-coder",
            "DC",
            "test",
            {"base_url": "http://127.0.0.1:9", "token": "tok"},
        )

        def online_health():
            return {"online": True, "detail": {}}

        with patch.object(adapter, "health", side_effect=online_health):
            with patch.object(adapter, "_request", side_effect=RuntimeError("daily-coder 500: boom")):
                status = adapter.backend_status()
                self.assertEqual(status["state"], "degraded")
                self.assertFalse(status["auth_ok"])
                self.assertFalse(adapter._auth_ok())

            with patch.object(adapter, "_request", side_effect=RuntimeError("daily-coder 401: unauthorized")):
                status = adapter.backend_status()
                self.assertEqual(status["state"], "unauthorized")
                self.assertFalse(status["auth_ok"])
                self.assertFalse(adapter._auth_ok())

            with patch.object(adapter, "_request", return_value=[]):
                status = adapter.backend_status()
                self.assertEqual(status["state"], "ready")
                self.assertTrue(status["auth_ok"])
                self.assertTrue(adapter._auth_ok())


class ApiSmokeTests(unittest.TestCase):
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

    def _get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_health_and_agents(self):
        health = self._get("/api/health")
        self.assertTrue(health["ok"])
        agents = self._get("/api/agents")
        self.assertGreaterEqual(len(agents), 2)

    def test_invalid_limit_returns_400(self):
        try:
            urllib.request.urlopen(self.base + "/api/agents/research-forge/runs?limit=abc", timeout=5)
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            body = json.loads(exc.read().decode("utf-8"))
            self.assertIn("limit", body.get("error", "").lower())

    def test_research_forge_start_and_thread(self):
        req = urllib.request.Request(
            self.base + "/api/agents/research-forge/runs",
            data=json.dumps({"request": "smoke test topic"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(body.get("accepted"))
        run_id = body["run_id"]

        req = urllib.request.Request(
            self.base + "/api/agents/research-forge/thread",
            data=json.dumps({"text": "steer: prefer primary sources", "run_id": run_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            msg = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(msg["status"], "queued")

        thread = self._get(f"/api/agents/research-forge/thread?run_id={run_id}")
        self.assertTrue(any(m.get("text", "").startswith("steer:") for m in thread))

    def test_static_serves_shell_modules(self):
        modules = (
            "/router.js",
            "/state.js",
            "/app.js",
            "/tabs/agent.js",
            "/tabs/ide.js",
            "/composer-picker.js",
            "/session-sidebar.js",
            "/slash-palette.js",
        )
        for path in modules:
            req = urllib.request.Request(self.base + path, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200, msg=path)
                body = resp.read()
                self.assertGreater(len(body), 10, msg=path)


class SetupRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = load_config(ROOT / "config" / "agents.json")
        cls._tmpdir = tempfile.TemporaryDirectory()
        reg = Registry(cfg, ROOT / "config", Path(cls._tmpdir.name))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.httpd.ctx = make_server_ctx(reg)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.httpd.server_address
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._tmpdir.cleanup()

    def _get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_expected_agents_includes_daily_task(self):
        data = self._get("/api/setup/expected-agents")
        ids = {e["id"] for e in data["expected"]}
        self.assertEqual(ids, {"daily-coder", "research-forge", "daily-task"})
        self.assertFalse(data["stale"])
        self.assertIn("daily-task", data["loaded"])

    def test_runtimes_returns_mock(self):
        data = self._get("/api/setup/runtimes")
        self.assertIn("providers", data)
        ids = [p["id"] for p in data["providers"]]
        self.assertIn("mock", ids)
        mock = next(p for p in data["providers"] if p["id"] == "mock")
        self.assertTrue(mock["configured"])
        self.assertNotIn("value", json.dumps(data))

    def test_palette_daily_coder_and_task(self):
        dc = self._get("/api/setup/palette?agent_id=daily-coder")
        self.assertIn("skills", dc)
        self.assertIn("subagents", dc)
        self.assertIn("items", dc)
        dt = self._get("/api/setup/palette?agent_id=daily-task")
        self.assertGreater(len(dt.get("subagents") or []), 0)


if __name__ == "__main__":
    unittest.main()
