"""Shared HTTP helpers for route modules."""
from __future__ import annotations

import json
import secrets
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def limit(query: dict, default: int = 50) -> int:
    try:
        return max(1, min(500, int(query.get("limit", [str(default)])[0])))
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer") from None


def resume_http_status(result: dict[str, Any]) -> int:
    """Map adapter resume payload to HTTP status (fail-closed — never 202 with accepted False)."""
    if result.get("accepted"):
        return 202
    err = result.get("error")
    code = err.get("code") if isinstance(err, dict) else None
    if code == "NOT_FOUND":
        return 404
    if code == "POLICY_DENIED":
        return 403
    return 502


def ctx(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    return handler.server.ctx  # type: ignore[attr-defined]


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    c = ctx(handler)
    if not c["auth_required"]:
        return True
    header = handler.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else handler.headers.get("X-Api-Token", "")
    return secrets.compare_digest(token or "", c["token"])


def send(handler: BaseHTTPRequestHandler, code: int, payload: Any, content_type: str = "application/json"):
    if isinstance(payload, bytes):
        body = payload
    elif content_type.startswith("text/") or content_type.endswith("javascript"):
        body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
    else:
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'",
    )
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if not length:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except ValueError:
        return {}
