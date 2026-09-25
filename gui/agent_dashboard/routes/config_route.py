"""Config overlay API — data_dir only."""
from __future__ import annotations

from ..config_overlay import load_overlay, validate_overlay_payload, write_overlay
from . import common as c


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path != "/api/config/overlay":
        return False
    ctx = c.ctx(handler)
    overlay = load_overlay(ctx["registry"].data_dir)
    c.send(handler, 200, {
        "overlay": overlay,
        "restart_required": bool(overlay),
        "path": "data_dir/config_overlay.json",
    })
    return True


def handle_post(handler, path: str, body: dict, parts: list[str]) -> bool:
    if path != "/api/config/overlay":
        return False
    ctx = c.ctx(handler)
    try:
        clean, unknown = validate_overlay_payload(body if isinstance(body, dict) else {})
    except ValueError as exc:
        c.send(handler, 400, {"error": str(exc)})
        return True
    if unknown:
        c.send(handler, 400, {"error": f"unknown keys: {', '.join(sorted(unknown))}"})
        return True
    write_overlay(ctx["registry"].data_dir, clean)
    c.send(handler, 200, {
        "ok": True,
        "overlay": clean,
        "restart_required": True,
        "message": "Restart the dashboard for overlay changes to take full effect.",
    })
    return True
