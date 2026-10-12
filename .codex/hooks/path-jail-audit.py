#!/usr/bin/env python3
"""beforeReadFile: deny secret/env/credential paths (Daily Coder path_policy spirit)."""

from __future__ import annotations

import sys

from _ide_pack_policy import (
    allow,
    append_audit,
    deny,
    file_path_from_payload,
    path_denied_by_globs,
    read_stdin_json,
    secret_deny_globs,
)

MSG = "Read denied: path matches IDE secret deny globs (aligned with Daily Coder policies.json)."


def main() -> int:
    payload = read_stdin_json()
    path = file_path_from_payload(payload)
    if not path:
        allow()
        return 0

    globs = secret_deny_globs()
    matched = path_denied_by_globs(path, globs)
    if matched:
        append_audit(
            {
                "event": "beforeReadFile",
                "decision": "deny",
                "path": path,
                "matched_glob": matched,
            }
        )
        deny(MSG, f"Matched pattern {matched} for {path}")
        return 0

    allow()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        deny(f"path-jail-audit hook error: {exc}", MSG)
        raise SystemExit(2) from exc
