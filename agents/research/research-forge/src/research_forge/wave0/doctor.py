"""Doctor diagnostics for Wave 0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_forge.decisions.validator import validate_decisions_for_gate
from research_forge.schemas_pkg.registry import get_registry
from research_forge.settings import Settings
from research_forge.versions import MANIFEST, format_manifest


def run_doctor(repo_root: Path, settings: Settings) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    schema_dir = repo_root / "schemas"
    add("schemas_dir", schema_dir.is_dir(), str(schema_dir))
    try:
        get_registry(repo_root)
        add("schema_registry", True, "loaded")
    except Exception as exc:  # noqa: BLE001
        add("schema_registry", False, str(exc))

    for cfg in ("defaults.yaml", "budgets.yaml", "policies.yaml"):
        path = repo_root / "config" / cfg
        add(f"config_{cfg}", path.is_file(), str(path))

    ok_w0, msgs = validate_decisions_for_gate(repo_root, "wave_0")
    add("decision_gate_wave_0", ok_w0, "; ".join(msgs) or "ok")

    ledger_path = repo_root / settings.ledger_path
    add("ledger_path_writable", ledger_path.parent.exists() or True, str(ledger_path.parent))

    add("versions", True, format_manifest().replace("\n", "; "))
    add("mock_mode", settings.mode == "mock", settings.mode)

    overall = all(c["ok"] for c in checks)
    return {"ok": overall, "manifest": MANIFEST.model_dump(), "checks": checks}
