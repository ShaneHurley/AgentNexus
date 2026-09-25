"""Structured error types for Research Forge."""

from __future__ import annotations

from enum import Enum
from typing import Any, NoReturn

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    BLOCKED = "BLOCKED"
    PLAN_STALE = "PLAN_STALE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    POLICY_DENIED = "POLICY_DENIED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NOT_FOUND = "NOT_FOUND"


class ForgeError(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def forge_error(code: ErrorCode, message: str, **details: Any) -> ForgeError:
    return ForgeError(code=code, message=message, details=details)


class ForgeException(Exception):
    """Raised when host code must fail closed."""

    def __init__(self, error: ForgeError) -> None:
        self.error = error
        super().__init__(error.message)


def raise_forge(code: ErrorCode, message: str, **details: Any) -> NoReturn:
    raise ForgeException(forge_error(code, message, **details))
