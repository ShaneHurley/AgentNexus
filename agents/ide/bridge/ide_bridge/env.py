"""Bridge child-process environment."""

from __future__ import annotations

import os
from typing import Mapping


def bridge_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["IDE_BRIDGE_ACTIVE"] = "1"
    if extra:
        env.update(extra)
    return env
