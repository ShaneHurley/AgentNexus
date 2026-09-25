"""Home snapshot TTL cache."""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler
from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]


class HomeSnapshotTests(unittest.TestCase):
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

    def test_snapshot_returns_agents(self):
        with urllib.request.urlopen(self.base + "/api/home/snapshot", timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("agents", data)
        self.assertGreaterEqual(len(data["agents"]), 2)

    def test_snapshot_cache_ttl_unit(self):
        from agent_dashboard.routes.home import SnapshotCache

        cache = SnapshotCache(ttl_seconds=0.2)
        calls = {"n": 0}

        def builder():
            calls["n"] += 1
            return {"n": calls["n"]}

        self.assertEqual(cache.get(builder)["n"], 1)
        self.assertEqual(cache.get(builder)["n"], 1)
        time.sleep(0.25)
        self.assertEqual(cache.get(builder)["n"], 2)
