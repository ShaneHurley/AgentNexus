# What Must Be Added — and How Credits Stay Safe

**Status:** Waves 0–2 implemented; retained as the acceptance checklist and historical build plan.  
**Target package:** this repo (`daily-coder-ecosystem`).  
**Authority:** user build intent + `agent_orchestration_master_spec.md` Part D.

This document answers two questions:

1. Exactly what is missing before the orchestration is a real daily coding assistant.
2. How the system must spend time and money so a normal day of use does **not** burn credits.

---

## Current honest state

| Layer | Status today |
|---|---|
| Agent folders (15 roles) | Present: `agent.json`, `model.json`, `prompt.md` |
| Skills (10) | Opt-in, plan-selected, version-pinned loader; no blanket injection |
| Orchestrator phase loop | Versioned S/M/L/XL workflows; mock runs are explicitly `SIMULATED` |
| Tool broker / policies | `PolicyGateway` authorizes, executes, redacts, and audits role calls |
| Frontier escalation | Wired after bounded lower-tier repair failure; maximum one call by profile |
| Sizer agent | Deterministic first; cheap role is called only when routing is ambiguous |
| Skill curator / frontier advisor | Triggered roles; skill promotion remains human-gated |
| Real repo edits / tests | Typed local tools, allowlisted writes, compare-and-swap, durable test jobs |
| Token budgets in config | Atomic per-call reservations, thresholds, daily token/USD limits, cost ledger |

**Bottom line:** local CLI and single-host REST/dashboard paths are implemented. Multi-host workers and high-risk business integrations remain intentionally disabled and fail closed.

---

## Cost doctrine (non-negotiable)

Spend only where it changes the outcome. Everything else is cheapest-tier or skipped.

```text
WHERE TO SPEND
  Master judgment on compressed packets
  Exact planning (so implementers stay cheap)
  Adversarial plan review (catches expensive mistakes early)
  One frontier call, only after a logged lower-tier failure, on a short brief

WHERE NOT TO SPEND
  Full fan-out on one-line / unambiguous fixes
  Extended reasoning on read / extract / format / transcribe jobs
  Re-reading the same files across agents
  Forwarding raw transcripts between tiers
  Frontier models for search, summarize, implement, test run, docs
  Brainstorm padding when nothing better exists
  Skills that add tokens without measured gain
```

### Hard money rules the runtime must enforce

1. **Sizing gate first.** Classify `TRIVIAL | CONTAINED | CROSS_CUTTING` (map to S/M/L/XL). Trivial skips research + brainstorm + frontier.
2. **Profile caps are hard stops**, not hints. Current declared caps:

| Profile | Max tokens | Max calls | Research lanes | Frontier |
|---|---:|---:|---:|---:|
| S | 40_000 | 12 | 1 | 0 |
| M | 80_000 | 24 | 3 | 1 |
| L | 140_000 | 40 | 5 | 1 |
| XL | 220_000 | 50 | 6 | 1 |

3. **Warn at 70%, checkpoint at 80%, hard stop at 90%** of usable budget (config already names these; code must use them). Keep 10% reserve.
4. **Per-call `max_output_tokens` from `agent.json` is enforced** by the provider wrapper, not trusted to the model.
5. **Budget check before every provider call**, including each research lane (today: one check per phase → parallel lanes can burst past the cap).
6. **Frontier:** at most one call per run, only via `authorize_frontier()`, only with a compressed decision brief — never the weak-model transcript.
7. **Reasoning off by default** for lowest-tier roles (recon, implementer, documenter, alignment, sizer).
8. **Context packet shrinks**, not grows: each role gets only its required slice + task anchor + plan allowlist. Compaction is type-aware (rules/permissions pinned).
9. **Daily / session spend ceiling** (new): a user-settable `max_spend_usd` and `max_tokens_per_day` in config; orchestrator refuses new runs when exceeded.
10. **Dry-run / mock is the default** until a human opts into a live provider with an explicit flag (`--live` or `provider != mock`).

---

## What to add — ordered by build priority

### Wave 0 — Stop the bleed (do this before any live LLM)

Without Wave 0, plugging in a real model will run the full DAG and charge for every phase.

| # | Add | Why it saves money | Files / touch points |
|---|---|---|---|
| 0.1 | **Live-spend guard** | Refuse live provider unless `--live` + budget profile chosen | `cli.py`, `config/default.json` |
| 0.2 | **Enforce warn / checkpoint / hard_stop fractions** | Soft warn then stop before 100% burn | `budget.py`, `orchestrator.py` |
| 0.3 | **Per-call budget check** (including each research lane) | Stops parallel burst overspend | `orchestrator.py` |
| 0.4 | **Trivial short-circuit path** | One-line fixes skip RESEARCH/BRAINSTORM/frontier | `router.py` `phases_for` |
| 0.5 | **Load `models.json` + map tiers → concrete models** | Cheap roles stay on cheap models | `orchestrator.py`, `agents/*/model.json` |
| 0.6 | **Context slicer** | Do not forward whole accumulating packet | new `daily_coder/context.py` |
| 0.7 | **Cost ledger fields** | `tokens`, `est_usd`, `cost_per_verified_pass` per run | `state_store.py`, CLI status |
| 0.8 | **Artifact path fix** | Artifacts under `root/.daily-coder/`, not CWD | `orchestrator.py` / `artifacts.py` |

