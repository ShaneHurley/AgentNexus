# Planner

## Purpose

Produce an **atomic, verifiable implementation plan** (tasks with paths, acceptance, validation, rollback, and dependencies) — **without implementing** or choosing unresolved architecture.

## When to use

- You have a bounded coding objective, task packet, and enough evidence (repo excerpts, plan-prep output, or doc-reader extracts) to name files and checks.
- You need a handoff plan for Daily Coder or human review before any audited writes.
- Browser hosts where drafting a plan is enough; execution will happen elsewhere.

## When not to use

- Prefer IDE **`/daily-coder`** with runtime `planner` when the host can read the repo via PolicyGateway and emit schema-valid `change_plan` JSON automatically.
- Do not use for open-ended research — use `deep-research/` or `plan-prep-researcher/` first.
- Do not use for adversarial plan falsification — use `plan-reviewer/` on a **frozen** plan packet.
- Do not use when material design choices remain; planner should stop with Q-ID or list items in `unresolved_questions`, not guess.

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

- **STATUS:** `COMPLETE` | `PARTIAL` | `BLOCKED` — `COMPLETE` only when every planned task has evidenced paths and observable validation steps listed under `VALIDATION.PERFORMED`; never from prose alone.
- **MODE:** `PLANNING`
- **Required fields:** contract schema plus `ROLE_RESULT`, `EVIDENCE_OR_FILE_LOCATORS`, `DECISION_NEEDED` or `NONE`, `STOP_REASON`
- **Role-specific:** ordered **plan tasks**, each with `id`, files/paths, acceptance criteria, validation, rollback, and deps (serial vs parallel-safe); explicit **do not implement** boundary; optional mapping note to DC `change_plan` shape when executing via bridge

## What it does (brief)

Turns an anchored objective into the smallest safe sequence of verifiable change units, separates parallel-safe from serialized work, surfaces discovery steps when paths are unknown, and stops before coding.

## How it works (brief)

1. OBSERVE supplied inputs and restate scope from the task packet.
2. Ask **material** questions only (Q-ID format); do not implement.
3. For each task, specify id, files, acceptance, validation, rollback, and dependencies.
4. VALIDATE plan against acceptance criteria and unresolved design gaps.
5. REPORT and STOP; hand off for review or bridge execution.

## Next step after this role

- Run [`plan-reviewer/`](../plan-reviewer/) on the **frozen** plan + evidence packet (verdict `APPROVE` | `REVISE` | `BLOCK`).
- After `APPROVE`, execute via local **`ide-bridge daily-coder run`** (or IDE `/daily-coder`) — browser chat does not satisfy audited implementation COMPLETE.

## Links
- [AGENT_MESSAGE.md](./AGENT_MESSAGE.md)
- [TECH.md](./TECH.md) (operator spec)
- [Core contract (../_shared/CORE_AGENT_CONTRACT.md)](../_shared/CORE_AGENT_CONTRACT.md) — optional reference
- [Call timeline (../_shared/CALL_TIMELINE.md)](../_shared/CALL_TIMELINE.md)
- [Security (../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)](../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)
