import importlib.util
import os
import signal
import subprocess
import sys
from pathlib import Path
import pytest


def lifecycle():
    assert importlib.util.find_spec("agent_core.lifecycle") is not None, "shared lifecycle guards missing"
    from agent_core import lifecycle
    return lifecycle


def test_lock_reentrant_and_released(tmp_path):
    m = lifecycle()
    with m.RunLock(tmp_path, "../../private/run"):
        with m.RunLock(tmp_path, "../../private/run"):
            assert len(list(tmp_path.glob("*.lock"))) == 1
    with m.RunLock(tmp_path, "../../private/run"):
        pass


def test_lock_blocks_other_process_and_releases_after_kill(tmp_path):
    m = lifecycle()
    package = str(Path(__file__).resolve().parents[1])
    code = "import sys; sys.path.insert(0, sys.argv[1]); from agent_core.lifecycle import RunLock; " + "\nwith RunLock(sys.argv[2], 'run'):\n print('ready', flush=True)\n sys.stdin.read()\n"
    child = subprocess.Popen([sys.executable, "-c", code, package, str(tmp_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(m.RunBusy):
            with m.RunLock(tmp_path, "run"):
                pytest.fail("concurrent executor admitted")
        child.kill(); child.wait(timeout=5)
        with m.RunLock(tmp_path, "run"):
            pass
    finally:
        if child.poll() is None: child.kill(); child.wait(timeout=5)
        child.stdin.close(); child.stdout.close()


def test_lock_rejects_symlink(tmp_path):
    m = lifecycle()
    import hashlib
    other = tmp_path / "other"; other.write_text("do not touch")
    (tmp_path / (hashlib.sha256(b"run").hexdigest() + ".lock")).symlink_to(other)
    with pytest.raises(OSError):
        with m.RunLock(tmp_path, "run"):
            pass
    assert other.read_text() == "do not touch"
