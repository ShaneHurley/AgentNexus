"""Unified shapes the UI and adapters share.

Adapters map agent-specific payloads into these dicts. Keep fields stable so the
front end can stay dumb and replaceable.
"""
from __future__ import annotations
from typing import Any, TypedDict


class AgentInfo(TypedDict, total=False):
    id: str
    name: str
    description: str
    enabled: bool
    online: bool
    capabilities: list[str]
    detail: str


class UnifiedRun(TypedDict, total=False):
    run_id: str
    agent_id: str
    status: str
    phase: str
    request: str
    updated_at: str
    est_usd: float
    profile: str
    raw: dict[str, Any]


class ApprovalItem(TypedDict, total=False):
    run_id: str
    agent_id: str
    kind: str
    summary: str


class ActivityItem(TypedDict, total=False):
    ts: str
    agent_id: str
    run_id: str
    role: str
    kind: str
    summary: str


class ThreadMessage(TypedDict, total=False):
    id: str
    agent_id: str
    run_id: str
    role: str  # user | agent | system
    text: str
    status: str  # queued | delivered | applied | rejected
    created_at: str
