"""daily-coder-ecosystem package."""

import sys
from pathlib import Path

__version__ = "0.1.0"

# Defensive bootstrap: ensure agent_core can be imported even if not pip-installed
try:
    import agent_core  # noqa: F401
except ImportError:
    _curr = Path(__file__).resolve().parent
    for _parent in _curr.parents:
        _cand = _parent / "agents" / "shared" / "agent-core"
        if _cand.is_dir():
            sys.path.insert(0, str(_cand))
            break
        _cand_alt = _parent / "shared" / "agent-core"
        if _cand_alt.is_dir():
            sys.path.insert(0, str(_cand_alt))
            break
