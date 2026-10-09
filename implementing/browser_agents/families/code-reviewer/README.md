# Code Reviewer (`code-reviewer`)

**Display:** Code Reviewer — Adversarial Diff Pass

Independent reviewer for source-code changes. Tries to **disprove** that a patch meets acceptance criteria using only supplied diff and context. Complements — never replaces — **code-crafter** mandatory `SELF_REVIEW`.

## Thought process

1. **Anchor** on the task packet: objective, acceptance criteria, `prior_artifact_ref` to craft output.
2. **Establish the case** — what artifact is under review, what “done” means, what evidence exists (diff first).
3. **Fact-find** — build a locator-backed fact table; tag `VERIFIED` / `SUPPORTED` / `INFERRED` / `UNKNOWN`; audit author `SELF_REVIEW` against hunks.
4. **Walk** the change in a fixed order (structure → correctness → risks → tests).
5. **Disprove** — assume failure; run falsifiable hypotheses on the diff.
6. **Verdict** — one of `APPROVE` | `REVISE` | `BLOCK` | `INSUFFICIENT_EVIDENCE`; findings sorted by severity.

Browser hosts have no PolicyGateway: review prose is **PROPOSED** until the operator acts (merge, bridge, IDE review).

## Two-layer review model

| Layer | Who | When |
|-------|-----|------|
| Self-review | `code-crafter` (same chat as author) | Before final patch / handoff |
| Independent review | `code-reviewer` (**new chat**) | After craft, before ship |

Skipping self-review violates code-crafter contract. Skipping independent review is an operator choice; this family exists for when you want a hostile second pass.

## Main vs variants

The **main** `AGENT_MESSAGE.md` uses the default **diff-adversarial** procedure (full hunk walk). Variants narrow the walk lens without changing the verdict schema.

## Variant catalog

| Variant | Why it exists |
|---------|----------------|
| `diff-adversarial` | Default: sequential @@ hunk walk; bugs, regressions, security signals, missing tests. |
| `pr-checklist` | PR-shaped honesty — description, scope, test plan, breaking changes vs diff. |
| `security-focus` | Trust boundaries, AuthZ, injection, secrets, unsafe defaults — fact-bound only. |
| `test-gap` | Maps acceptance criteria to test/observability evidence; gap matrix output. |
| `regression-hunt` | Before/after behavior, public API deltas, blast radius table. |

## Related families

- **`code-crafter`** — produces patch + `SELF_REVIEW`; not a reviewer.
- **`document-reviewer`** — non-code prose/PDF/Word.
- **`research-desk` / `assemble-given`** — extract facts; no quality verdict.
- **`mission-control` / `phase-code-review`** — orchestrates when to paste this family.

## Files

| File | Role |
|------|------|
| `AGENT_MESSAGE.md` | Default paste (diff-adversarial procedure) |
| `HOW_TO.md` | Operator steps, chain, variant picker |
| `TECH.md` | Full embed copy for tooling |
| `examples/` | Sample packet + output skeleton |
| `variants/<slug>/` | Specialized paste + short README |

IDE spirit reference (paste-only here): `.github/agents/code-reviewer.agent.md` — review actual diff adversarially before author commentary.