**Exit criterion:** `daily-coder run --provider mock` still works; attempting live without `--live` fails closed; S-profile path has fewer phases.

---

### Wave 1 — Wire enforcement that already exists on paper

| # | Add | What it does | Cost impact |
|---|---|---|---|
| 1.1 | **PolicyGateway wraps every tool call** | Broker + policies actually gate side effects | Prevents runaway writes (expensive repairs) |
| 1.2 | **Reference LocalToolAdapter** for enabled tools only | `filesystem.*`, `repository.*`, `shell.*`, `tests.run` | Real work without paying for “explore forever” |
| 1.3 | **Leave MCP/web/company tools disabled** | Fail closed until adapters exist | Avoids open-ended search spend |
| 1.4 | **Real ACCEPTANCE gate** | Checks plan review + tests + code review + alignment artifacts | Stops fake “COMPLETE” on empty mocks when live |
| 1.5 | **Wire frontier_advisor** via `escalation.py` | Only on qualifying triggers; count against `frontier_calls` | One expensive call max, logged |
| 1.6 | **Invoke sizer agent (or hybrid)** | Heuristic first; LLM sizer only if ambiguous | Cheap gate, not a ceremony |
| 1.7 | **Per-boundary alignment (cheap)** | After RESEARCH, PLAN, IMPLEMENT — not only at end | Cheap catch of drift before more spend |
| 1.8 | **PLAN_STALE / repair loop** | Cap with `max_repair_cycles: 2` | Bounded retries, not infinite loops |

**Exit criterion:** ToolBroker is on the live path; frontier cannot fire without authorization; acceptance is not hardcoded `pass` for live runs.

---

### Wave 2 — Complete the agent surface (still token-frugal)

| # | Add | Detail |
|---|---|---|
| 2.1 | **Research lane angles** | Configured non-overlapping angles (implementation, callers, tests, docs, config, user-named). Each lane gets its own tiny packet. |
| 2.2 | **Research cards: evidence only** | Remove / quarantine `recommended_followup` from external schema; require claim tags + locators. |
| 2.3 | **Tighten `change_plan` schema** | Exact file, region, before/after, allowlist, TEST line, verify command, rollback, budget — zero design wiggle room. |
| 2.4 | **failure_diagnostician role + phase** | On gate fail → diagnose → master decides repair or stop. No blind re-run of whole pipeline. |
| 2.5 | **skill_curator post-run only** | Propose skills; never auto-merge; never load into hot path by default. |
| 2.6 | **Brainstorm fabrication check** | Cheap check before master appraises; `NO BETTER ALTERNATIVE FOUND` is success. |
| 2.7 | **Skills runtime loader (opt-in)** | Load only skills named in the plan; progressive disclosure; skip if unused. |
| 2.8 | **Complete specialist folder contract** | Per agent: `tools` already in `agent.json`; add `budget.yaml` slice, `output.schema` link, optional `tests/` fixtures. |
| 2.9 | **E2E tests** | Mock full run; budget burst; frontier deny; trivial short-circuit; broker deny write outside allowlist. |

**Exit criterion:** All 15 agents are either on the DAG with a defined trigger or explicitly documented as off-by-default (skill_curator).

---

### Wave 3 — Defer until Wave 0–2 prove cost control

Do **not** build these first; they burn design time and can increase spend:

- Company / email / calendar / external-write adapters
- Autonomous skill self-improvement
- Unbounded multi-agent debate loops
- Always-on large AGENTS.md / repo dumps in every prompt
- Frontier-by-default or “use strongest model for everything”
- Quality-diversity ideation portfolio systems
- Full claim-to-evidence graph UI (ledger fields first is enough)

---

## Exact roster: what each agent should cost

