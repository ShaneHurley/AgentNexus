"""Storage and queue interfaces.

SQLite plus the in-process worker is the supported path today and satisfies every
requirement of single-host use. These interfaces exist so multi-host deployment is a
configuration change rather than a rewrite. They are deliberately inert: nothing in the
runtime selects a distributed backend yet, and the stubs fail closed if asked to.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class RunRepository(Protocol):
    """The subset of StateStore that a non-SQLite backend must reproduce."""
    def create(self, run_id, request, repo, config_hash, idem_key, **meta): ...
    def get(self, run_id): ...
    def transition(self, run_id, new_phase, payload, idem_key): ...
    def set_status(self, run_id, status): ...
    def add_usage(self, run_id, role, input_tokens, output_tokens): ...
    def total_usage(self, run_id): ...
    def record_artifact(self, h, run_id, kind, path, producer): ...

@runtime_checkable
class JobQueue(Protocol):
    """Work distribution. The local implementation runs jobs in-process."""
    def enqueue(self, job): ...
    def lease(self, worker_id, lease_seconds): ...
    def heartbeat(self, job_id, worker_id): ...
    def complete(self, job_id, worker_id, result): ...

class LocalQueue:
    """Single-host queue. Jobs are started directly by JobManager, so this is a pass-through."""
    def __init__(self, state):
        self.state = state
    def enqueue(self, job):
        return job
    def lease(self, worker_id, lease_seconds):
        return None
    def heartbeat(self, job_id, worker_id):
        self.state.heartbeat_job(job_id)
    def complete(self, job_id, worker_id, result):
        self.state.finish_job(job_id, result.get("state", "succeeded"), result.get("exit_code"), result.get("result_hash"))

class PostgresRepository:
    """Multi-host state backend.

    TODO(multi-host): implement using the same SQL shape as StateStore with
    `SELECT ... FOR UPDATE` on run rows, an advisory lock per run_id for transitions,
    and a `workers` table carrying lease expiry. Until then this fails closed so a
    misconfiguration cannot silently split run authority across hosts.
    """
    def __init__(self, dsn):
        raise NotImplementedError(
            "multi-host Postgres state is not enabled; use SQLite on a single host")

class DistributedQueue:
    """Multi-host work queue.

    TODO(multi-host): implement lease acquisition, heartbeat renewal, visibility timeout,
    and orphan recovery. Worker enrollment must be authenticated before this is enabled.
    """
    def __init__(self, url):
        raise NotImplementedError(
            "distributed job execution is not enabled; jobs run on the orchestrating host")
