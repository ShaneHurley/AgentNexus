"""Stdlib HTTP host for the shared dashboard and unified agent API."""
from __future__ import annotations

import json
import mimetypes
import os
import secrets as _secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .paths import docs_dir, project_root, resolve_data_dir
from .registry import Registry, load_config
from .routes import dispatch_get, dispatch_post, dispatch_put
from .routes.common import authorized, read_body, send
from .routes.home import SnapshotCache
from .routes.workshop import WorkshopSnapshotCache
from .routes import common as route_common
from .terminal_registry import TerminalRegistry
from .usage_store import UsageStore

# Backward-compatible test imports
_limit = route_common.limit
_resume_http_status = route_common.resume_http_status

WEB_ROOT = Path(__file__).resolve().parent / "web"


class _Handler(BaseHTTPRequestHandler):
    server_version = "agent-dashboard"

    def log_message(self, fmt, *args):  # quiet by default
        pass

    def _send(self, code: int, payload, content_type: str = "application/json"):
        return send(self, code, payload, content_type)

    def _authorized(self) -> bool:
        return authorized(self)

    def _body(self) -> dict:
        return read_body(self)

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        if ".." in rel or rel.startswith("/"):
            return self._send(404, {"error": "not found"})
        file_path = (WEB_ROOT / rel).resolve()
        if not str(file_path).startswith(str(WEB_ROOT.resolve())) or not file_path.is_file():
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        # Browsers reject ES modules served as octet-stream (common on some Windows setups).
        if file_path.suffix.lower() in {".js", ".mjs"}:
            ctype = "application/javascript; charset=utf-8"
        elif file_path.suffix.lower() == ".css":
            ctype = "text/css; charset=utf-8"
        elif file_path.suffix.lower() == ".html":
            ctype = "text/html; charset=utf-8"
        return self._send(200, file_path.read_bytes(), ctype)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if not path.startswith("/api/"):
            return self._static(path)
        if path != "/api/health" and not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if dispatch_get(self, path, query):
            return
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/") and not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        body = self._body()
        if dispatch_post(self, path, body):
            return
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/api/") and not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        body = self._body()
        if dispatch_put(self, path, query, body):
            return
        return self._send(404, {"error": "not found"})


def serve(
    config_path: Path | None = None,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
) -> None:
    config_path = Path(config_path).resolve() if config_path else None
    root = project_root(config_path=config_path)
    config_path = config_path or (root / "config" / "agents.json")
    if not config_path.is_file():
        raise SystemExit(
            f"Config not found: {config_path}\n"
            "Run from the agent-dashboard folder via start.py / start.bat, "
            "or pass --config path\\to\\config\\agents.json "
            "(or set AGENT_DASHBOARD_ROOT)."
        )
    config = load_config(config_path)
    data_dir = resolve_data_dir(config.get("data_dir"), project=root)
    registry = Registry(config, config_path.parent, data_dir)
    docs_path = docs_dir(config_dir=config_path.parent, project=root)
    host = host or config.get("host", "127.0.0.1")
    port = int(port or config.get("port", 8866))
    auth_required = bool(config.get("auth_required", False))
    token = (
        (token or "").strip()
        or (os.environ.get("AGENT_DASHBOARD_TOKEN") or "").strip()
        or _secrets.token_urlsafe(24)
    )

    if host not in {"127.0.0.1", "localhost", "::1"} and not auth_required:
        raise SystemExit(
            f"Refusing to bind {host} without auth. "
            "Set auth_required: true in config, or bind to 127.0.0.1 / localhost / ::1."
        )

    profiles_path = root / "config" / "terminal_profiles.json"
    if not profiles_path.is_file():
        profiles_path = config_path.parent / "terminal_profiles.json"
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.ctx = {
        "registry": registry,
        "auth_required": auth_required,
        "token": token,
        "config": config,
        "project_root": root,
        "docs_dir": docs_path,
        "usage_store": UsageStore(data_dir / "usage.jsonl"),
        "home_snapshot": SnapshotCache(ttl_seconds=5.0),
        "workshop_snapshot": WorkshopSnapshotCache(ttl_seconds=5.0),
        "terminal_registry": TerminalRegistry(data_dir, profiles_path),
    }
    try:
        config_display = str(config_path.relative_to(root))
    except ValueError:
        config_display = str(config_path)
    doc_files = sorted(docs_path.glob("*.md")) if docs_path.is_dir() else []
    if not doc_files:
        print(
            f"WARNING: no docs found under {docs_path} — "
            "Documentation tab will be empty. Use start.py from the agent-dashboard checkout.",
            flush=True,
        )
    print(json.dumps({
        "listening": f"http://{host}:{port}",
        "auth_required": auth_required,
        "api_token": token if auth_required else None,
        "agents": list(registry.adapters),
        "config": config_display,
        "project_root": str(root),
        "docs_dir": str(docs_path),
        "docs_count": len(doc_files),
        "web_root": str(WEB_ROOT),
        "data_dir": "outside-project (tokens are memory-only)",
    }, indent=2))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    finally:
        for adapter in registry.adapters.values():
            if hasattr(adapter, "clear_secrets"):
                adapter.clear_secrets()
