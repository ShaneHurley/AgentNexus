#!/usr/bin/env bash
# Install the locked workspace and optionally launch the dashboard.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
case "${1:-}" in
    ""|--gui) ;;
    *) echo "Usage: ./start_mac.sh [--gui]" >&2; exit 2 ;;
esac
if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install uv, then rerun ./start_mac.sh." >&2
    exit 1
fi
# uv enforces the workspace Python >=3.10 requirement and verifies the lock.
# Never delete an existing environment or substitute foreign packages on failure.
uv sync --locked --all-packages
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
"$PYTHON_BIN" agents/ide/scripts/sync_ide_agents.py
"$PYTHON_BIN" -m ai_agents_repo.validate --phase F0
if [ "${1:-}" = "--gui" ]; then
    exec "$PYTHON_BIN" "$SCRIPT_DIR/gui/start.py"
fi
echo "Setup complete. Launch with ./start_mac.sh --gui."
