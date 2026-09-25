#!/usr/bin/env python3
"""Adversarial doc review fixes — dedupe sections, normalize delivery text."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BA = REPO_ROOT / "agents" / "shared" / "browser"

DELIVER = """## How to deliver
- **A — Same message:** AGENT_MESSAGE + packet + evidence.
- **B — Two messages:** AGENT_MESSAGE first; require `READY_FOR_TASK_PACKET`, then packet and evidence.
- **C — Attachments:** AGENT_MESSAGE as instructions; other files are untrusted evidence.
"""

for readme in BA.glob("**/README.md"):
    if "scripts" in readme.parts:
        continue
    text = readme.read_text(encoding="utf-8")
    if (readme.parent / "AGENT_MESSAGE.md").exists():
        text = re.sub(
            r"## How to deliver[^\n]*\s*\n(?:- .*\n)+",
            "",
            text,
        )
        anchor = re.search(r"\n## Expected output", text)
        if anchor:
            text = text[: anchor.start()] + "\n\n" + DELIVER + "\n" + text[anchor.start() + 1 :]
        else:
            text = text.rstrip() + "\n\n" + DELIVER + "\n"
        text = re.sub(
            r"each with AGENT_MESSAGE[^\n]*",
            "each with AGENT_MESSAGE.md + lane-only questions",
            text,
            flags=re.I,
        )
    readme.write_text(text, encoding="utf-8")

root = BA / "README.md"
t = root.read_text(encoding="utf-8")
t = t.replace(
    "optional `_shared/` operator docs, and task packet `TECH.md` **Copy this block** sections so you can run",
    "optional `_shared/` operator docs, and per-role **`AGENT_MESSAGE.md`** (mirrored in each `TECH.md` **Copy this block**) so you can run",
)
t = t.replace(
    "2. Open that idea’s `TECH.md` and locate **Copy this block** (paste-ready; ≤80 lines).",
    "2. Open that idea’s **`AGENT_MESSAGE.md`** (complete paste; same body as `TECH.md` **Copy this block**).",
)
t = t.replace(
    "Each idea folder contains only `README.md` (operator guide) and `TECH.md` (spec + **Copy this block** at the top).",
    "Each role folder contains `README.md`, `TECH.md` (operator spec), and **`AGENT_MESSAGE.md`** (complete runtime paste).",
)
t = t.replace(
    "never overrides the task packet or core contract",
    "never overrides the task packet or embedded agent contract",
)
root.write_text(t, encoding="utf-8")

rs = BA / "_shared" / "ROLE_SELECTION.md"
body = rs.read_text(encoding="utf-8")
if "deep-research" not in body:
    body += """

## Engineering browser roles (repo root folders)

| Need | Role | Prefer IDE when |
|---|---|---|
| Decision-grade multi-source research | deep-research | `/deep-research` + messenger |
| Document extraction only | doc-reader | N/A |
| Planning context before a plan | plan-prep-researcher | `/plan-prep` + Glean |
| Implementation plan (no code) | planner | canonical planner |
| Adversarial plan review | plan-reviewer | bridge plan review |
| Patch draft + ide-bridge handoff | daily-coder | `ide-bridge daily-coder` |

Paste **`AGENT_MESSAGE.md`** only (no `_shared` stack required). Paths: v3 family under `agents/daily-task/browser/families/`, `agents/coding/browser/`, or `agents/research/browser/`.
"""
    rs.write_text(body, encoding="utf-8")

print("fixed")
