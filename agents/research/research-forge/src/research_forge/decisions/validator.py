"""Decision registry validation for wave gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import jsonschema
import yaml

from research_forge.errors import ErrorCode, forge_error

GateTarget = Literal["wave_0", "wave_1_mock", "wave_1_live"]

BOUNDARY_ORDER = [
    "none",
    "wave_0_scaffold",
    "wave_1_mock",
    "wave_1_live",
    "wave_2_plus",
]

GATE_MIN_BOUNDARY: dict[GateTarget, str] = {
    "wave_0": "wave_0_scaffold",
    "wave_1_mock": "wave_1_mock",
    "wave_1_live": "wave_1_live",
}


def _boundary_index(name: str) -> int:
    return BOUNDARY_ORDER.index(name)


def load_registry(repo_root: Path) -> dict[str, Any]:
    reg_path = repo_root / "docs" / "decisions" / "open-decisions.yaml"
    schema_path = repo_root / "docs" / "decisions" / "decision-registry.schema.json"
    with reg_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=data, schema=schema)
    return data


def validate_decisions_for_gate(
    repo_root: Path,
    gate: GateTarget,
) -> tuple[bool, list[str]]:
    """Return (ok, messages). Wave 0 passes with accepted_unknown; live fails closed."""
    try:
        reg = load_registry(repo_root)
    except Exception as exc:  # noqa: BLE001 — surface as gate failure
        return False, [f"registry invalid: {exc}"]

    min_idx = _boundary_index(GATE_MIN_BOUNDARY[gate])
    failures: list[str] = []

    for dec in reg.get("decisions", []):
        if not dec.get("blocking"):
            continue
        boundary = dec["earliest_blocking_boundary"]
        if boundary == "none":
            continue
        if _boundary_index(boundary) > min_idx:
            continue
        status = dec["status"]
        dec_id = dec["id"]
        if status == "resolved":
            continue
        if status == "accepted_unknown" and gate == "wave_0":
            continue
        if status == "accepted_unknown" and gate == "wave_1_mock":
            continue
        failures.append(
            f"{dec_id} blocks {gate}: status={status}, boundary={boundary}, "
            f"question={dec['question'][:80]}"
        )

    if gate == "wave_1_live":
        for dec in reg.get("decisions", []):
            if dec["status"] in ("pending", "blocked"):
                failures.append(f"{dec['id']} unresolved for live: status={dec['status']}")
            if dec["status"] == "accepted_unknown" and dec["earliest_blocking_boundary"] in (
                "wave_1_live",
                "wave_1_mock",
            ):
                if _boundary_index(dec["earliest_blocking_boundary"]) <= _boundary_index(
                    "wave_1_live"
                ):
                    failures.append(
                        f"{dec['id']} accepted_unknown not permitted for wave_1_live"
                    )

    return len(failures) == 0, failures


def validate_decisions_or_error(repo_root: Path, gate: GateTarget):
    ok, msgs = validate_decisions_for_gate(repo_root, gate)
    if ok:
        return None
    return forge_error(
        ErrorCode.BLOCKED,
        f"Decision gate failed for {gate}",
        failures=msgs,
    )
