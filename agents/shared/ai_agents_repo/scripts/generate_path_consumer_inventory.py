#!/usr/bin/env python3
"""Generate baseline inventory of legacy path string consumers in the checkout."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Legacy path needles (forward-slash normalized in matching)
NEEDLES: list[tuple[str, str]] = [
    ("ide-pack/ide-agents", "ide_hub"),
    ("ide-agents/", "ide_hub_logical"),
    ("daily-coder-ecosystem", "daily_coder"),
    ("research-forge", "research_forge"),
    ("agent-dashboard", "gui"),
    ("agent-core", "agent_core"),
    ("browser agent", "browser_legacy"),
    ("browser%20agent", "browser_legacy_encoded"),
    ("schemas/personal", "schemas_personal"),
    ("IDE_PACK_ROOT", "python_constant"),
    ("_resolve_repo_root", "python_helper"),
]

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    "site-packages",
    "agents/shared/ai_agents_repo/tests/fixtures",
}

CLASSIFICATIONS = frozenset(
    {
        "migrated",
        "generated",
        "historical",
        "external",
        "false_positive",
        "pending_wire",
        "inventory_tool",
    }
)

WIRED_SUFFIXES = (
    "agents/ide/scripts/sync_ide_agents.py",
    "agents/ide/scripts/import_daily_coder_agents.py",
    "agents/ide/scripts/import_rf_agents.py",
    "agents/ide/scripts/audit_prompt_bytes.py",
    "agents/ide/scripts/_repo_layout.py",
    "agents/ide/bridge/ide_bridge/dc_runner.py",
)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".ai-agents-layout").is_file():
            return parent
        if (parent / "ide-pack" / "ide-agents" / "MANIFEST.yml").is_file():
            return parent
    raise SystemExit("Could not locate repository root")


def _git_ls_files(root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _should_skip(rel: str) -> bool:
    parts = Path(rel).parts
    for skip in SKIP_DIR_NAMES:
        if skip in parts:
            return True
    if rel.endswith("path_consumer_inventory.baseline.json"):
        return True
    if "generate_path_consumer_inventory.py" in rel:
        return True
    return False


def _classify(rel: str, needle: str, line: str) -> str:
    norm = rel.replace("\\", "/")
    if norm.endswith("generate_path_consumer_inventory.py"):
        return "inventory_tool"
    if any(norm.endswith(w) for w in WIRED_SUFFIXES):
        return "migrated"
    if norm.startswith((".cursor/agents/", ".github/agents/", ".claude/agents/")):
        return "generated"
    if norm.startswith("ide-pack/.cursor/"):
        return "generated"
    if "/reports/" in norm and norm.endswith(".json"):
        return "historical"
    if norm.startswith("docs/research/") or "VALIDATION_REPORT" in norm:
        return "historical"
    if "browser agent/scripts/build_self_contained" in norm and "Downloads" in line:
        return "external"
    if needle in ("browser%20agent",) and norm.startswith("docs/"):
        return "false_positive"
    if norm.startswith(("ai_agents_repo/", "agents/shared/ai_agents_repo/")):
        return "migrated"
    return "pending_wire"


def scan(root: Path) -> dict:
    files = _git_ls_files(root)
    if not files:
        files = [
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        ]

    hits: list[dict] = []
    for rel in files:
        if _should_skip(rel):
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            line_norm = line.replace("\\", "/")
            for needle, category in NEEDLES:
                if needle not in line_norm and needle not in line:
                    continue
                classification = _classify(rel, needle, line)
                hits.append(
                    {
                        "file": rel.replace("\\", "/"),
                        "line": line_no,
                        "needle": needle,
                        "category": category,
                        "classification": classification,
                        "excerpt": line.strip()[:240],
                    }
                )

    # de-dupe identical hits
    seen: set[tuple] = set()
    unique: list[dict] = []
    for hit in hits:
        key = (hit["file"], hit["line"], hit["needle"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "hit_count": len(unique),
        "hits": sorted(unique, key=lambda h: (h["file"], h["line"], h["needle"])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write JSON baseline (default: agents/shared/ai_agents_repo/data/path_consumer_inventory.baseline.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare to committed baseline without writing",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    report = scan(root)
    out = args.output or (
        root / "agents" / "shared" / "ai_agents_repo" / "data" / "path_consumer_inventory.baseline.json"
    )

    if args.check:
        if not out.is_file():
            print(f"Missing baseline: {out}", file=sys.stderr)
            return 1
        baseline = json.loads(out.read_text(encoding="utf-8"))
        if baseline.get("hits") != report["hits"]:
            print("Inventory drift: regenerate with generate_path_consumer_inventory.py", file=sys.stderr)
            return 1
        print("Inventory OK")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({report['hit_count']} hits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
