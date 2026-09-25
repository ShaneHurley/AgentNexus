"""Invalid Director output routing (RF-W5-B-06)."""

from __future__ import annotations

from typing import Any

from research_forge.wave5.types import PRE_DIRECTOR_FALLBACK


class DirectorOutputRouter:
    """One schema-repair attempt without new reasoning."""

    def __init__(self) -> None:
        self.repair_attempted = False

    def route(
        self,
        *,
        output: dict[str, Any],
        validation: dict[str, Any],
        pre_director: dict[str, Any],
    ) -> dict[str, Any]:
        if validation.get("valid"):
            return {"status": "accepted", "output": output, "repair_used": False}

        if not self.repair_attempted:
            self.repair_attempted = True
            repaired = dict(output)
            repaired.pop("new_facts", None)
            repaired.pop("unsupported_claims", None)
            if "format" not in repaired:
                repaired["format"] = pre_director.get("format", "doctoral_synthesis")
            return {
                "status": "repair_attempt",
                "output": repaired,
                "repair_used": True,
                "note": "structural_repair_only",
            }

        return {
            "status": "fallback",
            "output": pre_director,
            "source": PRE_DIRECTOR_FALLBACK,
            "validation_issues": validation.get("issues", []),
            "director_failed": True,
        }
