"""Near-duplicate idea clustering (RF-W4-B-03)."""

from __future__ import annotations

import re
from typing import Any

from research_forge.wave4.diversity import _token_set, _jaccard


def _mechanism_signature(idea: dict[str, Any]) -> set[str]:
    parts = [
        idea.get("root_cause_model", ""),
        idea.get("proposal", ""),
        " ".join(idea.get("components") or []),
        " ".join(idea.get("assumptions") or []),
        idea.get("falsification_test", ""),
    ]
    return _token_set(" ".join(parts))


class NearDuplicateDetector:
    def similarity(self, left: dict[str, Any], right: dict[str, Any]) -> float:
        return _jaccard(_mechanism_signature(left), _mechanism_signature(right))

    def cluster(self, ideas: list[dict[str, Any]], threshold: float = 0.82) -> list[list[str]]:
        clusters: list[list[str]] = []
        assigned: set[str] = set()
        for i, a in enumerate(ideas):
            if a["idea_id"] in assigned:
                continue
            group = [a["idea_id"]]
            assigned.add(a["idea_id"])
            for j in range(i + 1, len(ideas)):
                b = ideas[j]
                if b["idea_id"] in assigned:
                    continue
                if self.similarity(a, b) >= threshold:
                    group.append(b["idea_id"])
                    assigned.add(b["idea_id"])
            if len(group) > 1:
                clusters.append(group)
        return clusters

    def title_differs_mechanism_same(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        titles = re.sub(r"\W+", "", left.get("title", "").lower()), re.sub(
            r"\W+", "", right.get("title", "").lower()
        )
        return titles[0] != titles[1] and self.similarity(left, right) >= 0.82
