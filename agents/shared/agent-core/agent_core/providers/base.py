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
    deadline: float | None = None
    credential_ref: str | None = None
    catalog_id: str | None = None
    policy_id: str | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)
    max_transport_retries: int = 0

    def __post_init__(self):
        import math
        if self.max_transport_retries not in (0, 1, 2):
            raise ValueError("transport retries must be 0..2")
        if self.deadline is not None and not math.isfinite(self.deadline):
            raise ValueError("deadline must be finite")


@dataclass
class ToolCall:
    """Tool invocation requested by a model."""
    name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class TokenUsage:
    """Token usage and accounting details."""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    evidence_status: str = "unknown"
    cache_creation_tokens: int | None = None

    def __post_init__(self):
        import math
        if self.evidence_status not in {"unknown","estimated","reported","reconciled"}:
            raise ValueError("invalid usage evidence")
        for count in (self.input_tokens,self.output_tokens,self.total_tokens,self.cached_tokens,self.reasoning_tokens,self.cache_creation_tokens):
            if count is not None and (not isinstance(count,int) or isinstance(count,bool) or count<0):
                raise ValueError("invalid token count")
        if self.cost_usd is not None and (not math.isfinite(self.cost_usd) or self.cost_usd<0):
            raise ValueError("invalid reported cost")
        if self.total_tokens is None and self.input_tokens is not None and self.output_tokens is not None:
            self.total_tokens=self.input_tokens+self.output_tokens

    @classmethod
    def from_counts(
        cls,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_per_1k: float | None = None,
    ) -> TokenUsage:
        total = prompt_tokens + completion_tokens
        cost = (total / 1000.0) * cost_per_1k if cost_per_1k is not None else None
        return cls(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
            evidence_status="estimated" if cost is not None else "reported",
        )


@dataclass
class InvocationResult:
    """Result returned by a provider invocation."""
    output: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str = "unknown"
    raw_ref: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_text: str | None = None
    usage: TokenUsage | None = None

    provider_request_id: str | None = None
    finish_reason: str | None = None
    cancellation_status: str = "unsupported"

    def __post_init__(self) -> None:
        if self.usage is None and (self.input_tokens is not None or self.output_tokens is not None):
            self.usage=TokenUsage(input_tokens=self.input_tokens,output_tokens=self.output_tokens,evidence_status="reported")
        elif self.usage is not None:
            if self.input_tokens is None: self.input_tokens=self.usage.input_tokens
            if self.output_tokens is None: self.output_tokens=self.usage.output_tokens


@dataclass(frozen=True)
class ProviderCapabilities:
    tools: bool = False
    json_schema: bool = False
    streaming: bool = False
    cancellation: bool = False

@dataclass(frozen=True)
class StreamEvent:
    type: str
    text: str | None = None
    tool_call: ToolCall | None = None
    usage: TokenUsage | None = None
    provider_request_id: str | None = None
    finish_reason: str | None = None

class Provider(ABC):
    """Abstract base provider for LLM and agent invocations."""
    name: str = "provider"
    capabilities = ProviderCapabilities()

    def cancel(self, request_id: str) -> str:
        return "unsupported"

    @abstractmethod
    def invoke(self, request: Invocation) -> InvocationResult:
        """Execute request and return InvocationResult."""
        ...
