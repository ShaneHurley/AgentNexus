"""Daily Task adapter — filesystem inbox for browser-router paste families.

No HTTP service. Lists families under the package root and accepts dashboard-owned
task/session requests under data_dir. Honest capabilities; startable:false.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


KNOWN_FAMILIES = (
    "plans-and-places",
    "kitchen-cooking",
    "learning-coach",
    "writing-studio",
    "thinking-lab",
    "mission-control",
)


class DailyTaskAdapter:
    def __init__(self, agent_id: str, name: str, description: str, options: dict[str, Any], data_dir: Path):
        self.id = agent_id
        self.name = name
        self.description = description
        self.package_root = Path(options.get("package_root", ".")).resolve()
        self.families_root = Path(
            options.get("families_root")
            or (self.package_root / "browser" / "families")
        ).resolve()
        self.inbox = data_dir / "daily-task"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> list[str]:
        return ["health", "runs", "start", "approve", "resume", "cancel", "activity", "metrics", "steer", "backend"]

    def backend_status(self) -> dict[str, Any]:
        health = self.health()
        online = bool(health.get("online"))
        return {
            "startable": False,
            "stoppable": False,
            "online": online,
            "auth_ok": online,
            "managed": False,
            "state": "ready" if online else "down",
            "message": (
                "No separate server — browser/router paste families via local package."
                if online
                else "Daily Task package path missing or incomplete."
            ),
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
        router = self.package_root / "ROUTER.yaml"
        driver = self.package_root / "driver.py"
        if not router.is_file() and not driver.is_file():
            return {"online": False, "detail": f"package_root missing markers: {self.package_root}"}
        families = self._list_families()
        if not families:
            return {
                "online": False,
                "detail": {
                    "ok": False,
                    "warning": "No browser families found",
                    "package_root": str(self.package_root),
                    "families_root": str(self.families_root),
                },
            }
        return {
            "online": True,
            "detail": {
                "ok": True,
                "package_root": str(self.package_root),
                "families_root": str(self.families_root),
                "families": families,
                "authority": "browser RCC paste harness — not IDE PolicyGateway",
            },
        }

    def _list_families(self) -> list[str]:
        if not self.families_root.is_dir():
            return list(KNOWN_FAMILIES) if (self.package_root / "ROUTER.yaml").is_file() else []
        found = []
        for d in sorted(self.families_root.iterdir()):
            if d.is_dir() and not d.name.startswith(".") and (d / "AGENT_MESSAGE.md").is_file():
                found.append(d.name)
        return found or list(KNOWN_FAMILIES)

    def _pending_path(self) -> Path:
        return self.inbox / "pending_requests.jsonl"

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        if self._pending_path().is_file():
            for line in self._pending_path().read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                runs.append(self._normalize_pending(item))
        runs.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> dict[str, Any]:
        for run in self.list_runs(limit=500):
            if run["run_id"] == run_id:
                return run
        raise KeyError(run_id)

    def start_run(self, request: str, **kwargs: Any) -> dict[str, Any]:
        run_id = f"DT-{uuid.uuid4().hex[:10]}"
        family = (kwargs.get("family") or kwargs.get("context") or "mission-control")
        if isinstance(family, str) and family not in self._list_families():
            # Allow forced subagent id like "family/variant"
            forced = kwargs.get("forced_subagents") or []
            if isinstance(forced, list) and forced:
                first = str(forced[0])
                fam = first.split("/", 1)[0]
                if fam in self._list_families():
                    family = fam
            elif isinstance(family, str) and "/" in family:
                fam = family.split("/", 1)[0]
                if fam in self._list_families():
                    family = fam
            if family not in self._list_families():
                family = "mission-control"
        forced = kwargs.get("forced_subagents") or []
        if not isinstance(forced, list):
            forced = [forced]
        item = {
            "run_id": run_id,
            "request": request,
            "status": "QUEUED",
            "phase": "intake",
            "family": family,
            "created_at": _now(),
            "updated_at": _now(),
            "notes": kwargs.get("notes") or "",
            "mode": kwargs.get("mode") or "paste",
            "forced_subagents": forced,
        }
        with self._pending_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        artifact = self.inbox / f"{run_id}.request.json"
        artifact.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "topic": request,
                    "family": family,
                    "mode": item["mode"],
                    "forced_subagents": forced,
                    "created_via": "agent-dashboard",
                    "created_at": item["created_at"],
                    "hint": "Paste AGENT_MESSAGE from the family into a browser chat; label STATUS honestly.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"accepted": True, "run_id": run_id, "artifact": str(artifact), "family": family, "forced_subagents": forced}

    def approve(self, run_id: str, *, reject: bool = False, note: str | None = None, kind: str = "plan") -> dict[str, Any]:
        decision = "rejected" if reject else "approved"
        path = self.inbox / f"{run_id}.decision.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "kind": kind,
                    "decision": decision,
                    "note": note,
                    "actor": "agent-dashboard",
                    "at": _now(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._patch_pending(run_id, status="REJECTED" if reject else "APPROVED", phase="human_gate")
        return {"decided": True, "state": decision, "path": str(path)}

    def resume(self, run_id: str) -> dict[str, Any]:
        note = self.inbox / f"{run_id}.resume.json"
        note.write_text(
            json.dumps({"run_id": run_id, "action": "resume", "at": _now()}, indent=2),
            encoding="utf-8",
        )
        self._patch_pending(run_id, status="ACTIVE", phase="resume_requested")
        return {
            "accepted": True,
            "run_id": run_id,
            "inbox_note": str(note),
            "hint": "No HTTP runtime — resume is an inbox signal for the paste harness.",
        }

    def cancel(self, run_id: str) -> dict[str, Any]:
        self._patch_pending(run_id, status="CANCELLED", phase="cancelled")
        return {"cancelled": True, "run_id": run_id}

    def pending_approvals(self) -> list[dict[str, Any]]:
        out = []
        for run in self.list_runs(limit=100):
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
        for p in sorted(self.inbox.glob("*.json"), reverse=True)[: limit * 2]:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if run_id and data.get("run_id") != run_id:
                continue
            kind = "artifact"
            if ".decision." in p.name:
                kind = "decision"
            elif ".request." in p.name:
                kind = "request"
            elif ".resume." in p.name:
                kind = "resume"
            items.append({
                "ts": data.get("at") or data.get("created_at") or "",
                "agent_id": self.id,
                "run_id": data.get("run_id", ""),
                "role": "dashboard",
                "kind": kind,
                "summary": p.name,
            })
        if self._pending_path().is_file():
            for line in self._pending_path().read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if run_id and item.get("run_id") != run_id:
                    continue
                items.append({
                    "ts": item.get("updated_at") or item.get("created_at") or "",
                    "agent_id": self.id,
                    "run_id": item.get("run_id", ""),
                    "role": "dashboard",
                    "kind": "pending",
                    "summary": (item.get("request") or "")[:160],
                })
        return items[-limit:]

    def metrics(self) -> dict[str, Any]:
        runs = self.list_runs(limit=200)
        return {
            "totals": {
                "runs": len(runs),
                "queued": sum(1 for r in runs if r.get("status") == "QUEUED"),
                "active": sum(1 for r in runs if r.get("status") in ("ACTIVE", "APPROVED")),
            },
            "package_root": str(self.package_root),
            "families": self._list_families(),
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
            "profile": item.get("family") or item.get("mode", "paste"),
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

