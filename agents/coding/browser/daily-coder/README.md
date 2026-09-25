# daily-coder

> **Redirect:** Implementation drafts live under **Code Crafter** — use [`code-crafter/variants/patch-draft`](../code-crafter/variants/patch-draft/README.md) with `browser_family: code-crafter`, `browser_variant: patch-draft` (legacy `browser_idea: daily-coder` — see [`../_shared/AUTHORITY.md`](../_shared/AUTHORITY.md)). Audited repo mutation still requires local `ide-bridge daily-coder run` (or IDE `/daily-coder`). This folder remains a legacy stub.

> **Browser daily-coder proposes diffs/commands only.** Never treat chat prose as COMPLETE for writes.

## Purpose

Produce one **coding change draft** for an approved, in-scope task: minimal patch or file contents, verification checklist, rollback steps, and a copy-ready **HANDOFF_TO_IDE_BRIDGE** block so the operator can run audited mutations locally.

## When to use

- You have an **approved plan** (from `planner/` + `plan-reviewer/` or equivalent) and need a bounded implementation draft in a browser host.
- The host can read pasted code/snippets or attachments but you will **not** claim git commits, test runs, or merges from chat alone.
- You want explicit `RUN` | `NOT RUN` | `PROPOSED` labels on every command and check.

## When not to use

- Prefer IDE **`/daily-coder`** or **`ide-bridge daily-coder run`** when you need PolicyGateway-backed runs, plan approval gates, SQLite state, or verified terminal JSON status.
- Do not use for **plan-only** work → `planner/` then `plan-reviewer/`.
- Do not use for **read-only recon** without implementation → `plan-prep-researcher/` or IDE `/researcher`.
- Do not use to emulate the full Daily Coder **phase DAG**, sixteen role fan-out, or mock/live runtime transitions in one web thread.

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

- **STATUS:** `COMPLETE` | `PARTIAL` | `BLOCKED` — `COMPLETE` only when every material acceptance criterion has **observable** evidence in `VALIDATION.PERFORMED`; browser drafts alone → typically `PARTIAL`.
- **MODE:** `CODING`
- **Required fields:** contract schema (`RESULT` / `ROLE_RESULT`, `VALIDATION.PERFORMED` / `NOT_PERFORMED`, `EVIDENCE`, `STOP_REASON`)
- **Role-specific:** unified diff or full file draft; command list with `RUN` | `NOT RUN` | `PROPOSED`; rollback; **`HANDOFF_TO_IDE_BRIDGE`** block; `DECISION_NEEDED` or `NONE`

## What it does (brief)

Inspects supplied context, aligns with the frozen plan, proposes the **smallest safe change**, lists verification steps the operator or bridge should run, and stops—without inventing test passes or repo writes.

## How it works (brief)

1. OBSERVE inputs, plan anchor, and acceptance criteria from the task packet.
2. Characterize or reproduce the failure from **supplied** evidence only.
3. Name target files and minimal edit before producing a patch.
4. Stop on plan/code mismatch; one Q-ID bundle if a material choice remains.
5. Emit patch + labeled checks + rollback + bridge handoff; report honest validation status.

## Next step after this role

1. Operator reviews the draft diff and checklist.
2. Run **`ide-bridge daily-coder run --request "…" --repo <path>`** (mock default) with mission text copied from the handoff block; **`approve`** / **`resume`** as runtime prompts.
3. Treat bridge exit codes and JSON as authoritative for SIMULATED/COMPLETE/BLOCKED—not this chat.

## Links
- [AGENT_MESSAGE.md](./AGENT_MESSAGE.md)
- [TECH.md](./TECH.md) (operator spec)
- [Core contract (../_shared/CORE_AGENT_CONTRACT.md)](../_shared/CORE_AGENT_CONTRACT.md) — optional reference
- [Call timeline (../_shared/CALL_TIMELINE.md)](../_shared/CALL_TIMELINE.md)
- [Security (../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)](../_shared/SECURITY_AND_RESTRICTED_ENVIRONMENTS.md)
