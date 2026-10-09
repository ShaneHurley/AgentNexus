"""ANX-0 HTTP authentication and browser-boundary regressions."""
import http.client
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from agent_dashboard.server import _Handler

class DashboardBoundaryTests(unittest.TestCase):
    def setUp(self):
        for name in ("dispatch_get", "dispatch_post", "dispatch_put"):
            mock = patch("agent_dashboard.server." + name, return_value=False)
            mock.start()
            self.addCleanup(mock.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.ctx = {"auth_required": False, "token": "test-token"}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.authority = "127.0.0.1:%s" % self.server.server_port
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
    def request(self, method="GET", headers=None, path="/api/nonexistent"):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request(method, path, body=b"{}" if method != "GET" else None, headers=headers or {})
        response = conn.getresponse()
        status = response.status
        response.read()
        conn.close()
        return status
    def test_local_mutation_requires_token_even_with_legacy_false(self):
        self.assertEqual(self.request("POST"), 401)
    def test_valid_header_cli_request(self):
        self.assertEqual(self.request(headers={"Authorization": "Bearer test-token"}), 404)
    def test_foreign_host_rejected_even_with_valid_token(self):
        self.assertEqual(self.request(headers={"Host": "attacker.example", "X-Api-Token": "test-token"}), 403)
    def test_origin_rejected_before_auth(self):
        for origin in ("http://attacker.example", "null", "http://127.0.0.1:1", "https://" + self.authority):
            with self.subTest(origin=origin):
                self.assertEqual(self.request("POST", {"Origin": origin, "X-Api-Token": "test-token"}), 403)
    def test_same_endpoint_origin_and_cli_allowed(self):
        self.assertEqual(self.request("POST", {"Origin": "http://" + self.authority, "X-Api-Token": "test-token"}), 404)
    def test_query_token_cannot_authenticate(self):
        self.assertEqual(self.request(path="/api/nonexistent?token=test-token"), 401)
    def test_static_foreign_host_rejected(self):
        self.assertEqual(self.request(headers={"Host": "attacker.example"}, path="/"), 403)

class StartupSecurityTests(unittest.TestCase):
    def test_startup_omits_raw_token_and_uses_assigned_port(self):
        from agent_dashboard.server import serve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "agents.json"
            config.write_text(json.dumps({"agents": [], "auth_required": False}))
            server = MagicMock()
            server.server_port = 12345
            registry = MagicMock()
            registry.adapters = {}
            output = io.StringIO()
            with patch("agent_dashboard.server.project_root", return_value=root), \
                    patch("agent_dashboard.server.resolve_data_dir", return_value=root / "data"), \
                    patch("agent_dashboard.server.Registry", return_value=registry), \
                    patch("agent_dashboard.server.ThreadingHTTPServer", return_value=server), \
                    contextlib.redirect_stdout(output):
                serve(config, port=0, token="secret-never-printed")
            self.assertNotIn("secret-never-printed", output.getvalue())
            self.assertIn("12345", output.getvalue())
            self.assertTrue(server.ctx["auth_required"])
    def test_missing_token_fails_closed(self):
        from agent_dashboard.server import serve
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "agents.json"
            config.write_text('{"agents": []}')
            with patch.dict("os.environ", {"AGENT_DASHBOARD_TOKEN": ""}), \
                    patch("agent_dashboard.server.project_root", return_value=root), \
                    patch("agent_dashboard.server.resolve_data_dir", return_value=root / "data"), \
                    self.assertRaises(SystemExit) as exc:
                serve(config)
            self.assertIn("AGENT_DASHBOARD_TOKEN", str(exc.exception))

class CleanCheckoutConfigTests(unittest.TestCase):
    def test_missing_private_config_uses_reviewed_example_without_writing(self):
        from agent_dashboard.registry import load_config
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "agents.json"
            config.with_name("agents.json.example").write_text('{"auth_required": true, "agents": []}')
            self.assertTrue(load_config(config)["auth_required"])
            self.assertFalse(config.exists())
    def test_other_missing_config_does_not_fall_back(self):
        from agent_dashboard.registry import load_config
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "custom.json"
            config.with_name("custom.json.example").write_text('{}')
            with self.assertRaises(FileNotFoundError):
                load_config(config)

class BrowserTokenTests(unittest.TestCase):
    def test_memory_only_token_entry_and_header_transport(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("Node required for browser API module contract test")
        source = Path(__file__).resolve().parents[1] / "agent_dashboard/web/api.js"
        script = r"""
          import fs from 'node:fs';
          import assert from 'node:assert/strict';
          let removed = false;
          globalThis.sessionStorage = {
            getItem() { throw Error('credential read from storage'); },
            setItem() { throw Error('credential persisted'); },
            removeItem(key) { assert.equal(key, 'ad_token'); removed = true; }
          };
          globalThis.fetch = async (path, options) => {
            assert.equal(path, '/api/agents');
            assert.equal(options.headers['X-Api-Token'], 'memory-secret');
            return {ok: true, text: async () => '{}'};
          };
          const client = await import('data:text/javascript;base64,' + fs.readFileSync(process.argv[1]).toString('base64'));
          assert.equal(client.getToken(), '');
          assert.equal(removed, true);
          client.setToken('memory-secret');
          await client.api('/api/agents');
        """
        result = subprocess.run([node, "--input-type=module", "-e", script, str(source)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
