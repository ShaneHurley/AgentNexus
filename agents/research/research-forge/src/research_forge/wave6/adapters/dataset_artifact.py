"""Dataset/code artifact metadata — no execution (RF-W6-B-08)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockDatasetArtifactAdapter:
    adapter_id = "mock_dataset"
    protocol_version = PROTOCOL_VERSION

    _ARTIFACTS: dict[str, dict[str, Any]] = {
        "ds-001": {
            "name": "benchmark-v2",
            "version": "2.1.0",
            "license": "CC-BY-4.0",
            "checksum": "sha256:abc",
            "environment": "python3.11",
            "source_code_path": "src/train.py",
            "source_code_text": "# training script — data only, not executed",
        }
    }

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read", "metadata"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        hits = [
            {
                "result_id": aid,
                "canonical_title": a["name"],
                "source_type": "dataset",
                "version": a["version"],
            }
            for aid, a in self._ARTIFACTS.items()
            if query.lower() in a["name"].lower()
        ]
        return {"results": hits, "next_cursor": None}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        aid = locator.get("artifact_id")
        art = self._ARTIFACTS.get(aid or "")
        if not art:
            return {"error": "not_found"}
        return {
            "access_level": "metadata",
            "access_disclosure": f"license={art['license']}",
            "locator": {"kind": "dataset", "value": aid},
            "content_hash": art["checksum"].split(":", 1)[-1],
            "reproducibility": {
                "version": art["version"],
                "environment": art["environment"],
                "checksum": art["checksum"],
            },
            "source_code": art["source_code_text"],
            "executed": False,
        }

    def execute(self, *_a: Any, **_k: Any) -> None:
        raise PermissionError("execution disabled")
