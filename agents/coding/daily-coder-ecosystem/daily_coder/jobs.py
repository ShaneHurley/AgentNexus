"""Durable background jobs.

Long test suites run detached. The run transitions to WAITING_JOB and makes no provider
calls while waiting, so a multi-hour suite costs zero tokens. Duration history lets the
scheduler predict how long the next run of the same suite will take.
"""
from __future__ import annotations
import json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
from .util import canonical_json, sha256_text

def fingerprint(repo, argv) -> str:
    return sha256_text(canonical_json({"repo": str(repo), "argv": list(argv)}))

class JobManager:
    def __init__(self, state, log_dir):
        self.state = state
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def estimate(self, repo, argv):
        return self.state.duration_estimate(fingerprint(repo, argv))

    def start(self, run_id, argv, cwd, kind="tests", timeout_s=0):
        job_id = str(uuid.uuid4())
        log_path = self.log_dir / f"{job_id}.log"
        fp = fingerprint(cwd, argv)
        self.state.create_job(job_id, run_id, kind, argv, cwd, log_path, fp, timeout_s)
        handle = log_path.open("w", encoding="utf-8")
        result_path = Path(str(log_path) + ".result.json")
        wrapper = [sys.executable, str(Path(__file__).with_name("job_runner.py")), "--result", str(result_path),
               "--timeout", str(timeout_s), "--", *argv]
        creation = {}
        if os.name == "nt":
            creation["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            creation["start_new_session"] = True
        proc = subprocess.Popen(wrapper, cwd=str(cwd), stdout=handle, stderr=subprocess.STDOUT,
                                text=True, env={k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "HOME", "PYTHONIOENCODING")},
                                **creation)
        handle.close()
        self.state.start_job(job_id, proc.pid)
        return {"job_id": job_id, "pid": proc.pid, "log": str(log_path), "estimate": self.state.duration_estimate(fp)}

    def poll(self, job_id):
        """Non-blocking status check. Recovers state after a runtime restart."""
        job = self.state.get_job(job_id)
        if job["state"] in ("succeeded", "failed", "cancelled", "timeout"):
            return job
        result_path = Path(str(job["log_path"]) + ".result.json")
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            tail = _tail(job["log_path"])
            result_hash = sha256_text(tail)
            self.state.finish_job(job_id, result["state"], result.get("exit_code"), result_hash)
            return self.state.get_job(job_id)
        pid = job["pid"]
        alive = _alive(pid) if pid else False
        if alive:
            self.state.heartbeat_job(job_id)
            if job["timeout_s"] and job["started"] and time.time() - job["started"] > job["timeout_s"]:
                self.cancel(job_id, state="timeout")
                return self.state.get_job(job_id)
            return self.state.get_job(job_id)
        # The wrapper is gone but no result marker exists: treat this as an interrupted job.
        tail = _tail(job["log_path"])
        self.state.finish_job(job_id, "failed", -1, sha256_text(tail))
        return self.state.get_job(job_id)

    def cancel(self, job_id, state="cancelled"):
        job = self.state.get_job(job_id)
        if job["pid"]:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(job["pid"]), "/T", "/F"], capture_output=True)
                else:
                    os.killpg(job["pid"], signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        self.state.finish_job(job_id, state, None, None)
        return self.state.get_job(job_id)

    def evidence(self, job_id):
        job = self.state.get_job(job_id)
        return {"job_id": job_id, "state": job["state"], "exit_code": job["exit_code"],
                "argv": json.loads(job["argv"]), "duration_s": (job["finished"] or time.time()) - (job["started"] or time.time()),
                "output_tail": _tail(job["log_path"])}


def _alive(pid) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OSError):
        return False
    return True

def _tail(path, limit=20000):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:]
