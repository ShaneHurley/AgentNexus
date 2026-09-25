# Provider Adapter Contract

Command and HTTP bridge providers use one contract. A request contains `run_id`, `role`, `prompt`, `input_packet`, `model_tier`, `model`, `max_output_tokens`, `idempotency_key`, `tools`, `tool_results`, `turn`, and `output_schema`.

The adapter returns:
```json
{"output": {}, "tool_calls": [], "input_tokens": 0, "output_tokens": 0, "model": "provider/model"}
```

Requirements:
- Fresh invocation per role attempt; no hidden cross-run state.
- Honor maximum output and return measured usage when available.
- Return only the role schema in `output`.
- To request tools, return `tool_calls` containing `name`, `arguments`, and optional `call_id`; omit `output`. The runtime executes calls through `PolicyGateway` and starts a fresh turn containing `tool_results`.
- Never silently substitute a model with weaker capabilities; report capability failure.
- Use idempotency keys for billable/retriable operations.

Direct adapters exist for OpenAI, Anthropic, Gemini, OpenRouter, and OpenAI-compatible local endpoints. External frameworks should use command or HTTP bridge contracts instead of replacing SQLite authority or the policy gateway. Run adapter conformance tests before declaring a provider supported.
