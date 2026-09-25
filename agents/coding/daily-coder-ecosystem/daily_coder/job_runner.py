"""Detached job wrapper that persists the real child exit status."""
from __future__ import annotations
import argparse, json, subprocess, time
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    started = time.time()
    result = {"argv": command, "started": started, "exit_code": None, "state": "failed"}
    try:
        cp = subprocess.run(command, timeout=args.timeout or None)
        result.update(exit_code=cp.returncode, state="succeeded" if cp.returncode == 0 else "failed")
    except subprocess.TimeoutExpired:
        result.update(state="timeout", error=f"timed out after {args.timeout}s")
    except Exception as exc:
        result.update(state="failed", error=f"{type(exc).__name__}: {exc}")
    result["finished"] = time.time()
    result["duration_s"] = result["finished"] - started
    path = Path(args.result)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    temp.replace(path)
    return 0 if result["state"] == "succeeded" else 1

if __name__ == "__main__":
    raise SystemExit(main())
