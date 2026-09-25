"""Route dispatch for stdlib HTTP handler."""
from __future__ import annotations

import urllib.parse
from http.server import BaseHTTPRequestHandler

from . import agents, config_route, docs, home, meta, setup, terminal, usage_route, workspace


def _parts(path: str) -> list[str]:
    return [urllib.parse.unquote(p) for p in path.split("/") if p]


def dispatch_get(handler: BaseHTTPRequestHandler, path: str, query: dict) -> bool:
    parts = _parts(path)
    for mod in (
        meta,
        agents,
        setup,
        usage_route,
        home,
        docs,
        config_route,
        workspace,
        terminal,
    ):
        if mod.handle_get(handler, path, query, parts):
            return True
    return False


def dispatch_post(handler: BaseHTTPRequestHandler, path: str, body: dict) -> bool:
    parts = _parts(path)
    for mod in (agents, setup, config_route, terminal):
        if mod.handle_post(handler, path, body, parts):
            return True
    return False


def dispatch_put(handler: BaseHTTPRequestHandler, path: str, query: dict, body: dict) -> bool:
    parts = _parts(path)
    if workspace.handle_put(handler, path, query, body, parts):
        return True
    return False
