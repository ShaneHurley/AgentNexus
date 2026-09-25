"""Config overlay + docs API."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from agent_dashboard.config_overlay import overlay_path
from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler
from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]


class ConfigDocsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = load_config(ROOT / "config" / "agents.json")
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.data = Path(cls._tmpdir.name)
        reg = Registry(cfg, ROOT / "config", cls.data)
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

    def test_overlay_rejects_unknown_keys(self):
        req = urllib.request.Request(
            self.base + "/api/config/overlay",
            data=json.dumps({"secret_token": "nope", "host": "127.0.0.1"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 400)

    def test_overlay_rejects_host_port_auth(self):
        req = urllib.request.Request(
            self.base + "/api/config/overlay",
            data=json.dumps({"port": 8866, "auth_required": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 400)

    def test_overlay_writes_under_data_dir_only(self):
        req = urllib.request.Request(
            self.base + "/api/config/overlay",
            data=json.dumps({"workspace_roots": ["./docs"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(body.get("ok"))
        path = overlay_path(self.data)
        self.assertTrue(path.is_file())
        repo_agents = ROOT / "config" / "agents.json"
        before = repo_agents.read_text(encoding="utf-8")
        written = path.read_text(encoding="utf-8")
        self.assertIn("workspace_roots", written)
        self.assertIn("docs", written)
        self.assertEqual(before, repo_agents.read_text(encoding="utf-8"))

    def test_docs_list_and_fetch(self):
        with urllib.request.urlopen(self.base + "/api/docs", timeout=10) as resp:
            docs = json.loads(resp.read().decode("utf-8"))["docs"]
        names = {d["name"] for d in docs}
        self.assertIn("ARCHITECTURE.md", names)

        with urllib.request.urlopen(self.base + "/api/docs/ARCHITECTURE", timeout=10) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
        self.assertIn("Architecture", doc["content"])

    def test_docs_traversal_blocked(self):
        req = urllib.request.Request(self.base + "/api/docs/..%2F..%2Fetc%2Fpasswd", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 404)
