#!/usr/bin/env python3
"""Cross-platform launcher for the shared agent dashboard.

Works on Windows, macOS, and Linux with Python 3.10+.
Parsable on older Pythons so it can re-launch a newer interpreter.
Creates .venv, upgrades bootstrap tooling, then serves the UI via PYTHONPATH.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

# Floor is Python 3.10+; current pip/setuptools are fine on that range.
BOOTSTRAP_PINS = (
    "pip>=24.2",
    "setuptools>=68",
    "wheel>=0.42",
)
BOOTSTRAP_MARKER_VERSION = "2"  # bump when BOOTSTRAP_PINS change


def _probe(cmd):
    try:
        out = subprocess.check_output(
            cmd + ["-c", "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        major_s, minor_s = lines[1].split(".")
        return lines[0], (int(major_s), int(minor_s))
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        return None


def find_base_python():
    """Prefer a newer interpreter when several are installed."""
    if sys.version_info >= (3, 10):
        return sys.executable

    candidates = []
    if platform.system() == "Windows" and shutil.which("py"):
        for ver in ("3.13", "3.12", "3.11", "3.10"):
            candidates.append(["py", "-" + ver])
        candidates.append(["py", "-3"])
    for name in (
        "python3.13", "python3.12", "python3.11", "python3.10",
        "python3", "python",
    ):
        path = shutil.which(name)
        if path:
            candidates.append([path])

    for cmd in candidates:
        probed = _probe(cmd)
        if probed and probed[1] >= (3, 10):
            return probed[0]
    return sys.executable


def venv_python():
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(cmd):
    print("+", " ".join(cmd))
    sys.stdout.flush()
    subprocess.check_call(cmd, cwd=str(ROOT))


def ensure_venv():
    py = venv_python()
    if py.is_file():
        try:
            out = subprocess.check_output(
                [str(py), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            major_s, minor_s = out.split(".", 1)
            if (int(major_s), int(minor_s)) >= (3, 10):
                return py
            print(
                "Existing .venv is Python %s (<3.10); recreating with a newer interpreter..."
                % out
            )
            sys.stdout.flush()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
            print("Existing .venv is unusable; recreating...")
            sys.stdout.flush()
        shutil.rmtree(VENV, ignore_errors=True)

    base = find_base_python()
    print("Creating virtualenv at %s with %s ..." % (VENV, base))
    sys.stdout.flush()
    subprocess.check_call([base, "-m", "venv", str(VENV)], cwd=str(ROOT))
    return venv_python()


def _marker_ok(marker: Path) -> bool:
    if not marker.is_file():
        return False
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return text == "v%s" % BOOTSTRAP_MARKER_VERSION or text.startswith(
        "v%s|" % BOOTSTRAP_MARKER_VERSION
    )


def ensure_install(py, *, force: bool = False):
    # Prefer PYTHONPATH over editable install so the project tree does not
    # get absolute local paths written into .venv metadata.
    marker = VENV / ".agent_dashboard_installed"
    if not force and _marker_ok(marker):
        return
    run([str(py), "-m", "pip", "install", "--upgrade", *BOOTSTRAP_PINS])
    marker.write_text(
        "v%s|%s\n" % (BOOTSTRAP_MARKER_VERSION, ",".join(BOOTSTRAP_PINS)),
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the shared agent orchestration dashboard")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--skip-install", action="store_true", help="Assume .venv already set up")
    parser.add_argument(
        "--refresh-bootstrap",
        action="store_true",
        help="Re-install pip/setuptools/wheel into .venv",
    )
    args, rest = parser.parse_known_args(argv)

    argv_rest = list(argv) if argv is not None else sys.argv[1:]

    if sys.version_info < (3, 10):
        better = find_base_python()
        if os.path.normcase(os.path.abspath(better)) != os.path.normcase(os.path.abspath(sys.executable)):
            print("Re-launching with %s" % better)
            sys.stdout.flush()
            return subprocess.call([better, str(ROOT / "start.py")] + argv_rest)
        sys.stderr.write("Python 3.10+ required (found %s)\n" % sys.version)
        return 1

    py = ensure_venv()
    if not args.skip_install:
        ensure_install(py, force=args.refresh_bootstrap)

    host = args.host or "127.0.0.1"
    port = args.port or 8866
    config_path = args.config or (ROOT / "config" / "agents.json")
    if config_path.is_file() and (args.host is None or args.port is None):
        try:
            import json
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            if args.host is None:
                host = cfg.get("host", host)
            if args.port is None:
                port = int(cfg.get("port", port))
        except Exception:
            pass

    url = "http://%s:%s/" % (host, port)
    print("\nAgent dashboard -> %s\n" % url)
    sys.stdout.flush()

    cmd = [
        str(py), "-m", "agent_dashboard",
        "--config", str(config_path),
        "--host", host,
        "--port", str(port),
    ]
    if args.token:
        cmd += ["--token", args.token]
    cmd += rest

    if not args.no_browser:
        def _open():
            time.sleep(0.8)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        import threading
        t = threading.Thread(target=_open)
        t.daemon = True
        t.start()

    env = os.environ.copy()
    sep = ";" if platform.system() == "Windows" else ":"
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (sep + prev if prev else "")
    # Pin checkout root so docs/, config/, and web assets resolve even if cwd drifts.
    env["AGENT_DASHBOARD_ROOT"] = str(ROOT)

    os.chdir(str(ROOT))
    if platform.system() != "Windows":
        os.execve(str(py), cmd, env)
        return 0
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
