"""Deterministic mock Director responses (mock-by-default)."""

from __future__ import annotations

import json
from typing import Any


def mock_director_response(task_id: str, prompt: str) -> dict[str, Any]:
    try:
        packet = json.loads(prompt)
    except json.JSONDecodeError:
        packet = {}
    ph = packet.get("packet_hash", "sha256:unknown")
    allowed = [r["evidence_id"] for r in packet.get("fact_table", [])] or ["EVD-A1"]

    if task_id == "director_invalid":
        return {
            "structured": {
                "packet_hash": ph,
                "conclusions": [
                    {
                        "conclusion_id": "C-1",
                        "text": "New fact invented",
                        "evidence_ids": ["EVD-INVENTED"],
                    }
                ],
                "claim_links": [],
                "alternatives": [],
                "unfavorable_evidence": [],
                "experiments": [],
                "unknowns": [],
                "format": "doctoral_synthesis",
                "new_facts": ["bad"],
            },
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    if task_id == "challenge_critique":
        return {
            "structured": {
                "critique": [{"severity": "critical", "evidence_id": allowed[0], "block_recommendation": True}],
                "agrees_with_director": False,
            },
            "usage": {"prompt_tokens": 80, "completion_tokens": 40},
        }

    eid = allowed[0]
    return {
        "structured": {
            "packet_hash": ph,
            "conclusions": [
                {
                    "conclusion_id": "C-1",
                    "text": "Proceed with bounded experiment aligned to charter.",
                    "evidence_ids": [eid],
                    "premises": ["Scrutiny cleared", "Promotion rules passed"],
                }
            ],
            "claim_links": [eid],
            "alternatives": ["Defer architecture change"],
            "unfavorable_evidence": [],
            "experiments": packet.get("experiments", [])[:1],
            "unknowns": packet.get("unknowns", []),
            "format": "doctoral_synthesis",
        },
        "usage": {"prompt_tokens": 120, "completion_tokens": 60},
    }
