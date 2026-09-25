"""G9 — workspace jail, terminal auth, traversal blocked."""
from __future__ import annotations

import json
import secrets
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler
from agent_dashboard.workspace_jail import resolve_in_root
from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceJailUnitTests(unittest.TestCase):
    def test_relative_to_blocks_dotdot(self):
        root = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(PermissionError):
                resolve_in_root(root, "../outside")
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)

    def test_windows_style_dotdot_segment(self):
        root = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(PermissionError):
                resolve_in_root(root, "foo/../../outside")
        finally:
            import shutil
            shutil.rmtree(root, ignore_errors=True)


class WorkspaceApiSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = load_config(ROOT / "config" / "agents.json")
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.data = Path(cls._tmpdir.name)
        reg = Registry(cfg, ROOT / "config", cls.data)
        cls.token = secrets.token_urlsafe(16)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.httpd.ctx = make_server_ctx(reg, auth_required=True, token=cls.token)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.httpd.server_address
        cls.base = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._tmpdir.cleanup()

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_workspace_requires_auth(self):
        req = urllib.request.Request(self.base + "/api/workspace/roots", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)

    def test_traversal_blocked_on_tree(self):
        with urllib.request.urlopen(
            urllib.request.Request(
                self.base + "/api/workspace/roots",
                headers=self._auth_headers(),
            ),
            timeout=10,
        ) as resp:
            roots = json.loads(resp.read().decode("utf-8"))["roots"]
        self.assertTrue(roots)
        root_id = roots[0]["id"]
        bad = f"{self.base}/api/workspace/tree?root={root_id}&path=..%2F..%2Fetc"
        req = urllib.request.Request(bad, headers=self._auth_headers())
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertIn(ctx.exception.code, (403, 404))

    def test_terminal_stop_and_auth(self):
        req = urllib.request.Request(self.base + "/api/terminal/profiles", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)

        spawn = urllib.request.Request(
            self.base + "/api/terminal/sessions",
            data=json.dumps({"profile_id": "echo"}).encode("utf-8"),
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(spawn, timeout=15) as resp:
            session = json.loads(resp.read().decode("utf-8"))
        sid = session["id"]

        stop = urllib.request.Request(
            self.base + f"/api/terminal/sessions/{sid}/stop",
            data=b"{}",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(stop, timeout=10) as resp:
            stopped = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(stopped["state"], "stopped")
