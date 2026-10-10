"""Explicit, authorized portability of reviewed local knowledge.

Exports include private data only when every selected namespace and class is
explicitly granted. Import never confers acceptance. Deletion is logical;
older backups may retain content.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import uuid

from .memory import KnowledgeStore, SCHEMA_VERSION, SCHEMA_CHECKSUM, record_hash, safe_path

MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 10000
FORMAT = "agent-nexus-memory/1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _confirmed(confirmed):
    if confirmed is not True:
        raise ValueError("explicit confirmation required")


def _path(access, path, tool, *, output=False):
    path = safe_path(path)
    access.effective_grant.authorize("tools", tool, path)
    if output and (path.exists() or not path.parent.is_dir()):
        raise ValueError("destination must be new with an existing parent")
    if not output and not path.is_file():
        raise ValueError("source file does not exist")
    return path


def _class(access, sensitivity):
    if sensitivity not in {"public", "private", "restricted"}:
        raise ValueError("invalid sensitivity")
    access.effective_grant.authorize("data_classes", sensitivity)


def _publish(temp, destination):
    # Hard link publishes without overwriting a concurrent destination.
    os.link(temp, destination)
    temp.unlink()


def _write_document(destination, doc):
    text = _canonical(doc)
    if len(text.encode()) > MAX_EXPORT_BYTES:
        raise ValueError("export exceeds size bound")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as fh:
        temp = Path(fh.name)
        try:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
            _publish(temp, destination)
        finally:
            temp.unlink(missing_ok=True)


def _bump(db):
    db.execute("UPDATE store_meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")


def _authorize_all(store, access, db):
    store._authorize(access, "meta")
    for row in db.execute("SELECT DISTINCT namespace,sensitivity FROM records"):
        store._authorize(access, row["namespace"])
        _class(access, row["sensitivity"])


def export_store(store, access, destination, *, namespaces, confirmed=False):
    _confirmed(confirmed)
    destination = _path(access, destination, "memory.export", output=True)
    if not isinstance(namespaces, (list, tuple)) or not namespaces or any(not isinstance(n, str) or not n for n in namespaces):
        raise ValueError("explicit namespaces required")
    store._authorize(access, "meta")
    for namespace in namespaces:
        store._authorize(access, namespace)
    with store.connect() as db:
        db.execute("BEGIN")
        records = [dict(r) for r in db.execute("SELECT * FROM records WHERE deleted_at IS NULL ORDER BY id") if r["namespace"] in namespaces]
        if len(records) > MAX_RECORDS:
            raise ValueError("record bound exceeded")
        for record in records:
            _class(access, record["sensitivity"])
        ids = {r["id"] for r in records}
        links = [dict(r) for r in db.execute("SELECT * FROM record_sources") if r["record_id"] in ids]
        source_ids = {r["source_id"] for r in links}
        payload = {"format": FORMAT, "schema_version": SCHEMA_VERSION, "schema_checksum": SCHEMA_CHECKSUM,
                   "store_id": store.store_id, "namespaces": sorted(set(namespaces)), "records": records,
                   "sources": [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY id") if r["id"] in source_ids],
                   "record_sources": links,
                   "relationships": [dict(r) for r in db.execute("SELECT * FROM relationships") if r["src_id"] in ids and (r["dst_store_id"] != store.store_id or r["dst_id"] in ids)],
                   "dependencies": [dict(r) for r in db.execute("SELECT * FROM dependencies") if r["record_id"] in ids]}
        payload["manifest"] = {"payload_hash": _hash(payload), "record_hashes": {r["id"]: r["content_hash"] for r in records}}
    _, source_map = _validate_document(payload)
    # Reuse storage validation for all source types, bounds, and secrets.
    for record in records:
        evidence = [{**source_map[link["source_id"]], "span": link["span"]}
                    for link in payload["record_sources"] if link["record_id"] == record["id"]]
        checked = {key: record[key] for key in ("namespace", "kind", "title", "body", "sensitivity", "expires_at")}
        checked.update(record_id=record["id"], sources=evidence, dependencies={d["key"]: d["fingerprint"] for d in payload["dependencies"] if d["record_id"] == record["id"]})
        store._validated(checked)
    _write_document(destination, payload)
    return {"path": str(destination), "exported": len(records)}


def _unique(items, key, *, uuid_required=True):
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise ValueError("invalid collection")
    result = {}
    for item in items:
        ident = item.get(key)
        if not isinstance(ident, str) or not ident.strip() or len(ident) > 4096 or "\x00" in ident or ident in result:
            raise ValueError("duplicate or invalid ID")
        if uuid_required:
            uuid.UUID(ident)
        result[ident] = item
    return result


def _validate_document(doc):
    required = {"format", "schema_version", "schema_checksum", "store_id", "namespaces", "records", "sources", "record_sources", "relationships", "dependencies", "manifest"}
    if not isinstance(doc, dict) or set(doc) != required or doc["format"] != FORMAT:
        raise ValueError("unsupported export format")
    if doc["schema_version"] != SCHEMA_VERSION or doc["schema_checksum"] != SCHEMA_CHECKSUM:
        raise ValueError("unsupported export schema")
    uuid.UUID(doc["store_id"])
    manifest = doc["manifest"]
    if not isinstance(manifest, dict) or set(manifest) != {"payload_hash", "record_hashes"} or manifest["payload_hash"] != _hash({k:v for k,v in doc.items() if k != "manifest"}):
        raise ValueError("manifest integrity mismatch")
    records = _unique(doc["records"], "id")
    sources = _unique(doc["sources"], "id", uuid_required=False)
    if len(records) > MAX_RECORDS or len(sources) > MAX_RECORDS * 10:
        raise ValueError("collection bound exceeded")
    namespaces = doc["namespaces"]
    if not isinstance(namespaces, list) or not namespaces or any(not isinstance(n,str) or not n for n in namespaces):
        raise ValueError("invalid namespaces")
    if not isinstance(manifest["record_hashes"], dict) or set(manifest["record_hashes"]) != set(records):
        raise ValueError("record manifest mismatch")
    for record in records.values():
        for flag in ("stale", "conflicted"):
            if type(record.get(flag)) not in (bool, int) or record[flag] not in (0, 1):
                raise ValueError("invalid record state flag")
        if record.get("namespace") not in namespaces or record.get("deleted_at") is not None or record_hash(record) != record.get("content_hash") or manifest["record_hashes"][record["id"]] != record["content_hash"]:
            raise ValueError("record integrity mismatch")
    for name in ("record_sources", "relationships", "dependencies"):
        if not isinstance(doc[name],list) or len(doc[name]) > MAX_RECORDS * 20 or any(not isinstance(r,dict) for r in doc[name]):
            raise ValueError("invalid reference collection")
    for link in doc["record_sources"]:
        if set(link) != {"record_id","source_id","span"} or link["record_id"] not in records or link["source_id"] not in sources:
            raise ValueError("invalid provenance reference")
    if {link["source_id"] for link in doc["record_sources"]} != set(sources):
        raise ValueError("unreferenced source")
    if {link["record_id"] for link in doc["record_sources"]} != set(records):
        raise ValueError("record missing provenance")
    for dep in doc["dependencies"]:
        if set(dep) != {"record_id","key","fingerprint"} or dep["record_id"] not in records or not isinstance(dep["key"],str) or not isinstance(dep["fingerprint"],str):
            raise ValueError("invalid dependency")
    for rel in doc["relationships"]:
        if set(rel) != {"src_id","dst_store_id","dst_id","kind"} or rel["src_id"] not in records or not isinstance(rel["kind"],str) or not rel["kind"]:
            raise ValueError("invalid relationship")
        uuid.UUID(rel["dst_store_id"])
        uuid.UUID(rel["dst_id"])
        if rel["dst_store_id"] == doc["store_id"] and rel["dst_id"] not in records:
            raise ValueError("dangling relationship")
    return records, sources


def import_store(store, access, source, *, confirmed=False, reference_stores=None):
    _confirmed(confirmed)
    source = _path(access, source, "memory.import")
    if source.stat().st_size > MAX_EXPORT_BYTES:
        raise ValueError("import exceeds size bound")
    try:
        doc = json.loads(source.read_text())
        records, sources = _validate_document(doc)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed import") from exc
    for namespace in doc["namespaces"]:
        store._authorize(access, namespace, write=True)
    for r in records.values():
        _class(access, r["sensitivity"])
    references = reference_stores or {}
    for rel in doc["relationships"]:
        if rel["dst_store_id"] != doc["store_id"]:
            target = references.get(rel["dst_store_id"])
            if target is None or target.store_id != rel["dst_store_id"]:
                raise ValueError("external relationship requires supplied authorized store")
            target.inspect(rel["dst_id"], access)
    # Stable deterministic destination IDs preserve lineage on repeated imports.
    mapped = {old: str(uuid.uuid5(uuid.UUID(store.store_id), doc["store_id"] + ":" + old)) for old in records}
    validated = {}
    for old, record in records.items():
        evidence = []
        for link in doc["record_sources"]:
            if link["record_id"] == old:
                item = dict(sources[link["source_id"]])
                item["id"] = str(uuid.uuid5(uuid.UUID(store.store_id), doc["store_id"] + ":source:" + item["id"]))
                item["span"] = link["span"]
                evidence.append(item)
        deps = {d["key"]: d["fingerprint"] for d in doc["dependencies"] if d["record_id"] == old}
        payload = {key:record[key] for key in ("namespace","kind","title","body","sensitivity","expires_at")}
        payload.update(record_id=mapped[old], sources=evidence, dependencies=deps)
        validated[old] = store._validated(payload)
    with store.connect(write=True) as db:
        for old, payload in validated.items():
            store._insert_draft(db, access, payload)
            # Re-import cannot clear an existing stale/conflict restriction.
            db.execute("UPDATE records SET stale=MAX(stale,?),conflicted=MAX(conflicted,?) WHERE id=?",
                       (int(records[old]["stale"]), int(records[old]["conflicted"]), mapped[old]))
            db.execute("INSERT OR IGNORE INTO import_lineage(record_id,source_store,source_id,source_hash) VALUES(?,?,?,?)", (mapped[old],doc["store_id"],old,records[old]["content_hash"]))
        for rel in doc["relationships"]:
            local = rel["dst_store_id"] == doc["store_id"]
            db.execute("INSERT OR IGNORE INTO relationships(src_id,dst_store_id,dst_id,kind) VALUES(?,?,?,?)", (mapped[rel["src_id"]],store.store_id if local else rel["dst_store_id"],mapped[rel["dst_id"]] if local else rel["dst_id"],rel["kind"]))
    return {"imported": len(records), "record_ids": list(mapped.values())}


def backup_store(store, access, destination, *, confirmed=False):
    _confirmed(confirmed)
    destination = _path(access, destination, "memory.backup", output=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as fh:
        temp = Path(fh.name)
    try:
        with store.connect() as source:
            source.execute("BEGIN")
            _authorize_all(store, access, source)
            with sqlite3.connect(temp) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("backup integrity failure")
        _publish(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    return {"path": str(destination), "store_id": store.store_id}


def promote_record(source, destination, source_access, destination_access, record_id, *, namespace="default", title, body, expected_hash, confirmed=False, fingerprints=None):
    _confirmed(confirmed)
    if fingerprints is not None and (not isinstance(fingerprints, dict) or len(fingerprints) > 256):
        raise ValueError("bounded current fingerprint map required")
    current_fingerprints = fingerprints if fingerprints is not None else {}
    for key, value in current_fingerprints.items():
        if any(not isinstance(x, str) or not x.strip() or len(x) > 4096 or "\x00" in x for x in (key, value)):
            raise ValueError("invalid current fingerprint")
    original = source.inspect(record_id, source_access)
    if any(current_fingerprints.get(key) != value for key, value in original["dependencies"].items()):
        raise ValueError("source dependencies require matching current fingerprints")
    if original["content_hash"] != expected_hash or original["verification_state"] != "accepted" or original.get("stale") or original.get("conflicted") or (original.get("expires_at") is not None and original["expires_at"] <= time.time()):
        raise ValueError("source must be current accepted record with matching hash")
    if not isinstance(title,str) or not title.strip() or not isinstance(body,str) or not body.strip() or body == original["body"] or title == original["title"]:
        raise ValueError("explicit reviewed transformed title and body required")
    destination._authorize(destination_access, namespace, write=True)
    _class(destination_access, "public")
    with source.connect() as db:
        current = db.execute("SELECT content_hash,verification_state,stale,conflicted,deleted_at,expires_at FROM records WHERE id=?",(record_id,)).fetchone()
        if current is None or current["content_hash"] != expected_hash or current["deleted_at"] or current["stale"] or current["conflicted"] or current["verification_state"] != "accepted" or (current["expires_at"] is not None and current["expires_at"] <= time.time()):
            raise ValueError("source changed during promotion")
        dependencies = dict(db.execute("SELECT key,fingerprint FROM dependencies WHERE record_id=?", (record_id,)))
        if any(current_fingerprints.get(key) != value for key, value in dependencies.items()):
            raise ValueError("source dependencies changed during promotion")
        with destination.connect(write=True) as out:
            promoted = destination._insert_draft(out, destination_access, {"namespace":namespace,"kind":"note","title":title,"body":body,"sensitivity":"public","sources":[{"locator":f"memory:{source.store_id}:{record_id}","retrieved_at":time.time(),"content_hash":expected_hash,"retrieval_status":"provided","synthetic":False}],"dependencies":{}})
            destination_id = promoted["id"] if isinstance(promoted,dict) else promoted
            out.execute("INSERT INTO promotions(source_store,source_id,destination_id,source_hash,transformation,approved_by,at) VALUES(?,?,?,?,?,?,?)",(source.store_id,record_id,destination_id,expected_hash,"explicit reviewed transformation",destination_access.identity,time.time()))
    return destination.inspect(destination_id, destination_access)


def delete_record(store, access, record_id, *, expected_hash, confirmed=False):
    _confirmed(confirmed)
    record = store.inspect(record_id,access)
    store._authorize(access, record["namespace"], write=True)
    now = time.time()
    with store.connect(write=True) as db:
        row = db.execute("SELECT * FROM records WHERE id=?",(record_id,)).fetchone()
        if not row or row["deleted_at"] is not None or row["content_hash"] != expected_hash:
            raise ValueError("delete hash mismatch")
        db.execute("DELETE FROM records_fts WHERE record_id=?",(record_id,))
        source_ids = [r[0] for r in db.execute("SELECT source_id FROM record_sources WHERE record_id=?",(record_id,))]
        db.execute("DELETE FROM record_sources WHERE record_id=?",(record_id,))
        for ident in source_ids:
            db.execute("DELETE FROM sources WHERE id=? AND NOT EXISTS(SELECT 1 FROM record_sources WHERE source_id=?)",(ident,ident))
        db.execute("DELETE FROM dependencies WHERE record_id=?",(record_id,))
        db.execute("DELETE FROM relationships WHERE src_id=? OR (dst_store_id=? AND dst_id=?)",(record_id,store.store_id,record_id))
        db.execute("DELETE FROM record_revisions WHERE record_id=?",(record_id,))
        db.execute("DELETE FROM import_lineage WHERE record_id=?",(record_id,))
        db.execute("UPDATE records SET title='',body='',author_identity='',run_id='',deleted_at=?,stale=1,updated_at=? WHERE id=?",(now,now,record_id))
        db.execute("INSERT INTO memory_tombstones(record_id,deleted_at,purge_after) VALUES(?,?,?)",(record_id,now,now+30*86400))
        _bump(db)
    return {"deleted": record_id, "purge_after": now+30*86400}


def memory_doctor(store, access):
    with store.connect() as db:
        db.execute("BEGIN")
        _authorize_all(store, access, db)
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
        count = lambda sql, args=(): db.execute(sql,args).fetchone()[0]
        migration = db.execute("SELECT checksum FROM schema_migrations WHERE version=?",(SCHEMA_VERSION,)).fetchone()
        return {"schema_version": SCHEMA_VERSION, "schema_ok": bool(migration and migration[0] == SCHEMA_CHECKSUM),
                "integrity_ok": len(integrity)==1 and integrity[0][0]=="ok", "foreign_key_errors":len(foreign_keys),
                "records":count("SELECT count(*) FROM records WHERE deleted_at IS NULL"),
                "tombstones":count("SELECT count(*) FROM memory_tombstones"),
                "missing_provenance":count("SELECT count(*) FROM records r WHERE deleted_at IS NULL AND NOT EXISTS(SELECT 1 FROM record_sources s WHERE s.record_id=r.id)"),
                "fts_mismatches":count("SELECT count(*) FROM records r WHERE deleted_at IS NULL AND NOT EXISTS(SELECT 1 FROM records_fts f WHERE f.record_id=r.id AND f.title=r.title AND f.body=r.body)")+count("SELECT count(*) FROM records_fts f WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.id=f.record_id AND r.deleted_at IS NULL)"),
                "content_hash_errors":sum(record_hash(dict(r)) != r["content_hash"] for r in db.execute("SELECT * FROM records WHERE deleted_at IS NULL")),
                "dependency_records":count("SELECT count(DISTINCT record_id) FROM dependencies"),
                "expired_caches":count("SELECT count(*) FROM records WHERE deleted_at IS NULL AND kind='cache' AND expires_at <= ?",(time.time(),))}
