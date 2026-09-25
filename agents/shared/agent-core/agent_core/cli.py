from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_core.registry import validate_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-core")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate-registry", help="Validate agent-core/registry.yaml")
    args = parser.parse_args(argv)
    if args.cmd == "validate-registry":
        root = Path(__file__).resolve().parents[1]
        errors = validate_registry(root / "registry.yaml")
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print("registry OK")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
