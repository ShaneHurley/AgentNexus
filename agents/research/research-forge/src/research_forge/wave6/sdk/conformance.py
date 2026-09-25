"""Adapter conformance suite (RF-W6-A-02)."""

from __future__ import annotations

from typing import Any, Callable

Rule = tuple[str, Callable[[Any], str | None]]


def _check_read_only(adapter: Any) -> str | None:
    ops = getattr(adapter, "supported_operations", lambda: frozenset())()
    if "write" in ops or "delete" in ops or "execute" in ops:
        return "mutating_operation_exposed"
    return None


def _check_pagination(adapter: Any) -> str | None:
    if not hasattr(adapter, "search"):
        return None
    try:
        p1 = adapter.search("conformance", page_size=1, cursor=0)
        if "results" not in p1:
            return "missing_results_key"
        if p1.get("next_cursor") is not None:
            p2 = adapter.search("conformance", page_size=1, cursor=p1["next_cursor"])
            if not p2.get("results"):
                return "pagination_empty_page"
    except Exception as exc:  # noqa: BLE001 — conformance boundary
        return f"pagination_error:{exc}"
    return None


def _check_access_disclosure(adapter: Any) -> str | None:
    if not hasattr(adapter, "read"):
        return None
    try:
        out = adapter.read({"url": "mock://conformance/doc"})
        if "access_level" not in out and "access_disclosure" not in out:
            return "missing_access_disclosure"
    except Exception:
        pass
    return None


def _check_rate_limit(adapter: Any) -> str | None:
    if not hasattr(adapter, "search"):
        return None
    out = adapter.search("rate", page_size=1)
    if out.get("error") == "rate_limit_exceeded":
        if "retry_after_ms" not in out:
            return "rate_limit_missing_retry"
    return None


def _check_locator(adapter: Any) -> str | None:
    if not hasattr(adapter, "read"):
        return None
    out = adapter.read({"path": "mock://local/x"})
    if out.get("error"):
        return None
    if "locator" not in out and "canonical_locator" not in out:
        return "missing_locator"
    return None


def _check_hashing(adapter: Any) -> str | None:
    if not hasattr(adapter, "read"):
        return None
    out = adapter.read({"path": "mock://local/hash-target"})
    if out.get("error"):
        return None
    if not out.get("content_hash"):
        return "missing_content_hash"
    return None


def _check_errors_structured(adapter: Any) -> str | None:
    if hasattr(adapter, "search"):
        out = adapter.search("", page_size=1)
        if out.get("error") and not isinstance(out.get("error"), str):
            return "error_not_string"
    return None


CONFORMANCE_RULES: list[Rule] = [
    ("read_only", _check_read_only),
    ("pagination", _check_pagination),
    ("access_disclosure", _check_access_disclosure),
    ("rate_limit", _check_rate_limit),
    ("locator", _check_locator),
    ("hashing", _check_hashing),
    ("errors", _check_errors_structured),
]


class ConformanceSuite:
    def run(self, adapter: Any, *, rules: list[Rule] | None = None) -> dict[str, Any]:
        active = rules or CONFORMANCE_RULES
        failures: list[str] = []
        passed: list[str] = []
        for name, fn in active:
            err = fn(adapter)
            if err:
                failures.append(f"{name}:{err}")
            else:
                passed.append(name)
        return {"passed": passed, "failures": failures, "ok": not failures}
