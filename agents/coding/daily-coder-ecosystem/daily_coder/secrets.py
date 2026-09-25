"""Provider secret storage.

Secret values live in the OS keyring when available, otherwise in a file with
owner-only permissions. SQLite and the API store identifiers and fingerprints only.
"""
from __future__ import annotations
import json, os, stat
from pathlib import Path
from .util import sha256_text

class SecretStore:
    def __init__(self, path, allow_insecure_file=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keyring = self._load_keyring()
        self.allow_insecure_file = allow_insecure_file

    @staticmethod
    def _load_keyring():
        try:
            import keyring  # optional dependency
            return keyring
        except Exception:
            return None

    def _file(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, data):
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        if os.name != "nt":
            self.path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def set(self, name, value):
        if self._keyring:
            self._keyring.set_password("daily-coder", name, value)
            data = self._file(); data[name] = {"backend": "keyring", "fingerprint": _fp(value)}
        elif self.allow_insecure_file:
            data = self._file(); data[name] = {"backend": "file", "value": value, "fingerprint": _fp(value)}
        else:
            raise RuntimeError("OS keyring is unavailable; refusing to store a plaintext secret")
        self._save(data)
        return {"name": name, "backend": data[name]["backend"], "fingerprint": data[name]["fingerprint"]}

    def get(self, name):
        env = os.environ.get(name) or os.environ.get(name.upper().replace("-", "_"))
        if env:
            return env
        entry = self._file().get(name)
        if not entry:
            return None
        if entry["backend"] == "keyring" and self._keyring:
            return self._keyring.get_password("daily-coder", name)
        return entry.get("value")

    def delete(self, name):
        data = self._file()
        if name in data:
            if data[name]["backend"] == "keyring" and self._keyring:
                try: self._keyring.delete_password("daily-coder", name)
                except Exception: pass
            del data[name]
            self._save(data)
            return True
        return False

    def list(self):
        """Never returns secret values."""
        return [{"name": k, "backend": v["backend"], "fingerprint": v["fingerprint"]} for k, v in sorted(self._file().items())]


def _fp(value: str) -> str:
    return sha256_text(value)[:12]
