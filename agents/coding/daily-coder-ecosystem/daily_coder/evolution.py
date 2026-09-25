"""Controlled evolution.

One bounded candidate per cycle. Candidates are evaluated automatically against frozen
and held-out task sets, but a candidate never becomes the live default without explicit
human promotion. Every promotion keeps provenance and a rollback copy.
"""
from __future__ import annotations
import json, shlex, shutil, subprocess, time, uuid
from pathlib import Path
from .util import canonical_json, sha256_text

KINDS = {"prompt", "skill", "router", "harness"}

class EvolutionManager:
    def __init__(self, root, state, history_dir=None):
        self.root = Path(root)
        self.state = state
        self.history = Path(history_dir or (self.root / ".daily-coder" / "evolution"))
        self.history.mkdir(parents=True, exist_ok=True)

    def propose(self, kind, target, new_text, rationale, provenance):
        if kind not in KINDS:
            raise ValueError(f"unknown candidate kind: {kind}")
        active = [c for c in self.state.candidates() if c["state"] in ("proposed", "eligible", "promoting")]
        if active:
            raise RuntimeError(f"candidate {active[0]['candidate_id']} is still active; resolve it before proposing another")
        path = self._target_path(target)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current == new_text:
            return None
        candidate_id = str(uuid.uuid4())
        payload = canonical_json({"target": target, "new_text": new_text})
        (self.history / f"{candidate_id}.json").write_text(
            json.dumps({"candidate_id": candidate_id, "kind": kind, "target": target,
                        "previous": current, "proposed": new_text, "rationale": rationale,
                        "provenance": provenance, "created": time.time()}, indent=2), encoding="utf-8")
        self.state.add_candidate(candidate_id, kind, target, sha256_text(payload), rationale, json.dumps(provenance, sort_keys=True))
        return candidate_id

    def evaluate(self, candidate_id, frozen_result, holdout_result):
        """Automatic gate: improve on frozen tasks and never regress on held-out tasks."""
        improved = frozen_result.get("score", 0) >= frozen_result.get("baseline", 0)
        no_regression = holdout_result.get("score", 0) >= holdout_result.get("baseline", 0)
        verdict = "eligible" if (improved and no_regression) else "rejected"
        self.state.add_evaluation(candidate_id, "gate", verdict,
                                  {"frozen": frozen_result, "holdout": holdout_result})
        self.state.set_candidate_state(candidate_id, verdict)
        return verdict

    def evaluate_commands(self, candidate_id, frozen_command, holdout_command, timeout=1800):
        """Run two external gates. Both must pass before human promotion is possible."""
        def run(command):
            argv = command if isinstance(command, list) else shlex.split(command)
            started = time.time()
            cp = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=timeout)
            return {"score": 1 if cp.returncode == 0 else 0, "baseline": 1,
                    "returncode": cp.returncode, "duration_s": round(time.time() - started, 3),
                    "output": (cp.stdout + cp.stderr)[-4000:]}
        return self.evaluate(candidate_id, run(frozen_command), run(holdout_command))

    def promote(self, candidate_id, actor):
        """Human-gated. Only an eligible candidate can be promoted."""
        record = self._record(candidate_id)
        rows = [c for c in self.state.candidates() if c["candidate_id"] == candidate_id]
        if not rows:
            raise KeyError(candidate_id)
        if rows[0]["state"] != "eligible":
            raise PermissionError(f"candidate is {rows[0]['state']}; only an eligible candidate can be promoted")
        expected = sha256_text(canonical_json({"target": record["target"], "new_text": record["proposed"]}))
        if expected != rows[0]["diff"]:
            self.state.set_candidate_state(candidate_id, "rejected")
            raise PermissionError("candidate content does not match its evaluated fingerprint")
        path = self._target_path(record["target"])
        if path.exists():
            shutil.copy2(path, self.history / f"{candidate_id}.rollback")
        self.state.set_candidate_state(candidate_id, "promoting")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + f".{candidate_id}.tmp")
        temp.write_text(record["proposed"], encoding="utf-8")
        temp.replace(path)
        self.state.set_candidate_state(candidate_id, "promoted")
        self.state.add_evaluation(candidate_id, "promotion", "promoted", {"actor": actor})
        return {"candidate_id": candidate_id, "target": record["target"], "promoted_by": actor}

    def rollback(self, candidate_id, actor):
        record = self._record(candidate_id)
        backup = self.history / f"{candidate_id}.rollback"
        if not backup.exists():
            raise FileNotFoundError("no rollback copy for this candidate")
        shutil.copy2(backup, self._target_path(record["target"]))
        self.state.set_candidate_state(candidate_id, "rolled_back")
        self.state.add_evaluation(candidate_id, "rollback", "rolled_back", {"actor": actor})
        return {"candidate_id": candidate_id, "rolled_back_by": actor}

    def _record(self, candidate_id):
        path = self.history / f"{candidate_id}.json"
        if not path.exists():
            raise KeyError(candidate_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _target_path(self, target):
        normalized = str(target).replace("\\", "/")
        allowed = ((normalized.startswith("skills/") and normalized.endswith("/SKILL.md")) or
                   (normalized.startswith("agents/") and normalized.endswith("/prompt.md")) or
                   normalized in {"daily_coder/router.py", "daily_coder/workflow.py"})
        if not allowed:
            raise PermissionError("evolution target is outside prompt, skill, router, and workflow modules")
        path = (self.root / target).resolve()
        if self.root.resolve() not in path.parents:
            raise PermissionError("candidate target escapes the package root")
        return path
