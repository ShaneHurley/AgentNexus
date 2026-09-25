#!/usr/bin/env bash
# Start the shared agent dashboard (macOS / Linux)
set -euo pipefail
cd "$(dirname "$0")"

pick_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$c"
        return 0
      fi
    fi
  done
  return 1
}

PY="$(pick_python)" || {
  echo "Python 3.10+ not found." >&2
  exit 1
}

exec "$PY" start.py "$@"
