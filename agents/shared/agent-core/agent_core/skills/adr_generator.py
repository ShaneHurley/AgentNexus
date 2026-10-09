"""Architecture Decision Record (ADR) Generator Skill.

Provides structured formatting, parsing, and management of Architecture Decision
Records following the Michael Nygard / MADR standard.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any


def format_adr(
    title: str,
    status: str,
    context: str,
    decision: str,
    consequences: str,
    adr_id: int | str | None = None,
    date: str | None = None,
    alternatives: list[str] | None = None,
) -> str:
    """Format an Architecture Decision Record (ADR) into Markdown.

    Args:
        title: Short title of the decision.
        status: Current status (e.g. Proposed, Accepted, Rejected, Deprecated, Superseded).
        context: The context, forces, and problem statement driving this decision.
        decision: The chosen architecture or design decision.
        consequences: The resulting consequences, trade-offs, and downstream impacts.
        adr_id: Optional ID number or string (e.g. 1 or '0001').
        date: Optional ISO date string (YYYY-MM-DD). Defaults to today.
        alternatives: Optional list of alternative solutions considered.

    Returns:
        Formatted Markdown ADR string.
    """
    id_prefix = f"ADR-{adr_id}: " if adr_id is not None else ""
    date_str = date or datetime.date.today().isoformat()

    lines = [
        f"# {id_prefix}{title.strip()}",
        "",
        "## Status",
        f"{status.strip()}",
        "",
        "## Date",
        f"{date_str}",
        "",
        "## Context",
        f"{context.strip()}",
        "",
        "## Decision",
        f"{decision.strip()}",
        "",
        "## Consequences",
        f"{consequences.strip()}",
    ]

    if alternatives:
        lines.extend([
            "",
            "## Alternatives Considered",
        ])
        for alt in alternatives:
            lines.append(f"- {alt.strip()}")

    lines.append("")
    return "\n".join(lines)


def parse_adr(markdown_text: str) -> dict[str, Any]:
    """Parse a Markdown ADR document into structured fields.

    Args:
        markdown_text: Raw Markdown content of an ADR.

    Returns:
        dict with keys: title, adr_id, status, date, context, decision, consequences, alternatives.
    """
    res: dict[str, Any] = {
        "title": "",
        "adr_id": None,
        "status": "",
        "date": "",
        "context": "",
        "decision": "",
        "consequences": "",
        "alternatives": [],
    }

    if not markdown_text:
        return res

    sections: dict[str, list[str]] = {}
    current_section = "_title"
    sections[current_section] = []

    in_code_block = False
    for line in markdown_text.splitlines():
        if line.startswith("```"):
            in_code_block = not in_code_block
            if current_section in sections:
                sections[current_section].append(line)
            continue

        if not in_code_block and line.startswith("# "):
            title_line = line[2:].strip()
            # Match optional ADR-###:
            m = re.match(r"^ADR-([0-9a-zA-Z]+):\s*(.*)$", title_line)
            if m:
                res["adr_id"] = m.group(1)
                res["title"] = m.group(2).strip()
            else:
                res["title"] = title_line
        elif not in_code_block and line.startswith("## "):
            sec_name = line[3:].strip().lower()
            matched_key = None
            for candidate in ("status", "date", "context", "decision", "consequence", "alternative"):
                if candidate in sec_name:
                    matched_key = candidate
                    break
            if matched_key:
                current_section = matched_key
                sections[current_section] = []
            else:
                if current_section in sections:
                    sections[current_section].append(line)
        else:
            if current_section in sections:
                sections[current_section].append(line)

    for sec, lines in sections.items():
        text_val = "\n".join(lines).strip()
        if "status" in sec:
            res["status"] = text_val
        elif "date" in sec:
            res["date"] = text_val
        elif "context" in sec:
            res["context"] = text_val
        elif "decision" in sec:
            res["decision"] = text_val
        elif "consequence" in sec:
            res["consequences"] = text_val
        elif "alternative" in sec:
            alts = []
            for l in lines:
                l_clean = l.strip()
                if l_clean.startswith(("-", "*")):
                    alts.append(l_clean.lstrip("-* ").strip())
            res["alternatives"] = alts

    return res


def save_adr(
    directory: Path | str,
    title: str,
    status: str,
    context: str,
    decision: str,
    consequences: str,
    adr_id: int | str | None = None,
    alternatives: list[str] | None = None,
) -> Path:
    """Save an ADR to a markdown file in the specified directory.

    If adr_id is omitted, auto-detects the next number based on existing ADR files.

    Args:
        directory: Directory where ADR markdown files are stored.
        title: Title of ADR.
        status: Status.
        context: Context.
        decision: Decision.
        consequences: Consequences.
        adr_id: Optional explicit integer or string ID.
        alternatives: Optional alternatives list.

    Returns:
        Path to the saved ADR file.
    """
    dir_path = Path(directory)
    dir_path.mkdir(parents=True, exist_ok=True)

    if adr_id is None:
        existing = list(dir_path.glob("*.md"))
        highest = 0
        for f in existing:
            m = re.match(r"^(\d+)-", f.name)
            if m:
                highest = max(highest, int(m.group(1)))
        adr_int = highest + 1
    else:
        adr_int = int(str(adr_id).lstrip("0") or "0")

    formatted_id = f"{adr_int:04d}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    filename = f"{formatted_id}-{slug}.md"
    file_path = dir_path / filename

    content = format_adr(
        title=title,
        status=status,
        context=context,
        decision=decision,
        consequences=consequences,
        adr_id=formatted_id,
        alternatives=alternatives,
    )

    file_path.write_text(content, encoding="utf-8")
    return file_path
