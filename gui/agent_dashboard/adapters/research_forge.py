"""Research Forge adapter — filesystem + optional package imports.

No HTTP service required. Reads ledger/experiments from the package workspace and
accepts dashboard-owned steer notes / pending requests under data_dir.
"""
from __future__ import annotations
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchForgeAdapter:
    def __init__(self, agent_id: str, name: str, description: str, options: dict[str, Any], data_dir: Path):
        self.id = agent_id
        self.name = name
        self.description = description
        self.package_root = Path(options.get("package_root", ".")).resolve()
        self.workspace_root = Path(options.get("workspace_root", self.package_root)).resolve()
        self.inbox = data_dir / "research-forge"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self._ensure_path()

    def _ensure_path(self) -> None:
        src = self.package_root / "src"
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))

    def capabilities(self) -> list[str]:
        return ["health", "runs", "start", "approve", "resume", "cancel", "activity", "metrics", "steer", "backend"]

    def backend_status(self) -> dict[str, Any]:
        health = self.health()
        online = bool(health.get("online"))
        detail = health.get("detail")
        warn = ""
        if isinstance(detail, dict) and detail.get("warning"):
            warn = f" ({detail['warning']})"
        elif isinstance(detail, str) and not online:
            warn = f" ({detail})"
        if online:
            msg = "No separate server — uses the local package/workspace." + warn
        else:
            msg = "Package path missing or doctor failed." + warn
        return {
            "startable": False,
            "stoppable": False,
            "online": online,
            "auth_ok": online,
            "managed": False,
            "state": "ready" if online else "down",
            "message": msg,
            "base_url": None,
            "has_token": False,
            "pid": None,
        }

    def start_backend(self, *, force: bool = False, provider: str | None = None) -> dict[str, Any]:
        return {"ok": True, "already_running": True, "backend": self.backend_status()}

    def stop_backend(self, *, force: bool = False) -> dict[str, Any]:
        return {"ok": True, "stopped": False, "backend": self.backend_status()}

    def set_backend_token(self, token: str) -> dict[str, Any]:
        return {"ok": True, "backend": self.backend_status()}

    def clear_secrets(self) -> None:
        return

    def health(self) -> dict[str, Any]:
        if not (self.package_root / "pyproject.toml").is_file():
            return {"online": False, "detail": f"package_root missing: {self.package_root}"}
        try:
            from research_forge.settings import load_settings
            from research_forge.wave0.doctor import run_doctor
            settings = load_settings(self.package_root)
            report = run_doctor(self.package_root, settings)
            return {"online": bool(report.get("ok")), "detail": report}
        except ModuleNotFoundError as exc:  # noqa: BLE001
            missing = getattr(exc, "name", None) or str(exc)
            return {
                "online": True,
                "detail": {
                    "ok": True,
                    "warning": f"Doctor skipped — missing dependency '{missing}'. Install research-forge deps for full doctor.",
                    "package_root": str(self.package_root),
                    "workspace_root": str(self.workspace_root),
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "online": False,
                "detail": {
                    "ok": False,
                    "warning": str(exc),
                    "package_root": str(self.package_root),
                    "workspace_root": str(self.workspace_root),
                },
            }

    def _ledger_path(self) -> Path:
        return self.workspace_root / "runs" / "ledger.jsonl"

    def _experiment_root(self) -> Path:
        # Prefer package config; fall back to common layout.
        candidate = self.workspace_root / ".research-forge" / "experiments"
        if candidate.is_dir():
            return candidate
        return self.workspace_root / "experiments"

    def _pending_path(self) -> Path:
        return self.inbox / "pending_requests.jsonl"

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        # Dashboard-owned pending / started requests
        if self._pending_path().is_file():
            for line in self._pending_path().read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                runs.append(self._normalize_pending(item))
        # Experiments
        root = self._experiment_root()
        if root.is_dir():
            for d in sorted(root.iterdir(), reverse=True):
                if not d.is_dir() or not d.name.startswith("EXP-"):
                    continue
                status = {}
                status_file = d / "status.json"
                if status_file.is_file():
                    status = json.loads(status_file.read_text(encoding="utf-8"))
                proposal = {}
                for name in ("proposal.json", "create.json", "meta.json"):
                    p = d / name
                    if p.is_file():
                        proposal = json.loads(p.read_text(encoding="utf-8"))
                        break
                runs.append({
                    "run_id": d.name,
                    "agent_id": self.id,
                    "status": status.get("status", "UNKNOWN"),
                    "phase": status.get("phase", "experiment"),
                    "request": proposal.get("title") or proposal.get("question") or d.name,
                    "updated_at": status.get("updated_at") or "",
                    "est_usd": 0.0,
                    "profile": "experiment",
                    "raw": {"status": status, "proposal": proposal},
                })
        # Ledger run ids
        ledger = self._ledger_path()
        if ledger.is_file():
            seen: set[str] = set()
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                rid = ev.get("run_id")
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                runs.append({
                    "run_id": rid,
                    "agent_id": self.id,
                    "status": "LEDGER",
                    "phase": ev.get("event_type", ""),
                    "request": f"ledger run {rid}",
                    "updated_at": ev.get("ts", ""),
                    "est_usd": 0.0,
                    "profile": "ledger",
                    "raw": {"last_event": ev},
                })
        # newest first when timestamps exist; else keep order
        return runs[:limit]

    def get_run(self, run_id: str) -> dict[str, Any]:
        for run in self.list_runs(limit=500):
            if run["run_id"] == run_id:
                return run
        raise KeyError(run_id)

    def start_run(self, request: str, **kwargs: Any) -> dict[str, Any]:
        # Persist forced_subagents / UI prefs on inbox artifact; ignore unknown keys safely.
        run_id = f"RF-{uuid.uuid4().hex[:10]}"
        forced = kwargs.get("forced_subagents") or []
        if not isinstance(forced, list):
            forced = [forced]
        item = {
            "run_id": run_id,
            "request": request,
            "status": "QUEUED",
            "phase": "intake",
            "created_at": _now(),
            "updated_at": _now(),
            "notes": kwargs.get("notes") or "",
            "mode": kwargs.get("mode") or "mock",
            "forced_subagents": forced,
        }
        with self._pending_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        artifact = self.inbox / f"{run_id}.request.json"
        artifact.write_text(json.dumps({
            "run_id": run_id,
            "topic": request,
            "objective": request,
            "mode": item["mode"],
            "forced_subagents": forced,
            "created_via": "agent-dashboard",
            "created_at": item["created_at"],
        }, indent=2), encoding="utf-8")
        return {"accepted": True, "run_id": run_id, "artifact": str(artifact), "forced_subagents": forced}

    def approve(self, run_id: str, *, reject: bool = False, note: str | None = None, kind: str = "plan") -> dict[str, Any]:
        decision = "rejected" if reject else "approved"
        path = self.inbox / f"{run_id}.decision.json"
        path.write_text(json.dumps({
            "run_id": run_id,
            "kind": kind,
            "decision": decision,
            "note": note,
            "actor": "agent-dashboard",
            "at": _now(),
        }, indent=2), encoding="utf-8")
        self._patch_pending(run_id, status="REJECTED" if reject else "APPROVED", phase="human_gate")
        return {"decided": True, "state": decision, "path": str(path)}

    def resume(self, run_id: str) -> dict[str, Any]:
        """Resume a paused Wave 1 run from durable state when available (REC-06)."""
        from research_forge.decisions.validator import validate_decisions_for_gate
        from research_forge.errors import ErrorCode, forge_error
        from research_forge.wave1.orchestrator import Wave1Orchestrator
        from research_forge.wave1.persistence import load_run_state, save_run_state

        try:
            state, meta = load_run_state(self.package_root, run_id)
        except FileNotFoundError:
            note = self.inbox / f"{run_id}.resume.json"
            note.write_text(
                json.dumps({"run_id": run_id, "action": "resume", "at": _now(), "failed": "NOT_FOUND"}, indent=2),
                encoding="utf-8",
            )
            return {
                "accepted": False,
                "run_id": run_id,
                "error": forge_error(
                    ErrorCode.NOT_FOUND,
                    f"No persisted state for run {run_id}",
                    hint="Run wave1 first so state is saved under runs/wave1/<run_id>/state.json",
                ).to_dict(),
                "inbox_note": str(note),
            }
        except ValueError as exc:
            return {
                "accepted": False,
                "run_id": run_id,
                "error": forge_error(ErrorCode.SCHEMA_INVALID, str(exc)).to_dict(),
            }

        use_live = bool(meta.get("live"))
        if use_live:
            ok_live, live_msgs = validate_decisions_for_gate(self.package_root, "wave_1_live")
            if not ok_live:
                return {
                    "accepted": False,
                    "run_id": run_id,
                    "error": forge_error(
                        ErrorCode.POLICY_DENIED,
                        "Live mode blocked",
                        failures=live_msgs,
                    ).to_dict(),
                }

        answers: dict[str, str] = {}
        answers_path = self.inbox / f"{run_id}.answers.json"
        if answers_path.is_file():
            try:
                raw = json.loads(answers_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    answers = {str(k): str(v) for k, v in raw.items()}
            except json.JSONDecodeError:
                answers = {}

        self._patch_pending(run_id, status="ACTIVE", phase="resume_requested")
        note = self.inbox / f"{run_id}.resume.json"
        note.write_text(
            json.dumps({"run_id": run_id, "action": "resume", "at": _now()}, indent=2),
            encoding="utf-8",
        )
        try:
            orch = Wave1Orchestrator(self.package_root, live=use_live)
            result = orch.resume(state, answers)
            if isinstance(result.get("state"), dict) and result["state"].get("run_id"):
                save_run_state(self.package_root, result["state"], live=use_live)
            self._patch_pending(
                run_id,
                status="DONE" if result.get("ok") and not result.get("paused") else "ACTIVE",
                phase=(result.get("state") or {}).get("phase") or "resumed",
            )
            return {
                "accepted": True,
                "run_id": run_id,
                "ok": bool(result.get("ok")),
                "paused": bool(result.get("paused")),
                "phase": (result.get("state") or {}).get("phase"),
                "persisted": True,
                "inbox_note": str(note),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "accepted": False,
                "run_id": run_id,
                "error": forge_error(ErrorCode.INTERNAL_ERROR, str(exc)).to_dict(),
                "inbox_note": str(note),
            }

    def cancel(self, run_id: str) -> dict[str, Any]:
        self._patch_pending(run_id, status="CANCELLED", phase="cancelled")
        return {"cancelled": True, "run_id": run_id}

    def pending_approvals(self) -> list[dict[str, Any]]:
        out = []
        for run in self.list_runs(limit=100):
            if run.get("status") in ("QUEUED", "WAITING_HUMAN", "APPROVED"):
                if run.get("status") == "QUEUED":
                    out.append({
                        "run_id": run["run_id"],
                        "agent_id": self.id,
                        "kind": "intake",
                        "summary": (run.get("request") or "")[:120],
                    })
        return out

    def activity(self, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        ledger = self._ledger_path()
        if ledger.is_file():
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                if run_id and ev.get("run_id") != run_id:
                    continue
                items.append({
                    "ts": str(ev.get("ts") or ""),
                    "agent_id": self.id,
                    "run_id": ev.get("run_id", ""),
                    "role": ev.get("actor") or "",
                    "kind": ev.get("event_type") or "event",
                    "summary": json.dumps(ev.get("payload") or {})[:160],
                })
        for p in sorted(self.inbox.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if run_id and data.get("run_id") != run_id:
                continue
            items.append({
                "ts": data.get("at") or data.get("created_at") or "",
                "agent_id": self.id,
                "run_id": data.get("run_id", ""),
                "role": "dashboard",
                "kind": p.suffix and p.name.split(".")[1] if "." in p.name else "artifact",
                "summary": p.name,
            })
        return items[-limit:]

    def metrics(self) -> dict[str, Any]:
        runs = self.list_runs(limit=200)
        return {
            "totals": {
                "runs": len(runs),
                "queued": sum(1 for r in runs if r.get("status") == "QUEUED"),
                "active": sum(1 for r in runs if r.get("status") in ("ACTIVE", "LEDGER")),
            },
            "package_root": str(self.package_root),
            "workspace_root": str(self.workspace_root),
        }

    def _normalize_pending(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": item["run_id"],
            "agent_id": self.id,
            "status": item.get("status", "QUEUED"),
            "phase": item.get("phase", "intake"),
            "request": item.get("request", ""),
            "updated_at": item.get("updated_at") or item.get("created_at") or "",
            "est_usd": 0.0,
            "profile": item.get("mode", "mock"),
            "raw": item,
        }

    def _patch_pending(self, run_id: str, **fields: Any) -> None:
        path = self._pending_path()
        if not path.is_file():
            return
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("run_id") == run_id:
                item.update(fields)
                item["updated_at"] = _now()
            rows.append(item)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
