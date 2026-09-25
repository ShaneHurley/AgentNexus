#!/usr/bin/env python3
"""CLI router for Browser RCC v3 families (F2b)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow checkout-only invocation before editable install
_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "agents" / "shared" / "ai_agents_repo" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ai_agents_repo.browser.router import AUTHORITY_BANNER, V3_FAMILY_IDS, route  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route browser_family (+ variant) to AGENT_MESSAGE.md")
    parser.add_argument("family", nargs="?", help="browser_family slug")
    parser.add_argument("variant", nargs="?", help="browser_variant slug (optional)")
    parser.add_argument("--list", action="store_true", help="List all ten family ids")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable route")
    args = parser.parse_args(argv)

    if args.list:
        for fam in sorted(V3_FAMILY_IDS):
            print(fam)
        return 0

    if not args.family:
        print(AUTHORITY_BANNER, file=sys.stderr)
        parser.print_help()
        return 2

    try:
        result = route(args.family, args.variant or None)
    except (KeyError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "authority_banner": result.authority_banner,
            "family": result.family,
            "variant": result.variant,
            "logical_slug": result.logical_slug,
            "domain": result.domain,
            "agent_message": str(result.agent_message),
            "family_root": str(result.family_root),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(result.authority_banner)
    print()
    print(f"family: {result.logical_slug}")
    print(f"domain: {result.domain}")
    print(f"paste: {result.agent_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
