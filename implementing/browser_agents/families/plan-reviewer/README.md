# Plan Reviewer

## Purpose

**Adversarially falsify** a **frozen** implementation plan and evidence packet — return exactly **`APPROVE`**, **`REVISE`**, or **`BLOCK`** with ranked, evidence-bound findings.

## When to use

- A planner (browser or IDE) produced a plan you will treat as **read-only** for this call.
- You want the strongest failure case, scope/dependency/test/rollback checks, and explicit verdict before execution.
- Browser hosts where human review replaces Daily Coder runtime `plan_reviewer`.

## When not to use

- Prefer IDE **`/daily-coder`** runtime `plan_reviewer` when the host can diff against live repo state and emit schema-valid `review` JSON.
- Do not use on a moving target — freeze plan + evidence first; revisions belong in a **new** planner call after `REVISE`.
- Do not use for net-new research or plan authoring — use `deep-research/`, `plan-prep-researcher/`, or `planner/`.
- Do not use to score plans by issue count or pad findings without locators.

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

- **STATUS:** `COMPLETE` | `PARTIAL` | `BLOCKED` — `COMPLETE` when verdict and findings are evidence-bound and `VALIDATION.PERFORMED` lists what was checked; never from prose alone.
- **MODE:** `REVIEW`
- **Required fields:** contract schema plus `ROLE_RESULT`, `EVIDENCE_OR_FILE_LOCATORS`, `DECISION_NEEDED` or `NONE`, `STOP_REASON`
- **Role-specific:** verdict **`APPROVE` | `REVISE` | `BLOCK`**; strongest failure case first; ranked findings (severity, falsifiable claim, locator); unsupported criticism omitted

## What it does (brief)

Freezes the supplied packet, attacks executability (scope, ordering, deps, permissions, rollback, tests, concurrency, acceptance), leads with the worst credible failure, and returns an exact verdict — without inventing repo facts.

## How it works (brief)

1. OBSERVE frozen plan + evidence only; declare freeze boundary.
2. REFLECT: single largest executability risk.
3. Attack plan dimensions with evidence-bound claims.
4. Rank findings; drop unsupported items.
5. Emit verdict and STOP; planner revision or bridge if `APPROVE`.

## Next step after this role

- **`REVISE`:** return to [`planner/`](../planner/) with findings + preserved accepted tasks; re-freeze and re-review.
- **`APPROVE`:** run **`ide-bridge daily-coder run`** (or IDE `/daily-coder`) — browser review is not audited execution COMPLETE.
- **`BLOCK`:** fix authority/evidence gaps before replanning.

## Links
- [AGENT_MESSAGE.md](./AGENT_MESSAGE.md)
- [TECH.md](./TECH.md) (operator spec)
- [Core contract (../_shared/CORE_AGENT_CONTRACT.md)](../_shared/CORE_AGENT_CONTRACT.md) — optional reference
- [Call timeline (../_shared/CALL_TIMELINE.md)](../_shared/CALL_TIMELINE.md)
- [Security (../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)](../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)
