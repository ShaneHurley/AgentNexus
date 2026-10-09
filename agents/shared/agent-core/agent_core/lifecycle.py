"""Single-host execution ownership and conservative recovery failures.

An OS lock proves local ownership without expiring a lease under a slow worker.
It is not a security sandbox or evidence of remote cancellation.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import os
import threading
import fcntl


class RunBusy(RuntimeError):
    """Another executor still owns this local run."""


class ReconciliationRequired(RuntimeError):
    """An external outcome must be resolved before dispatch can continue."""


_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_local = threading.local()


class RunLock:
    """Nonblocking process lock, reentrant in the owning thread.

    Keep the file: unlinking a lock file lets another process lock a new inode.
    The kernel releases ownership if the process dies, including SIGKILL.
    """
    def __init__(self, directory: Path, key: str):
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / (hashlib.sha256(key.encode()).hexdigest() + ".lock")
        with _guard:
            self.lock = _locks.setdefault(str(self.path), threading.RLock())

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            raise RunBusy("run already owned by another thread")
        states = getattr(_local, "states", None)
        if states is None:
            states = _local.states = {}
        key = str(self.path)
        if key in states:
            states[key][1] += 1
            return self
        fd = None
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunBusy("run already owned by another process") from exc
            states[key] = [fd, 1]
            return self
        except BaseException:
            if fd is not None: os.close(fd)
            self.lock.release()
            raise

    def __exit__(self, *exc):
        key = str(self.path)
        state = _local.states[key]
        state[1] -= 1
        try:
            if state[1] == 0:
                del _local.states[key]
                try:
                    fcntl.flock(state[0], fcntl.LOCK_UN)
                finally:
                    os.close(state[0])
        finally:
            self.lock.release()
