"""CLI entry: python -m agent_dashboard"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

from .server import serve


def main(argv=None):
    parser = argparse.ArgumentParser(description="Shared agent orchestration dashboard")
    parser.add_argument("--config", type=Path, default=None, help="Path to config/agents.json")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--token",
        default=os.environ.get("AGENT_DASHBOARD_TOKEN"),
        help="Hub API token when auth_required is true (default: AGENT_DASHBOARD_TOKEN env)",
    )
    args = parser.parse_args(argv)
    serve(config_path=args.config, host=args.host, port=args.port, token=args.token)


if __name__ == "__main__":
    main()