| Agent | Tier | When it runs | Typical spend | Must not do |
|---|---|---|---|---|
| Sizer | Lowest | Always (or heuristic) | Tiny | Design decisions |
| Researcher × N | Lowest | M/L/XL only; N from profile | High count, tiny each | Recommend / plan / write |
| Master | Mid–high | Always (compressed input) | Moderate | Side effects; raw dumps |
| Frontier advisor | Frontier | ≤1, authorized only | Rare, brief only | Search / implement / review routine |
| Brainstormer | Mid | Skip on S; one pass | Bounded | Pad weak ideas |
| Planner | Mid | After decide | Moderate | Leave open design choices |
| Plan reviewer | Mid | Before any write | Small | Silent “fixes” |
| Implementer × N | Lowest | Exact tasks only | High count, tiny each | Redesign / expand scope |
| Test designer / author | Mid | Non-trivial only | Moderate | Self-bless tests |
| Test executor | Low–mid | After tests exist | Small | Interpret away failures |
| Code reviewer | Mid–high | Before accept | Moderate | Grade own code |
| Documenter | Lowest | End | Minimal | Rewrite unreviewed docs |
| Alignment | Lowest | Phase boundaries | Minimal | Approve off-task work |
| Skill curator | Lowest | After success, optional | Minimal | Auto-promote skills |
| Failure diagnostician | Mid | On failure only | Moderate | Restart whole run blindly |

---

## Pipeline with cost annotations

```text
Request
  │
  ▼
[Sizer / heuristic] ── TRIVIAL ──► compact path:
  │                                 inspect → plan-lite → implement → verify → review → done
  │                                 (no research fan-out, no brainstorm, frontier=0)
  │
  ├── CONTAINED (M) → few recon lanes → master → [optional brainstorm]
  └── CROSS_CUTTING (L/XL) → more lanes → master → brainstorm → …
        │
        ▼
  Plan (exact) → Plan review (adversarial)  ←── highest leverage token save
        │
        ▼
  Implement (cheap, allowlisted) → Test author → Test exec → Code review
        │
        ▼
  Alignment → Acceptance (real gate) → Document
        │
        └── on fail → Diagnostician → ≤2 repair cycles → STOP or escalate once
```

---

## File-level add / change checklist

### Must change (Wave 0–1)

- [`daily_coder/orchestrator.py`](../daily_coder/orchestrator.py) — slicer, per-call budget, frontier, acceptance, alignment boundaries, ToolBroker path
- [`daily_coder/budget.py`](../daily_coder/budget.py) — warn / checkpoint / hard stop; frontier_calls; daily cap
- [`daily_coder/router.py`](../daily_coder/router.py) — trivial phase list; risk fields
- [`daily_coder/cli.py`](../daily_coder/cli.py) — `--live`, spend report, refuse over daily cap
- [`daily_coder/tool_broker.py`](../daily_coder/tool_broker.py) — phase-aware authorize
- **New** `daily_coder/context.py` — role packet builder
- **New** `daily_coder/acceptance.py` — real gate
- **New** `daily_coder/providers/local_tools.py` — filesystem/shell/tests via broker
- [`config/default.json`](../config/default.json) — `require_live_flag`, `max_tokens_per_day`, `max_spend_usd`
- [`config/budgets.json`](../config/budgets.json) — keep S low; optionally add `TRIVIAL` profile even tighter (e.g. 15k tokens / 6 calls)

### Must complete (Wave 2)

- [`schemas/change_plan.schema.json`](../schemas/change_plan.schema.json) — full exact-change fields
- Research / brainstorm schemas — claim tags, no free recommendations
- [`agents/sizer/`](../agents/sizer/), [`agents/frontier_advisor/`](../agents/frontier_advisor/) — actually invoked
- **New** `agents/failure_diagnostician/`
- [`skills/*/SKILL.md`](../skills/) — loader + allowlist injection only when planned
- [`tests/`](../tests/) — E2E orchestrator + budget + broker

### Explicitly do not add yet

- Adapters for the remaining disabled enterprise and external-write tools in `config/tools.json`
- Automatic skill or harness promotion without human approval
- Native adapters for additional vendors beyond OpenAI, Anthropic, Gemini, OpenRouter, and OpenAI-compatible endpoints

---

## Recommended first live usage profile

Until you trust the gates:

1. Always start with `--provider mock`.
2. First live runs: **profile S only**, one small repo, `--live`, with `max_spend_usd` set low (e.g. $1–2/day).
3. Confirm: trivial path skips fan-out; implementer cannot write outside allowlist; frontier stays at 0.
4. Only then try profile M on a real bugfix.
5. Never point XL at an open-ended “explore the whole codebase” request without a written acceptance criterion.

---

## Definition of “complete enough to use daily”

The orchestration is ready for daily use when:

- Trivial work cannot accidentally pay for a full fan-out.
- Live runs require an explicit opt-in and respect daily spend caps.
- Cheap models do volume; frontier is 0 or 1 compressed call.
- Tool writes go through the broker with plan allowlists.
- Acceptance requires independent review + test evidence (live path).
- A failed run stops or diagnoses; it does not silently re-burn the budget.
- Swapping a model is still one `model.json` edit.

These conditions now hold for the supported local CLI and single-host service paths. Multi-host workers and disabled enterprise integrations remain extension boundaries, not supported execution paths.
