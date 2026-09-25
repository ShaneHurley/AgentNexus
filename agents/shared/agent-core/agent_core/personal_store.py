"""Deterministic personal career store helper (no drafting / reasoning)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


def default_store_root() -> Path:
    override = os.environ.get("PERSONAL_CAREER_ROOT")
    if override:
        return Path(override)
    home = Path.home()
    # Windows-friendly default; also works on Unix
    return home / ".config" / "personal-career"


def ensure_layout(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "opportunities").mkdir(exist_ok=True)
    (root / "applications").mkdir(exist_ok=True)
    (root / "interviews").mkdir(exist_ok=True)
    profile = root / "profile.yaml"
    if not profile.exists():
        profile.write_text(
            "version: '0.1.0'\nidentity: {}\nskills: []\neducation: []\nexperience_ids: []\n",
            encoding="utf-8",
        )
    for name in ("accomplishments.jsonl", "projects.jsonl", "events.jsonl"):
        path = root / name
        if not path.exists():
            path.write_text("", encoding="utf-8")


def _load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dump_yaml(path: Path, data: Any) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML required")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"not a file: {path}"]
    if path.suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
    elif path.suffix == ".jsonl":
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {i}: {exc}")
    elif path.suffix in {".yaml", ".yml"}:
        try:
            _load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    else:
        errors.append(f"unsupported type: {path.suffix}")
    return errors


def append_accomplishment(root: Path, draft_path: Path, confirm: bool) -> int:
    ensure_layout(root)
    errors = validate_file(draft_path)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    record = json.loads(draft_path.read_text(encoding="utf-8"))
    required = ["id", "context", "action", "result_status", "confidentiality"]
    missing = [k for k in required if k not in record]
    if missing:
        print(f"missing fields: {missing}", file=sys.stderr)
        return 1
    print("--- proposed accomplishment ---")
    print(json.dumps(record, indent=2))
    if not confirm:
        print("dry-run only; pass --confirm to append")
        return 0
    out = root / "accomplishments.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    _append_event(root, {"type": "accomplishment.append", "id": record["id"]})
    print(f"appended to {out}")
    return 0


def profile_show(root: Path) -> int:
    ensure_layout(root)
    print((root / "profile.yaml").read_text(encoding="utf-8"))
    return 0


def profile_apply(root: Path, diff_path: Path, confirm: bool) -> int:
    ensure_layout(root)
    proposed = _load_yaml(diff_path)
    current = _load_yaml(root / "profile.yaml")
    print("--- current ---")
    print(yaml.safe_dump(current, sort_keys=False) if yaml else current)
    print("--- proposed ---")
    print(yaml.safe_dump(proposed, sort_keys=False) if yaml else proposed)
    if not confirm:
        print("dry-run only; pass --confirm to apply")
        return 0
    _dump_yaml(root / "profile.yaml", proposed)
    _append_event(root, {"type": "profile.apply", "at": _now()})
    print("profile updated")
    return 0


def export_store(root: Path, dest: Path) -> int:
    ensure_layout(root)
    if dest.exists():
        print(f"refusing to overwrite: {dest}", file=sys.stderr)
        return 1
    shutil.copytree(root, dest)
    print(f"exported to {dest}")
    return 0


def delete_store(root: Path, confirm: bool) -> int:
    if not root.exists():
        print("store does not exist")
        return 0
    print(f"would delete: {root}")
    if not confirm:
        print("dry-run only; pass --confirm to delete")
        return 0
    shutil.rmtree(root)
    print("deleted")
    return 0


def _append_event(root: Path, event: dict[str, Any]) -> None:
    event = {**event, "at": _now()}
    with (root / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="personal-store")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Store root (default: PERSONAL_CAREER_ROOT or ~/.config/personal-career)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate a YAML/JSON/JSONL file")
    p_val.add_argument("file", type=Path)

    p_app = sub.add_parser("accomplishment", help="Accomplishment operations")
    app_sub = p_app.add_subparsers(dest="acc_cmd", required=True)
    p_append = app_sub.add_parser("append")
    p_append.add_argument("draft", type=Path)
    p_append.add_argument("--confirm", action="store_true")

    p_prof = sub.add_parser("profile")
    prof_sub = p_prof.add_subparsers(dest="prof_cmd", required=True)
    prof_sub.add_parser("show")
    p_apply = prof_sub.add_parser("apply")
    p_apply.add_argument("diff", type=Path)
    p_apply.add_argument("--confirm", action="store_true")

    p_art = sub.add_parser("artifact")
    art_sub = p_art.add_subparsers(dest="art_cmd", required=True)
    p_der = art_sub.add_parser("derive")
    p_der.add_argument("--from", dest="from_ids", required=True)
    p_stale = art_sub.add_parser("stale")
    p_stale.add_argument("--source", required=True)

    p_exp = sub.add_parser("export")
    p_exp.add_argument("dest", type=Path)

    p_del = sub.add_parser("delete")
    p_del.add_argument("--confirm", action="store_true")

    args = parser.parse_args(argv)
    root = args.root or default_store_root()

    if args.cmd == "validate":
        errs = validate_file(args.file)
        if errs:
            for e in errs:
                print(e, file=sys.stderr)
            return 1
        print("OK")
        return 0
    if args.cmd == "accomplishment" and args.acc_cmd == "append":
        return append_accomplishment(root, args.draft, args.confirm)
    if args.cmd == "profile" and args.prof_cmd == "show":
        return profile_show(root)
    if args.cmd == "profile" and args.prof_cmd == "apply":
        return profile_apply(root, args.diff, args.confirm)
    if args.cmd == "artifact":
        print(f"recorded intent: {args.art_cmd} (lineage helper stub)")
        ensure_layout(root)
        _append_event(root, {"type": f"artifact.{args.art_cmd}", "args": vars(args)})
        return 0
    if args.cmd == "export":
        return export_store(root, args.dest)
    if args.cmd == "delete":
        return delete_store(root, args.confirm)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
