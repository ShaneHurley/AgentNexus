"""Deterministic writing lint. Fail-closed for COMPLETE writing_result."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EM_DASH = "\u2014"
EN_DASH = "\u2013"


def check_punctuation(text: str) -> list[str]:
    findings: list[str] = []
    if EM_DASH in text:
        findings.append("em dash (U+2014) present")
    if EN_DASH in text and "allowed_en_dash" not in text:
        # Flag en dashes used as em-dash substitutes in prose
        if re.search(r"\s" + EN_DASH + r"\s", text):
            findings.append("spaced en dash used like an em dash")
    return findings


def check_repetition(text: str, min_words: int = 5) -> list[str]:
    """Flag exact duplicate sentences (simple heuristic)."""
    findings: list[str] = []
    raw = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentences = [re.sub(r"\s+", " ", s).strip(" \t\"'") for s in raw]
    seen: set[str] = set()
    for s in sentences:
        key = s.lower()
        if len(key.split()) < min_words:
            continue
        if key in seen:
            findings.append(f"repeated sentence: {s[:80]}")
        seen.add(key)
    return findings


def check_terminology(text: str, banned: list[str] | None = None) -> list[str]:
    banned = banned or []
    findings: list[str] = []
    lower = text.lower()
    for term in banned:
        if term.lower() in lower:
            findings.append(f"banned terminology: {term}")
    return findings


def check_links(text: str) -> list[str]:
    findings: list[str] = []
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        url = match.group(2).strip()
        if not url or url == "#":
            findings.append(f"empty or placeholder link: {match.group(0)}")
    return findings


def check_structure(text: str, mode: str = "email") -> list[str]:
    findings: list[str] = []
    if mode == "email" and len(text.strip()) < 20:
        findings.append("email body too short")
    return findings


CHECKS = {
    "punctuation": lambda t, **_: check_punctuation(t),
    "repetition": lambda t, **_: check_repetition(t),
    "terminology": lambda t, banned=None, **_: check_terminology(t, banned),
    "links": lambda t, **_: check_links(t),
    "structure": lambda t, mode="email", **_: check_structure(t, mode),
}


def lint(check: str, text: str, **kwargs) -> list[str]:
    if check not in CHECKS:
        raise ValueError(f"unknown check: {check}")
    return CHECKS[check](text, **kwargs)


def may_complete(text: str) -> tuple[bool, list[str]]:
    """Return whether writing_result.status may be COMPLETE."""
    findings = check_punctuation(text) + check_repetition(text)
    return (len(findings) == 0, findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="writing-lint")
    parser.add_argument(
        "check",
        choices=["punctuation", "repetition", "terminology", "links", "structure", "all"],
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--mode", default="email")
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    text = args.artifact.read_text(encoding="utf-8")
    checks = list(CHECKS) if args.check == "all" else [args.check]
    all_findings: list[str] = []
    for name in checks:
        all_findings.extend(lint(name, text, mode=args.mode))
    if all_findings:
        for f in all_findings:
            print(f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
