from __future__ import annotations

import json

from research_forge.errors import ErrorCode, forge_error


def test_error_round_trip() -> None:
    err = forge_error(ErrorCode.POLICY_DENIED, "denied", rule="default_deny")
    raw = json.dumps(err.to_dict())
    loaded = json.loads(raw)
    assert loaded["code"] == "POLICY_DENIED"
    assert loaded["details"]["rule"] == "default_deny"
