#!/usr/bin/env python3
"""Estimate resident prompt bytes for IDE agent files (body + eager `#file:` targets).

`load-on-invoke:` SSOT pointers are deferred until agent invocation and are
reported separately (not included in `total_bytes`).

Usage (from repository root):
  python agents/ide/scripts/audit_prompt_bytes.py
  python agents/ide/scripts/audit_prompt_bytes.py --output reports/prompt-bytes.json
  python agents/ide/scripts/audit_prompt_bytes.py --roots canonical,.cursor/agents
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from _repo_layout import REPO_ROOT, ide_pack_root, resolve_file_ref  # type: ignore[import-not-found]

IDE_PACK_ROOT = ide_pack_root()

FILE_REF_RE = re.compile(r"#file:([^\s`)\]]+)")
LOAD_ON_INVOKE_RE = re.compile(r"load-on-invoke:([^\s`)\]]+)")


def file_utf8_bytes(path: Path) -> int:
    return len(path.read_bytes())


@dataclass
class FileRefReport:
    ref: str
    resolved: str | None
    bytes: int
    missing: bool = False


@dataclass
class AgentReport:
    agent: str
    path: str
    body_bytes: int
    file_refs: list[FileRefReport] = field(default_factory=list)
    load_on_invoke_refs: list[FileRefReport] = field(default_factory=list)
    total_bytes: int = 0
    deferred_invoke_bytes: int = 0

    def finalize(self) -> None:
        ref_bytes = sum(r.bytes for r in self.file_refs)
        self.deferred_invoke_bytes = sum(r.bytes for r in self.load_on_invoke_refs)
        self.total_bytes = self.body_bytes + ref_bytes


def audit_agent(path: Path) -> AgentReport:
    text = path.read_text(encoding="utf-8")
    report = AgentReport(
        agent=path.stem,
        path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        body_bytes=len(text.encode("utf-8")),
    )
    for ref in FILE_REF_RE.findall(text):
        resolved = resolve_file_ref(ref)
        if resolved is None:
            report.file_refs.append(FileRefReport(ref=ref, resolved=None, bytes=0, missing=True))
            continue
        report.file_refs.append(
            FileRefReport(
                ref=ref,
                resolved=str(resolved.relative_to(REPO_ROOT)).replace("\\", "/"),
                bytes=file_utf8_bytes(resolved),
            )
        )
    for ref in LOAD_ON_INVOKE_RE.findall(text):
        resolved = resolve_file_ref(ref)
        if resolved is None:
            report.load_on_invoke_refs.append(
                FileRefReport(ref=ref, resolved=None, bytes=0, missing=True)
            )
            continue
        report.load_on_invoke_refs.append(
            FileRefReport(
                ref=ref,
                resolved=str(resolved.relative_to(REPO_ROOT)).replace("\\", "/"),
                bytes=file_utf8_bytes(resolved),
            )
        )
    report.finalize()
    return report


def discover_agents(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.md") if p.name.lower() != "readme.md")


def build_report(roots: list[Path]) -> dict:
    agents: list[AgentReport] = []
    for root in roots:
        for path in discover_agents(root):
            agents.append(audit_agent(path))
    agents.sort(key=lambda a: a.total_bytes, reverse=True)
    missing = [
        asdict(r)
        for a in agents
        for r in (*a.file_refs, *a.load_on_invoke_refs)
        if r.missing
    ]
    totals = [a.total_bytes for a in agents]
    deferred = [a.deferred_invoke_bytes for a in agents]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "agent_count": len(agents),
        "total_bytes_all_agents": sum(totals),
        "median_bytes": sorted(totals)[len(totals) // 2] if totals else 0,
        "p90_bytes": sorted(totals)[int(len(totals) * 0.9)] if totals else 0,
        "median_deferred_invoke_bytes": sorted(deferred)[len(deferred) // 2] if deferred else 0,
        "missing_file_refs": missing,
        "agents": [asdict(a) for a in agents],
    }


def default_roots() -> list[Path]:
    return [
        IDE_PACK_ROOT / "canonical",
        REPO_ROOT / ".cursor" / "agents",
    ]


def parse_roots(raw: str) -> list[Path]:
    out: list[Path] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        p = Path(part)
        if not p.is_absolute():
            p = REPO_ROOT / p
        out.append(p.resolve())
    return out or default_roots()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit IDE agent prompt byte footprint.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write JSON report to this path (default: agents/ide/reports/prompt-bytes.json)",
    )
    parser.add_argument(
        "--roots",
        default="",
        help="Comma-separated agent roots (default: agents/ide/canonical and .cursor/agents)",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit 1 when any #file: reference cannot be resolved",
    )
    args = parser.parse_args(argv)

    roots = parse_roots(args.roots) if args.roots else default_roots()
    report = build_report(roots)

    out_path = args.output
    if out_path is None:
        out_path = IDE_PACK_ROOT / "reports" / "prompt-bytes.json"
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(str(out_path))
    if args.fail_on_missing and report["missing_file_refs"]:
        print(f"Missing {len(report['missing_file_refs'])} #file: target(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
