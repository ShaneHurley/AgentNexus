# Operations

## Run lifecycle
Use `daily-coder status RUN_ID` to inspect authoritative state. `resume` continues only from the last committed phase. Duplicate phase delivery is ignored through idempotency keys.

Live runs require `--live`. A reviewed plan transitions to `WAITING_HUMAN`; use `daily-coder approve RUN_ID` and then `resume`. Long tests transition to `WAITING_JOB`; `resume` is non-spending while the job is active. Inspect them with `daily-coder jobs`.

Use `daily-coder spend` for daily usage or `daily-coder spend --run-id RUN_ID` for one run. Per-call reservation under the 90% usable ceiling, daily token/USD limits, call caps, and frontier call caps are runtime-enforced. Threshold labels (warn / checkpoint) are recorded for operators; they do not by themselves abort a run.

Resume always continues from the last committed phase using the **stored** `sizing.workflow` key — it does not re-size the request text. Repair rewinds within that same workflow.

The drift watchdog re-injects the task anchor after ten active minutes and stops identical repeated tool calls. It does not wake a model while a durable job is waiting. L/XL plans are chunked by the `decomposition` limits in `config/default.json`.

Start the optional local service with `daily-coder serve`. It prints a bearer token and dashboard URL. Bind beyond loopback only behind TLS and an authenticated reverse proxy.

## Orchestration benchmark (mock)

The harness runs four fixed scenarios through `MockProvider` (no credits): trivial → S, contained → M, cross-cutting → L, high-risk → XL. See `daily_coder/benchmark.py` for request text and expectations.

**Pinned baseline:** [`baselines/orchestration-v1.json`](../baselines/orchestration-v1.json) — commit updates only when routing, workflow, or config changes are intentional; include rationale in the PR.

### Before / after a harness change

From `daily-coder-ecosystem/` (after `pip install -e .`):

```bash
# Optional: refresh the pin (only when deliberately repinning)
daily-coder benchmark --output baselines/orchestration-v1.json

# Compare a candidate tree against the pin
daily-coder benchmark --baseline baselines/orchestration-v1.json
```

Use `--repeats N` for multiple passes per scenario (summary aggregates all records). JSON on stdout includes per-run `records`, aggregate `summary`, and when `--baseline` is set a `comparison` block with `before` / `after` / `percent` for median and p90 **calls**, **tokens**, and **latency**, plus `success_regression` when `summary.successful` drops.

### Operator review (today)

Reject or rework changes when any of the following hold:

| Signal | Meaning |
|--------|---------|
| `verified_routes` below 4 | Profile routing no longer matches S/M/L/XL expectations |
| `successful` below 4 | Runs did not finish with status `SIMULATED` under mock |
| `comparison.success_regression` is true | Fewer successful runs than the baseline file |
| Large **calls** or **tokens** median/p90 increase | Orchestration fan-out or context cost regressed (latency alone is noisy on shared runners) |

Expect the **trivial** scenario (`Fix typo`) to use the `S_TRIVIAL` workflow (~**7** mock role calls) while still reporting profile `S`. Non-trivial S requests keep the full S tail including test_author and documenter.

The baseline file also records `config_hash` over `config/default.json`, `config/budgets.json`, and `config/models.json`; a hash mismatch means comparisons span different configuration — repin or align config before trusting deltas.

### CI compare (gate)

Daily Coder CI runs:

```bash
daily-coder benchmark --baseline baselines/orchestration-v1.json --gate
```

**Fail** (exit code 1) when `verified_routes` or `successful` drop below 4, when `comparison.success_regression` is true, or when **median_calls**, **p90_calls**, **median_tokens**, or **p90_tokens** rise more than **10%** without an updated baseline and documented rationale. Latency percent deltas remain advisory until CI uses stable hardware.

Reviewers can run the same command locally before merging harness changes.

## Failures
- Malformed / schema-invalid model output: up to `max_retries` from `agent.json` inside the invocation, then repair.
- Provider timeout/rate limit: provider-local bounded backoff; failure is recorded as an invocation event.
- Permission denial: stop; never auto-widen permissions.
- Test/review failure: diagnose → on the last allowed repair cycle optionally call frontier (live, authorized) → rewind and retry; when cycles are exhausted, halt **without** another frontier call.
- Budget exhaustion: record the stop and fail closed; increasing a limit requires explicit operator action.
- Background test: inspect the durable log and duration estimate; cancel by job ID if required.

## Skill maintenance
Review active skills periodically for overlap, staleness, and negative transfer. Promote only candidates that pass pinned execution checks and human approval. Keep rollback history.

See also [`TECHNICAL.md`](TECHNICAL.md).
