"""G5 — every registered hub path appears in /api/openapi.json."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from agent_dashboard.registry import Registry, load_config
from agent_dashboard.routes.meta import HUB_OPENAPI_PATHS
from agent_dashboard.server import _Handler
from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]

REGISTERED_GET = [
    "/api/health",
    "/api/openapi.json",
    "/api/agents",
    "/api/usage",
    "/api/home/snapshot",
    "/api/docs",
    "/api/config/overlay",
    "/api/setup/runtimes",
    "/api/setup/secrets",
    "/api/setup/palette",
    "/api/setup/expected-agents",
    "/api/workspace/roots",
    "/api/workspace/tree",
    "/api/workspace/file",
    "/api/terminal/profiles",
    "/api/terminal/sessions",
]

REGISTERED_POST = [
    "/api/config/overlay",
    "/api/setup/secrets",
    "/api/terminal/sessions",
]

REGISTERED_PUT = [
    "/api/workspace/file",
]


class OpenApiParityTests(unittest.TestCase):
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

    def test_openapi_lists_all_static_hub_paths(self):
        with urllib.request.urlopen(self.base + "/api/openapi.json", timeout=10) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
        paths = set(doc.get("paths", {}))
        for p in HUB_OPENAPI_PATHS:
            self.assertIn(p, paths, msg=f"missing openapi path {p}")

    def test_dispatch_modules_cover_registered_routes(self):
        """Sanity: static registry paths are declared in OpenAPI."""
        for p in REGISTERED_GET:
            self.assertIn(p, HUB_OPENAPI_PATHS)
        for p in REGISTERED_POST:
            spec = HUB_OPENAPI_PATHS[p]
            self.assertIn("post", spec)
        for p in REGISTERED_PUT:
            spec = HUB_OPENAPI_PATHS[p]
            self.assertIn("put", spec)
