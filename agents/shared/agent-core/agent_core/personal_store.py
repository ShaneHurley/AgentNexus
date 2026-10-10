"""Deterministic personal career store helper (no drafting / reasoning)."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import functools
import time
from contextlib import contextmanager
import tempfile
import uuid

import jsonschema
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


def _safe(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    # macOS exposes temporary directories through the system /var alias.
    if sys.platform == "darwin" and str(path).startswith("/var/"):
        path = Path("/private") / path.relative_to("/")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink paths are not supported")
    return path


@contextmanager
def _mutation_lock(root: Path):
    """Bounded advisory lock shared by processes; previews never call this."""
    root = _safe(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _safe(root.parent / f".{root.name}.personal-store.lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + 2
        if os.name == "nt":
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            def acquire():
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            def release():
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        while True:
            try:
                acquire()
                acquired = True
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise ValueError("personal store writer busy") from None
                time.sleep(0.01)
        yield
    finally:
        if acquired:
            release()
        os.close(descriptor)
    # Keep the lock inode: unlinking it lets concurrent writers lock different files.


def _serialized(function):
    signature = inspect.signature(function)
    @functools.wraps(function)
    def guarded(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        confirmed = bound.arguments.get("confirm", bound.arguments.get("confirmed", False))
        if confirmed is not True:
            return function(*args, **kwargs)
        try:
            with _mutation_lock(bound.arguments["root"]):
                return function(*args, **kwargs)
        except (ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return guarded


def _validate(data: Any, schema: str) -> None:
    base = Path(__file__).resolve().parents[2] / "schemas" / "personal"
    jsonschema.Draft202012Validator(json.loads((base / f"{schema}.schema.json").read_text())).validate(data)


def _atomic(path: Path, text: str) -> None:
    path = _safe(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as fh:
        temp = Path(fh.name)
        try:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def _validate_store(root: Path) -> None:
    _safe(root)
    if not root.is_dir():
        raise ValueError("store does not exist")
    for path in root.rglob("*"):
        _safe(path)
    _validate(_load_yaml(root / "profile.yaml"), "career-profile")
    _accomplishments(root)


def _accomplishments(root: Path) -> dict[str, dict]:
    result = {}
    path = _safe(root / "accomplishments.jsonl")
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            _validate(record, "accomplishment")
            if record["id"] in result:
                raise ValueError("duplicate accomplishment ID")
            result[record["id"]] = record
    return result


def _fingerprint(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ensure_layout(root: Path) -> None:
    root = _safe(root)
    if root.exists():
        for path in root.rglob("*"):
            _safe(path)
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


@_serialized
def append_accomplishment(root: Path, draft_path: Path, confirm: bool) -> int:
    try:
        _safe(root)
        record = json.loads(_safe(draft_path).read_text())
        _validate(record, "accomplishment")
        if root.exists():
            _validate_store(root)
        current = _accomplishments(root)
        if record["id"] in current:
            raise ValueError("duplicate accomplishment ID")
        print("--- proposed accomplishment ---")
        print(json.dumps(record, indent=2))
        if not confirm:
            print("dry-run only; pass --confirm to append")
            return 0
        ensure_layout(root)
        out = _safe(root / "accomplishments.jsonl")
        _atomic(out, out.read_text() + json.dumps(record, ensure_ascii=False) + "\n")
        _append_event(root, {"type": "accomplishment.append", "id": record["id"]})
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def profile_show(root: Path) -> int:
    try:
        _validate_store(root)
        print((root / "profile.yaml").read_text())
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


@_serialized
def profile_apply(root: Path, diff_path: Path, confirm: bool) -> int:
    try:
        _safe(root)
        proposed = _load_yaml(_safe(diff_path))
        _validate(proposed, "career-profile")
        current = {}
        if root.exists():
            _validate_store(root)
            current = _load_yaml(root / "profile.yaml")
        print("--- current ---")
        print(yaml.safe_dump(current, sort_keys=False))
        print("--- proposed ---")
        print(yaml.safe_dump(proposed, sort_keys=False))
        if not confirm:
            print("dry-run only; pass --confirm to apply")
            return 0
        ensure_layout(root)
        _atomic(root / "profile.yaml", yaml.safe_dump(proposed, sort_keys=False))
        _append_event(root, {"type": "profile.apply"})
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


@_serialized
def export_store(root: Path, dest: Path, *, confirmed: bool = True) -> int:
    try:
        _validate_store(root)
        dest = _safe(dest)
        if dest.exists():
            raise ValueError("refusing to overwrite destination")
        print(f"would export: {root} -> {dest}")
        if not confirmed:
            return 0
        shutil.copytree(root, dest)
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


@_serialized
def delete_store(root: Path, confirm: bool) -> int:
    try:
        root = _safe(root)
        if not root.exists():
            return 0
        _validate_store(root)
        print(f"would delete: {root}")
        if confirm:
            shutil.rmtree(root)
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


@_serialized
def artifact_derive(root: Path, source_ids: list[str], artifact_id: str, confirm: bool) -> int:
    try:
        _validate_store(root)
        records = _accomplishments(root)
        if not artifact_id or not source_ids or len(set(source_ids)) != len(source_ids) or any(x not in records for x in source_ids):
            raise ValueError("explicit existing source IDs and artifact ID required")
        path = _safe(root / "artifacts.jsonl")
        artifacts = [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
        if any(x["id"] == artifact_id for x in artifacts):
            raise ValueError("artifact ID already exists")
        artifact = {"id": artifact_id, "source_ids": source_ids,
                    "source_fingerprints": {x: _fingerprint(records[x]) for x in source_ids},
                    "stale": False, "derived_at": _now()}
        print("--- proposed artifact lineage ---")
        print(json.dumps(artifact, indent=2))
        if confirm:
            _atomic(path, "".join(json.dumps(x) + "\n" for x in [*artifacts, artifact]))
            _append_event(root, {"type": "artifact.derive", "id": artifact_id})
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


@_serialized
def artifact_stale(root: Path, source_id: str, confirm: bool = False) -> int:
    try:
        _validate_store(root)
        records = _accomplishments(root)
        path = _safe(root / "artifacts.jsonl")
        if not path.exists():
            print("[]")
            return 0
        artifacts = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        changed = []
        for artifact in artifacts:
            if source_id in artifact["source_ids"] and (source_id not in records or artifact["source_fingerprints"][source_id] != _fingerprint(records[source_id])):
                changed.append(artifact["id"])
                if confirm:
                    artifact["stale"] = True
        print(json.dumps({"stale_artifact_ids": changed, "confirmed": confirm}))
        if confirm and changed:
            _atomic(path, "".join(json.dumps(x) + "\n" for x in artifacts))
            _append_event(root, {"type": "artifact.stale", "ids": changed})
        return 0
    except (ValueError, OSError, jsonschema.ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def import_personal_files(root: Path, store, access, selected_files: list[str], *, namespace="default", confirmed=False) -> dict:
    """Import explicitly selected authoritative files as reversible drafts.

    Originals are retained. Returned record IDs may be deleted through the
    confirmed memory deletion API without changing the personal files.
    """
    from .memory_portability import _class
    _validate_store(root)
    root = _safe(root)
    if not isinstance(selected_files, list) or not selected_files or len(set(selected_files)) != len(selected_files):
        raise ValueError("explicit unique file selection required")
    if any(name not in {"profile.yaml", "accomplishments.jsonl"} for name in selected_files):
        raise ValueError("only schema-validated profile/accomplishment files may be selected")
    store._authorize(access, namespace, write=True)
    payloads = []
    for name in selected_files:
        path = _safe(root / name)
        access.effective_grant.authorize("tools", "memory.import", path)
        text = path.read_text()
        fingerprint = hashlib.sha256(text.encode()).hexdigest()
        if name == "profile.yaml":
            records = [("profile", _load_yaml(path))]
        else:
            records = list(_accomplishments(root).items())
        for source_id, value in records:
            sensitivity = "restricted" if value.get("confidentiality") == "employer_confidential" else "private"
            _class(access, sensitivity)
            payloads.append({"namespace": namespace, "kind": "note", "title": f"Personal {source_id}",
                "body": json.dumps(value, sort_keys=True, ensure_ascii=False), "sensitivity": sensitivity,
                "record_id": str(uuid.uuid5(uuid.UUID(store.store_id), str(path) + ":" + source_id + ":" + fingerprint)),
                "sources": [{"locator": path.as_uri(), "retrieved_at": path.stat().st_mtime,
                             "content_hash": fingerprint, "retrieval_status": "provided", "synthetic": False}],
                "dependencies": {path.as_uri(): fingerprint}})
    print(json.dumps({"selected_files": selected_files, "proposed_drafts": len(payloads), "originals_retained": True}))
    if not confirmed:
        return {"imported": 0, "record_ids": [], "originals_retained": True}
    if confirmed is not True:
        raise ValueError("explicit confirmation required")
    with store.connect(write=True) as db:
        records = [store._insert_draft(db, access, payload) for payload in payloads]
    return {"imported": len(records), "record_ids": [r["id"] for r in records], "originals_retained": True}


def _append_event(root: Path, event: dict[str, Any]) -> None:
    event = {**event, "at": _now()}
    with _safe(root / "events.jsonl").open("a", encoding="utf-8") as fh:
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
    p_der.add_argument("--id", dest="artifact_id", required=True)
    p_der.add_argument("--confirm", action="store_true")
    p_stale = art_sub.add_parser("stale")
    p_stale.add_argument("--source", required=True)
    p_stale.add_argument("--confirm", action="store_true")

    p_exp = sub.add_parser("export")
    p_exp.add_argument("dest", type=Path)
    p_exp.add_argument("--confirm", action="store_true")

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
        if args.art_cmd == "derive":
            return artifact_derive(root, args.from_ids.split(","), args.artifact_id, args.confirm)
        return artifact_stale(root, args.source, args.confirm)
    if args.cmd == "export":
        return export_store(root, args.dest, confirmed=args.confirm)
    if args.cmd == "delete":
        return delete_store(root, args.confirm)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
