# Daily Coder — Technical reference

Authoritative description of the **implemented** runtime after workflow version `2.1`. Prefer this document over aspirational notes in older cost plans when they disagree.

## Pipeline

```text
CLI / REST
  → Orchestrator.run
      → size_request → sizing artifact {profile, trivial_signal, workflow}
      → phases_for(workflow)
      → per phase: _run_phase → _invoke (budget reserve → provider → settle → schema)
      → gates / repair / acceptance
```

| Workflow key | When | Skips |
|--------------|------|-------|
| `S` | Profile S, no trivial keywords | RESEARCH, BRAINSTORM, TEST_DESIGN |
| `S_TRIVIAL` | Profile S **and** `trivial_signal` | Also TEST_AUTHOR, DOCUMENT |
| `M` / `L` / `XL` | By score | See `workflow.py` |

**Profile vs workflow:** Budget caps and `boundary_alignment` still key off **profile** (`S`). Only the phase list uses `S_TRIVIAL`. Resume and repair reload `sizing.workflow` from the artifact store so mid-run code updates cannot re-derive a different route.

**Acceptance:** `require_alignment_pass` remains true by default, so `S_TRIVIAL` **keeps** the `ALIGNMENT` phase. State machine allows `IMPLEMENT→TEST_EXECUTE` and `CODE_REVIEW→ALIGNMENT` for that skip path (`state_machine.py`).

Mock benchmark (post-2.1): trivial scenario ≈ **7** role calls (was ~9).

## Context projection

`context.build_packet(role, packet)` sends only `PINNED` + `ROLE_INPUTS[role]`. `_rebuild_packet` lifts digests so those keys exist:

| Packet key | Built from |
|------------|------------|
| `plan_summary` | plan allowlist, unit counts/ids, unresolved questions, verification count |
| `implement_summary` | changed files, command/observation counts, blocked (no observation prose) |
| `diff_summary` | optional diff artifact file list |
| `verification_commands` | `plan.verification_commands` |
| `plan_slice` | `plan.change_units` (implementer chunk override still wins via `_role_extra`) |
| `research_digest` | compacted research cards (unwraps `{lane, angle, card}` wrappers and legacy flat cards) |
| `repo_map` | live only: one audited `filesystem.list` before research fan-out; omitted on deny/error/non-live |

Digests are truncated at `DIGEST_CHARS` (2000).

## Invocation loop

1. Slice packet; advertise tools only when `live` and a gateway exists.
2. `budget.reserve` → `provider.invoke` → `budget.settle`.
3. Tool turns append results with `"turn": turn` for provider replay.
4. Final output: `SchemaRegistry.validate`. On `SchemaError` / empty output, retry up to `agent.json` `max_retries` with a new idempotency key (`…:retryN`). Transport errors and tool-limit errors are not retried here.
5. Role gates (`_gate`) may return `("repair", reason)`.

## Repair and frontier

With `max_repair_cycles = 2`:

| `cycles` after bump | Behavior |
|---------------------|----------|
| 1 | Diagnose → rewind → retry (no frontier) |
| 2 | Diagnose → **frontier if live + authorized** → rewind → retry (`frontier_advice` available to master) |
| 3+ | Diagnose → **halt; no frontier** |

Frontier never runs then immediately halts. Profile `S` has `frontier_calls: 0`, so frontier stays off for small work.

## Research fan-out

`_research` runs lanes in batches of `max_parallel_agents`. Each stored entry is `{lane, angle, card}` where `card` is the schema-validated `research_card` (metadata is never merged into the card because `additionalProperties: false`).

After each batch, `should_stop_research(cards, min_cards=…)` stops further batches only when:

- at least `min_cards` exist (profile field `early_stop_min_cards` in `config/budgets.json`, default **2**; explicit on **M**)
- every unwrapped body has an explicit `unknowns` key that is empty
- no observation has `label == "UNKNOWN"`

Mock researchers always report unknowns, so early-stop is inert under mock. Live `repo_map` is injected once before the first lane. Shared `WebClient` call budget is thread-safe under parallel lanes.

## Providers

| Provider | Notes |
|----------|--------|
| `mock` | Contract exercise only; runs end `SIMULATED` |
| `openai` / `openrouter` | Native `role=tool` messages when `call_id` present; `response_format=json_object` when no tools; compact schema field list in system prompt; falls back to `TOOL_RESULT` user text if `call_id` missing; retries once without `response_format` if the server rejects it |
| `local` | Same adapter with `supports_json_response_format=False` |
| `anthropic` / `gemini` | Unchanged this pass (full schema instruction + user tool results) |

## Adversarial findings (status)

| ID | Finding | Status |
|----|---------|--------|
| F1 | Role inputs never built | **Fixed** — digests in `_rebuild_packet` |
| F2 | Frontier spent then unused on halt | **Fixed** — last-chance before retry only |
| F3 | `max_retries` unused | **Fixed** — schema retries in `_invoke` |
| F4 | Trivial paid full S tail | **Fixed** — `S_TRIVIAL` (keeps ALIGNMENT) |
| F5 | OpenAI tools/JSON fragile | **Fixed** for OpenAI-compatible path |
| F6 | Research always full lane count / early-stop gaming | **Fixed** — batched early-stop; requires explicit empty `unknowns` and no `UNKNOWN` labels; lane wrappers + live `repo_map` |
| F7 | Mock dead return; sizing dropped `trivial_signal` | **Fixed** |

### Deferred

- Phase-level token envelopes
- Prompt caching APIs
- Wiring `reasoning` flags from `models.json`
- Making budget warn/checkpoint levels halt (today they are mostly telemetry; hard stop is the 90% reserve fraction)
- Anthropic/Gemini native tool/JSON parity

## Key files

| Concern | Path |
|---------|------|
| Orchestration | `daily_coder/orchestrator.py` |
| Workflows | `daily_coder/workflow.py` |
| Sizing / phases | `daily_coder/router.py` |
| Transitions | `daily_coder/state_machine.py` |
| Context | `daily_coder/context.py` |
| Budget | `daily_coder/budget.py` |
| Acceptance | `daily_coder/acceptance.py` |
| OpenAI adapter | `daily_coder/providers/openai_compat.py` |
