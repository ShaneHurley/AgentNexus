"""Local Markdown/text reader (RF-W1-E-02)."""

from __future__ import annotations

from pathlib import Path

from research_forge.adapters.reader.protocol import ContentChunk, ReaderResponse
from research_forge.hashing.content import hash_file_stream

MAX_BYTES = 512_000
ALLOWED_SUFFIX = {".md", ".txt", ".markdown"}


class LocalTextReader:
    adapter_id = "local_reader_v1"

    def read(
        self,
        source_ref: dict[str, object],
        *,
        locator: str | None = None,
    ) -> dict[str, object]:
        path_str = str(source_ref.get("path") or "")
        path = Path(path_str)
        if not path.is_file():
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "inaccessible", "path": path_str},
            ).to_dict()
        if path.suffix.lower() not in ALLOWED_SUFFIX:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "unsupported_mime", "suffix": path.suffix},
            ).to_dict()
        size = path.stat().st_size
        if size > MAX_BYTES:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "oversized", "size": size},
            ).to_dict()
        for enc in ("utf-8", "iso-8859-1"):
            try:
                text = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                text = None
        if text is None:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "encoding_error"},
            ).to_dict()
        chunks = self._chunk(text, locator)
        content_hash = hash_file_stream(path)
        return ReaderResponse(
            access_level="full",
            chunks=chunks,
            metadata={"encoding": enc, "content_hash": content_hash, "path": str(path)},
            raw_byte_ref=f"file://{path.as_posix()}",
        ).to_dict()

    def _chunk(self, text: str, locator: str | None) -> list[ContentChunk]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[ContentChunk] = []
        for i, para in enumerate(paragraphs):
            loc = f"paragraph:{i+1}"
            if locator and locator != loc:
                continue
            chunks.append(
                ContentChunk(chunk_id=f"chk-{i+1}", locator=loc, text=para, access_level="full")
            )
        if locator and not chunks:
            chunks.append(
                ContentChunk(
                    chunk_id="chk-miss",
                    locator=locator,
                    text="",
                    access_level="metadata",
                )
            )
        return chunks or [
            ContentChunk(chunk_id="chk-1", locator="paragraph:1", text=text[:2000], access_level="full")
        ]
