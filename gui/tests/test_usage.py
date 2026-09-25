"""G7 — usage.jsonl hooks and GET /api/usage."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from agent_dashboard.metrics_normalize import normalize_metrics
from agent_dashboard.registry import Registry, load_config
from agent_dashboard.server import _Handler
from tests.test_server_ctx import make_server_ctx

ROOT = Path(__file__).resolve().parents[1]


class NormalizeMetricsTests(unittest.TestCase):
    def test_research_forge_shape_has_null_gaps(self):
        raw = {
            "totals": {"runs": 3, "queued": 1, "active": 0},
            "package_root": "/x",
        }
        out = normalize_metrics("research-forge", raw)
        self.assertEqual(out["agent_id"], "research-forge")
        self.assertEqual(out["totals"]["runs"], 3)
        self.assertEqual(out["totals"]["queued"], 1)
        self.assertIsNone(out["totals"]["waiting_human"])
        self.assertIsNone(out["roles"])

    def test_daily_coder_like_shape(self):
        raw = {
            "totals": {"runs": 10, "active": 2, "complete": 7, "failed": 1},
            "roles": {"planner": {"calls": 1, "tokens": 2, "usd": 0.01}},
            "today": {"usd": 0.5},
        }
        out = normalize_metrics("daily-coder", raw)
        self.assertEqual(out["totals"]["complete"], 7)
        self.assertAlmostEqual(out["spend_usd"], 0.5)
        self.assertIn("planner", out["roles"])


class UsageApiTests(unittest.TestCase):
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

    def test_run_start_appends_usage_jsonl(self):
        req = urllib.request.Request(
            self.base + "/api/agents/research-forge/runs",
            data=json.dumps({"request": "usage hook test"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        run_id = body["run_id"]

        with urllib.request.urlopen(self.base + "/api/usage", timeout=10) as resp:
            usage = json.loads(resp.read().decode("utf-8"))
        events = [e for e in usage["events"] if e.get("run_id") == run_id]
        self.assertTrue(any(e.get("event") == "run_start" for e in events))

    def test_usage_bucket_day(self):
        store = self.httpd.ctx["usage_store"]
        store.append("approve", "research-forge", run_id="R1", meta={})
        with urllib.request.urlopen(self.base + "/api/usage?bucket=day", timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(data["buckets"])
        self.assertIn("metrics", data)
        self.assertGreaterEqual(len(data["metrics"]), 1)
