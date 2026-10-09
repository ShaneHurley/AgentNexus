"""Provider base interfaces and models for agent-core."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Invocation:
    """Standardized invocation request sent to a provider."""
    run_id: str
    role: str
    prompt: str
    input_packet: dict[str, Any]
    model_tier: str
    max_output_tokens: int
    idempotency_key: str
    model: str = "unknown"
    tools: tuple = ()
    tool_results: tuple = ()
    turn: int = 0
    reasoning: bool = False
    output_schema: dict[str, Any] | None = None


@dataclass
class ToolCall:
    """Tool invocation requested by a model."""
    name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class TokenUsage:
    """Token usage and accounting details."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    @classmethod
    def from_counts(
        cls,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_per_1k: float = 0.0,
    ) -> TokenUsage:
        total = prompt_tokens + completion_tokens
        cost = (total / 1000.0) * cost_per_1k if cost_per_1k else 0.0
        return cls(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
        )


@dataclass
class InvocationResult:
    """Result returned by a provider invocation."""
    output: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "unknown"
    raw_ref: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_text: str | None = None
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        if self.usage is None and (self.input_tokens or self.output_tokens):
            self.usage = TokenUsage(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                total_tokens=self.input_tokens + self.output_tokens,
            )
        elif self.usage is not None:
            if not self.input_tokens and self.usage.input_tokens:
                self.input_tokens = self.usage.input_tokens
            if not self.output_tokens and self.usage.output_tokens:
                self.output_tokens = self.usage.output_tokens


class Provider(ABC):
    """Abstract base provider for LLM and agent invocations."""
    name: str = "provider"

    @abstractmethod
    def invoke(self, request: Invocation) -> InvocationResult:
        """Execute request and return InvocationResult."""
        ...
