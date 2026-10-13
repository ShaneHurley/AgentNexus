"""Opt-in acceptance against the reviewed local Docker image; no host fallback."""
import os
import subprocess
import time
from pathlib import Path

import pytest
from agent_core.isolation import DockerRunner

IMAGE = "python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTNEXUS_LIVE_DOCKER") != "1",
    reason="explicit local Docker acceptance only",
)


def container_ids():
    return set(subprocess.run(
        ["docker", "ps", "-aq"], check=True, capture_output=True, text=True,
    ).stdout.split())


def test_real_worker_pass_failure_timeout_cancellation_and_cleanup(tmp_path):
    (tmp_path / "test_fixture.py").write_text(
        "import unittest\n"
        "class Fixture(unittest.TestCase):\n"
        "    def test_boundary(self):\n"
        "        self.assertEqual(1, 0)\n"
    )
    runner = DockerRunner(IMAGE, tmp_path)
    before = container_ids()
    passing = runner.run(["python", "-c", "print(42)"], timeout=10)
    assert passing["returncode"] == 0 and passing["stdout"].strip() == "42"
    assert passing["image"] == IMAGE
    assert "test_fixture.py" in passing["source_hashes"]
    assert len(passing["source_snapshot_sha256"]) == 64
    failing = runner.run(["python", "-m", "unittest", "discover"], timeout=10)
    assert failing["returncode"] == 1 and "FAILED" in failing["stderr"]
    timed = runner.run(["python", "-c", "import time; time.sleep(30)"], timeout=1)
    assert timed["timeout"] and not timed["cancelled"]
    started = time.monotonic()
    cancelled = runner.run(
        ["python", "-c", "import time; time.sleep(30)"], timeout=10,
        cancel_check=lambda: time.monotonic() - started > 1,
    )
    assert cancelled["cancelled"] and cancelled["cancellation_confirmed"]
    assert not (container_ids() - before), "worker container remained after cleanup"
