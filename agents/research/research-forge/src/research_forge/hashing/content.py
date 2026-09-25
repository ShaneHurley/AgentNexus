"""Canonical content hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

HASH_ALGORITHM = "sha256-v1"
NORMALIZATION_VERSION = "text-nfkc-v1"


def hash_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"


def hash_normalized_text(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKC", text)
    return hash_bytes(normalized.encode("utf-8"))


def hash_file_stream(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def hash_retrieved_content(
    content: bytes,
    adapter_id: str,
    retrieval_metadata: dict[str, str],
) -> str:
    meta = "|".join(f"{k}={retrieval_metadata[k]}" for k in sorted(retrieval_metadata))
    payload = adapter_id.encode() + b"\0" + meta.encode() + b"\0" + content
    return hash_bytes(payload)
