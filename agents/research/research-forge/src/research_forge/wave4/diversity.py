"""Ideator diversity detection (RF-W4-A-06)."""

from __future__ import annotations

import re
from typing import Any

_GENERIC = re.compile(
    r"\b(best practice|industry standard|digital transformation|synergy|holistic)\b",
    re.I,
)
_MODULE_RENAME = re.compile(r"\b(module|service|component)\s+[A-Za-z0-9_-]+\b", re.I)


def _token_set(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class DiversityChecker:
    def check_pair(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        flags: list[str] = []
        lt = _token_set(left.get("proposal", "") + left.get("root_cause_model", ""))
        rt = _token_set(right.get("proposal", "") + right.get("root_cause_model", ""))
        if _jaccard(lt, rt) >= 0.85:
            flags.append("paraphrase")
        if _GENERIC.search(left.get("proposal", "")) and _GENERIC.search(right.get("proposal", "")):
            flags.append("generic_best_practice")
        lc = left.get("components") or []
        rc = right.get("components") or []
        component_sim = 0.0
        if lc and rc:
            component_sim = _jaccard(_token_set(" ".join(lc)), _token_set(" ".join(rc)))
        if component_sim >= 0.5 and left.get("root_cause_model") == right.get("root_cause_model"):
            if _MODULE_RENAME.search(" ".join(lc)) and _MODULE_RENAME.search(" ".join(rc)):
                flags.append("renamed_modules_same_architecture")
                if component_sim >= 0.5 and _jaccard(lt, rt) >= 0.65:
                    flags.append("paraphrase")
        if _jaccard(lt, rt) >= 0.85:
            if "paraphrase" not in flags:
                flags.append("paraphrase")
        return flags

    def check_batch(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, a in enumerate(candidates):
            for j in range(i + 1, len(candidates)):
                flags = self.check_pair(a, candidates[j])
                if flags:
                    out.append({"idea_ids": [a["idea_id"], candidates[j]["idea_id"]], "flags": flags})
        return out

    def is_near_clone(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        return bool(self.check_pair(left, right))
