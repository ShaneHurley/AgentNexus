"""Secret Scanner Skill.

Provides regex-based detection and redaction of leaked API keys, tokens, and
private keys in code snippets, diffs, and prompts.
"""

from __future__ import annotations

import re
from typing import Any

# Pattern definitions for common sensitive tokens
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # OpenRouter API Key (sk-or-v1-...)
    ("openrouter_api_key", re.compile(r"\bsk-or-v1-[a-f0-9]{64}\b")),
    ("openrouter_api_key", re.compile(r"\bsk-or-[a-zA-Z0-9_-]{32,}\b")),
    # Anthropic API Key (sk-ant-...)
    ("anthropic_api_key", re.compile(r"\bsk-ant-[a-zA-Z0-9_\-]{20,}\b")),
    # OpenAI API Key (classic and project tokens)
    ("openai_api_key", re.compile(r"\bsk-proj-[a-zA-Z0-9_-]{48,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b")),
    # GitHub Personal Access Token / Fine-grained / OAuth
    ("github_pat", re.compile(r"\bghp_[a-zA-Z0-9]{36}\b")),
    ("github_fine_grained_pat", re.compile(r"\bgithub_pat_[a-zA-Z0-9_]{40,}\b")),
    ("github_oauth", re.compile(r"\bgho_[a-zA-Z0-9]{36}\b")),
    # AWS Access Key ID
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # AWS Secret Access Key in key-value context
    (
        "aws_secret_key",
        re.compile(r"(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?"),
    ),
    # Private Key Headers
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    # Slack Token
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")),
    # Generic API Key / Secret assignments
    (
        "generic_api_secret",
        re.compile(r"(?i)(?:api_key|apikey|secret_key|auth_token|client_secret)\s*[:=]\s*['\"]([a-zA-Z0-9_\-\.]{20,})['\"]"),
    ),
]


def redact_secret(val: str) -> str:
    """Safely redact secret string, leaving small prefix and suffix for recognition."""
    if len(val) <= 8:
        return "[REDACTED]"
    if len(val) <= 16:
        return f"{val[:3]}...{val[-3:]}"
    return f"{val[:6]}...{val[-4:]}"


def scan_for_secrets(text: str) -> list[dict[str, Any]]:
    """Scan text for API keys, tokens, and credentials.

    Args:
        text: Input string (e.g. source code, commit diff, config file).

    Returns:
        List of detected secrets:
            [{"type": str, "redacted": str, "line": int, "col": int, "snippet": str}]
    """
    if not text:
        return []

    results: list[dict[str, Any]] = []
    lines = text.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        line_matches: list[tuple[int, int, str, str, str]] = []
        line_spans: list[tuple[int, int]] = []

        for secret_type, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                # If pattern has a capturing group (like secret assignment), target group 1
                if match.groups() and match.group(1):
                    secret_val = match.group(1)
                    start_col = match.start(1)
                    end_col = match.end(1)
                else:
                    secret_val = match.group(0)
                    start_col = match.start()
                    end_col = match.end()

                # Check overlap
                if any(start_col < existing_end and end_col > existing_start for existing_start, existing_end in line_spans):
                    continue

                line_spans.append((start_col, end_col))
                redacted = redact_secret(secret_val)
                line_matches.append((start_col, end_col, secret_type, secret_val, redacted))

        if not line_matches:
            continue

        # Sort matches on this line by start position
        line_matches.sort(key=lambda m: m[0])

        # Build safe snippet with all secrets on this line redacted
        pieces: list[str] = []
        last_pos = 0
        for start_col, end_col, _, _, redacted in line_matches:
            pieces.append(line[last_pos:start_col])
            pieces.append(redacted)
            last_pos = end_col
        pieces.append(line[last_pos:])
        line_snippet = "".join(pieces).strip()

        for start_col, end_col, secret_type, secret_val, redacted in line_matches:
            results.append({
                "type": secret_type,
                "redacted": redacted,
                "line": line_idx,
                "col": start_col + 1,
                "snippet": line_snippet,
            })

    return results
