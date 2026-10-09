from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = (
    "id",
    "version",
    "kind",
    "primary_outcome",
    "lifecycle",
)


def load_registry(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "roles" not in data:
        raise ValueError("registry must be a mapping with 'roles'")
    return data


def validate_registry(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing registry: {path}"]
    try:
        data = load_registry(path)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    seen = set()
    for i, role in enumerate(data.get("roles", [])):
        if not isinstance(role, dict):
            errors.append(f"roles[{i}] must be a mapping")
            continue
        for field in REQUIRED_FIELDS:
            if field not in role:
                errors.append(f"roles[{i}] missing {field}")
        if role.get("id") in seen: errors.append(f"duplicate role ID: {role.get('id')}")
        seen.add(role.get("id"))
        ref = role.get("contract")
        if ref and not ref.startswith("services/"):
            target = (path.parent / ref).resolve()
            if not target.is_relative_to(path.parent.resolve()) or not target.is_file(): errors.append(f"unresolved contract: {ref}")
        lifecycle = role.get("lifecycle")
        if lifecycle not in {None, "experimental", "active", "deprecated", "retired"}:
            errors.append(f"roles[{i}] invalid lifecycle: {lifecycle}")
    return errors
