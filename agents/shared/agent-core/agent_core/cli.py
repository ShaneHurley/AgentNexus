from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

from agent_core.registry import validate_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-core")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate-registry", help="Validate agent-core/registry.yaml")
    compiled = sub.add_parser("compile-registry", help="Compile a reviewed repository snapshot; does not activate it")
    compiled.add_argument("--repo", type=Path, required=True)
    compiled.add_argument("--output", type=Path, required=True)
    activate = sub.add_parser("activate-registry", help="Activate or roll back with an explicit current grant ceiling")
    activate.add_argument("snapshot_id")
    activate.add_argument("--store", type=Path, required=True)
    activate.add_argument("--ceiling", type=Path, required=True)
    activate.add_argument("--revoke", action="append", default=[])
    args = parser.parse_args(argv)
    if args.cmd in {"compile-registry", "activate-registry"}:
        from agent_core.registry_snapshot import compile_repository, SnapshotStore
        from agent_core.contracts import ContractDenied, Grant
        try:
            if args.cmd == "compile-registry":
                snapshot = compile_repository(args.repo)
                key = SnapshotStore(args.output).publish(snapshot)
                print(json.dumps({"snapshot_id":key,"warnings":snapshot.data["warnings"],"activated":False},indent=2))
            else:
                ceiling = {key:Grant.from_mapping(value) for key,value in json.loads(args.ceiling.read_text()).items()}
                SnapshotStore(args.store).activate(args.snapshot_id,ceiling=ceiling,revoked=args.revoke)
                print(json.dumps({"snapshot_id":args.snapshot_id,"activated":True}))
            return 0
        except (ContractDenied,ValueError,OSError) as exc:
            print(str(exc),file=sys.stderr)
            return 1
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
