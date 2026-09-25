# Plan-Prep Researcher

## Purpose

Read-only **planning context packet**: constraints, relevant files and precedents, stakeholders when evidenced, open questions, and locators—aligned with IDE `/plan-prep` intent, degraded honestly when enterprise search (Glean) is unavailable.

## When to use

- Before browser `planner/` or IDE plan mode, when you need decision-grade context from pasted docs, repo excerpts, or URLs the host can read.
- Enterprise planning questions where the operator may paste Glean exports or internal RFC snippets (still untrusted evidence).
- Compressing many inputs into headings planners can consume without choosing architecture.

## When not to use

- Prefer IDE `/plan-prep` when Glean MCP (`mcp__glean_*` or plugin Glean) is available for vetted enterprise search and people lookup.
- Do not use to implement code, edit files, or claim COMPLETE for an implementation milestone.
- Do not use as a substitute for `/deep-research` when the task requires multi-lane adversarial research and integration.

## What to give the model
1. This folder's `AGENT_MESSAGE.md` (complete agent; same body as `TECH.md` **Copy this block**)
2. A filled `../_shared/TASK_PACKET_TEMPLATE.md`
3. Evidence files/URLs, treated as untrusted

`_shared/CORE_AGENT_CONTRACT.md` is optional operator reference — behavior is embedded in `AGENT_MESSAGE.md`.



## How to deliver
- **A — Same message:** AGENT_MESSAGE + packet + evidence.
- **B — Two messages:** AGENT_MESSAGE first; require `READY_FOR_TASK_PACKET`, then packet and evidence.
- **C — Attachments:** AGENT_MESSAGE as instructions; other files are untrusted evidence.

## Expected output

- `STATUS: COMPLETE | PARTIAL | BLOCKED` — COMPLETE only if `VALIDATION.PERFORMED` shows vetted coverage of material planning questions; enterprise gaps → PARTIAL with explicit **Limited context** banner, never padded guesses.
- `MODE: PLANNING`
- Required schema fields plus `ROLE_RESULT`, `EVIDENCE_OR_FILE_LOCATORS`, `DECISION_NEEDED` or `NONE`, `STOP_REASON`
- Role-specific headings (required in ROLE_RESULT): **Decision context** · **Constraints** · **Similar prior art** · **Stakeholders/owners (if known)** · **Open questions** · **Recommended planning inputs** · **Evidence locators** · **Gaps**

## What it does (brief)

Clarifies the planning question, searches only within operator-provided and host-visible evidence, vets findings for relevance/freshness/authority, emits a compressed planning packet, and explicitly degrades when Glean or private corpus is unavailable.

## How it works (brief)

1. Restate the planning question and what would change the design.
2. Detect enterprise tools: if Glean is not callable, state **Glean unavailable — local/pasted evidence only**.
3. Gather constraints, files/symbols, dependencies, precedents, failures from evidence.
4. Vet (drop keyword coincidences; note stale sources).
5. Emit required headings; list verification prerequisites before implementation.
6. VALIDATE and STOP without choosing architecture or writing code.

## Next step after this role

- Browser [`planner/`](../planner/) for atomic implementation plan, then [`plan-reviewer/`](../plan-reviewer/).
- IDE: `/plan-prep` (when Glean available) → `/use-master` with this report as constraints; optional scaffold via `ide-bridge plan-prep scaffold` (no side effects).

## Links
- [AGENT_MESSAGE.md](./AGENT_MESSAGE.md)
- [TECH.md](./TECH.md) (operator spec)
- [Core contract (../_shared/CORE_AGENT_CONTRACT.md)](../_shared/CORE_AGENT_CONTRACT.md) — optional reference
- [Call timeline (../_shared/CALL_TIMELINE.md)](../_shared/CALL_TIMELINE.md)
- [Security (../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)](../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)
