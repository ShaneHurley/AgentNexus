"""Validated, immutable model catalogs; publishing never changes active pins."""
from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def routing_policy_digest(policy):
    """SHA-256 of canonical routing policy excluding role qualification reports.

    Remove each roles[role].qualifications field entirely, preserving every other
    policy field, then hash canonical sorted compact JSON. Evaluation policy_hash
    uses this digest; adding reviewed reports cannot create a circular dependency.
    Full policy snapshot hashes remain separate run pins. Any routing-policy change
    (including another role) invalidates prior qualification evidence.
    """
    fields(policy, {"schema_version", "roles"}, {"schema_version", "roles"})
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or not isinstance(policy["roles"], dict):
        raise ValueError("unsupported policy schema")
    clean=json.loads(canonical(policy))
    for spec in clean["roles"].values():
        if not isinstance(spec,dict): raise ValueError("invalid routing policy role")
        spec.pop("qualifications",None)
    return digest(clean)


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("invalid fields")


def number(value, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid " + name)
    if integer and not isinstance(value, int):
        raise ValueError("invalid " + name)
    return value


def strings(value, name):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value) or len(set(value)) != len(value):
        raise ValueError("invalid " + name)


def validate_catalog(data):
    fields(data, {"schema_version", "models"}, {"schema_version", "models"})
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or not isinstance(data["models"], dict) or not data["models"]:
        raise ValueError("unsupported catalog schema")
    required = {"provider", "model", "context_tokens", "output_tokens", "risks", "privacy", "features", "credential_ref", "pricing", "latency_ms"}
    for alias, model in data["models"].items():
        if not isinstance(alias, str) or not alias:
            raise ValueError("invalid alias")
        fields(model, required, required)
        for key in ("provider", "model"):
            if not isinstance(model[key], str) or not model[key]: raise ValueError("invalid " + key)
        for key in ("context_tokens", "output_tokens"):
            number(model[key], key, True)
            if model[key] == 0: raise ValueError("invalid capacity")
        for key in ("risks", "privacy", "features"): strings(model[key], key)
        ref = model["credential_ref"]
        if ref is not None and (not isinstance(ref, str) or not ref): raise ValueError("invalid credential reference")
        fields(model["pricing"], {"input_per_million", "output_per_million"}, {"input_per_million", "output_per_million"})
        for key, val in model["pricing"].items():
            if val is not None: number(val, key)
        if model["latency_ms"] is not None: number(model["latency_ms"], "latency_ms")
    canonical(data)


@dataclass(frozen=True)
class CatalogSnapshot:
    _json: str
    hash: str

    @classmethod
    def from_dict(cls, payload):
        validate_catalog(payload)
        encoded = canonical(payload)
        return cls(encoded, hashlib.sha256(encoded.encode()).hexdigest())

    @property
    def data(self):
        return json.loads(self._json)


class CatalogStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, pin):
        if not isinstance(pin, str) or len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin):
            raise ValueError("invalid catalog pin")
        return self.path / (pin + ".json")

    def _atomic(self, destination, content):
        fd, tmp = tempfile.mkstemp(dir=self.path, prefix=".candidate-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp, destination)
            directory = os.open(self.path, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def publish(self, payload):
        snapshot = CatalogSnapshot.from_dict(payload)
        destination = self._snapshot_path(snapshot.hash)
        if destination.exists():
            self.load(snapshot.hash)
        else:
            self._atomic(destination, snapshot._json)
        return snapshot

    def activate(self, pin, *, confirmed=False):
        if confirmed is not True: raise ValueError("catalog activation requires confirmation")
        snapshot = self.load(pin)
        self._atomic(self.path / "active.json", canonical({"catalog_hash": snapshot.hash}))
        return snapshot

    def load(self, pin=None):
        if pin is None:
            try:
                active = json.loads((self.path / "active.json").read_text())
                fields(active, {"catalog_hash"}, {"catalog_hash"})
                pin = active["catalog_hash"]
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("no active catalog") from exc
        try: payload = json.loads(self._snapshot_path(pin).read_text())
        except (OSError, json.JSONDecodeError) as exc: raise ValueError("missing or invalid catalog pin") from exc
        snapshot = CatalogSnapshot.from_dict(payload)
        if snapshot.hash != pin: raise ValueError("catalog integrity mismatch")
        return snapshot

    def diff(self, old_pin, new_pin):
        old, new = self.load(old_pin).data["models"], self.load(new_pin).data["models"]
        return {"old_hash": old_pin, "new_hash": new_pin,
                "added": sorted(set(new)-set(old)), "removed": sorted(set(old)-set(new)),
                "changed": {key: {"before": old[key], "after": new[key]} for key in sorted(set(old)&set(new)) if old[key] != new[key]}}
