"""Phase validation gates (F0 grows with inventory, wiring, #file: checks)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_agents_repo import (
    dc_root,
    ide_pack_root,
    layout,
    repo_root,
    resolve_ref,
)
from ai_agents_repo.discovery import read_marker
from ai_agents_repo.exceptions import LayoutError, RefResolutionError


def _package_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def _baseline_inventory_path() -> Path:
    return _package_dir() / "data" / "path_consumer_inventory.baseline.json"


def _check_f0a() -> list[str]:
    errors: list[str] = []
    root = repo_root()
    marker = root / ".ai-agents-layout"
    if not marker.is_file():
        errors.append("Missing repo marker .ai-agents-layout")
    else:
        try:
            read_marker(root)
        except LayoutError as exc:
            errors.append(str(exc))

    try:
        lay = layout(root=root)
    except LayoutError as exc:
        errors.append(f"layout(): {exc}")
        return errors

    if not ide_pack_root(root=root).is_dir():
        errors.append(f"{lay} ide_pack_root missing")
    if not dc_root(root=root).is_dir():
        errors.append(f"{lay} dc_root missing")
    return errors


def _check_f0b() -> list[str]:
    errors: list[str] = []
    baseline = _baseline_inventory_path()
    if not baseline.is_file():
        errors.append(f"Missing inventory baseline: {baseline}")
        return errors
    try:
        data = json.loads(baseline.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid inventory JSON: {exc}")
        return errors
    if data.get("schema_version") != 1:
        errors.append("inventory schema_version must be 1")
    unclassified = [
        h for h in data.get("hits", []) if h.get("classification") in (None, "", "unclassified")
    ]
    if unclassified:
        errors.append(f"{len(unclassified)} unclassified inventory hits")
    return errors


def _check_f0c() -> list[str]:
    errors: list[str] = []
    root = repo_root()
    hub = ide_pack_root(root=root)
    wired = [
        hub / "bridge" / "ide_bridge" / "dc_runner.py",
        hub / "scripts" / "sync_ide_agents.py",
        hub / "scripts" / "import_daily_coder_agents.py",
        hub / "scripts" / "import_rf_agents.py",
        hub / "scripts" / "audit_prompt_bytes.py",
    ]
    needles = ("ai_agents_repo", "_repo_layout")
    for path in wired:
        if not path.is_file():
            errors.append(f"Expected wired consumer missing: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if not any(n in text for n in needles):
            errors.append(f"{path.relative_to(root)} not wired to ai_agents_repo")
    return errors


def _check_f0d() -> list[str]:
    errors: list[str] = []
    root = repo_root()
    adr = root / "docs" / "decisions" / "ADR-REPO-LAYOUT-2026-09.md"
    checklist = root / "docs" / "ide-agents" / "file-ref-verification-checklist.md"
    if not adr.is_file():
        errors.append("Missing ADR-REPO-LAYOUT-2026-09.md")
    if not checklist.is_file():
        errors.append("Missing file-ref-verification-checklist.md")
    try:
        sample = "ide-agents/contracts/deep-research-phase-index.md"
        path = resolve_ref(sample, root=root, must_exist=True)
        if not path.is_file():
            errors.append(f"resolve_ref sample missing: {sample}")
    except RefResolutionError as exc:
        errors.append(f"resolve_ref smoke test failed: {exc}")
    return errors


def _check_keep_six() -> list[str]:
    errors: list[str] = []
    manifest = ide_pack_root() / "MANIFEST.yml"
    if not manifest.is_file():
        errors.append("MANIFEST.yml not found for KEEP-6")
        return errors
    try:
        import yaml
    except ImportError:
        errors.append("pyyaml required for KEEP-6 validation")
        return errors
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    agents = data.get("agents") or []
    uf = sorted(a["name"] for a in agents if a.get("user_invocable"))
    expected = sorted(
        [
            "deep-research",
            "plan-prep",
            "research-messenger",
            "use-master",
            "daily-coder",
            "researcher",
        ]
    )
    if uf != expected:
        errors.append(f"KEEP-6 mismatch: got {uf}, expected {expected}")
    return errors


_PHASE_CHECKS = {
    "F0": [_check_f0a, _check_f0b, _check_f0c, _check_f0d, _check_keep_six],
    "F0a": [_check_f0a],
    "F0b": [_check_f0b],
    "F0c": [_check_f0c],
    "F0d": [_check_f0d],
}


def run_phase(phase: str) -> tuple[int, list[str]]:
    phase = phase.upper()
    if phase not in _PHASE_CHECKS:
        return 2, [f"Unknown phase {phase!r}; supported: {', '.join(_PHASE_CHECKS)}"]

    errors: list[str] = []
    for check in _PHASE_CHECKS[phase]:
        errors.extend(check())
    return (0 if not errors else 1), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ai_agents_repo migration phases.")
    parser.add_argument(
        "--phase",
        default="F0",
        help="Phase gate (F0, F0a, F0b, F0c, F0d)",
    )
    args = parser.parse_args(argv)
    code, errors = run_phase(args.phase)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
    else:
        print(f"OK: phase {args.phase.upper()}")
    return code
