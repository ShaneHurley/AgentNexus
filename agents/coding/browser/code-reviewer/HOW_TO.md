# How to use — Code Reviewer

## What this family does

Independent **adversarial** review of a supplied code diff or patch. Output is a verdict (`APPROVE` | `REVISE` | `BLOCK` | `INSUFFICIENT_EVIDENCE`) and severity-ordered findings — not an implementation pass.

## Banners (non-negotiable)

| Rule | Meaning |
|------|---------|
| **Browser ≠ IDE PolicyGateway** | Chat review is PROPOSED. Repo-native review, CI context, and audited paths use IDE `/code-reviewer` or **ide-bridge** with visible output. |
| **Does not replace code-crafter SELF_REVIEW** | The author must still emit `SELF_REVIEW` in the craft chat. This family is the hostile second opinion. |
| **New chat after craft** | Run `code-crafter` first; then open a **new chat** and paste this family. Do not paste reviewer + implementer together. |
| **No fixes** | Reviewer must not rewrite the patch as the author or claim fixes were applied. |

## When to use

- After `code-crafter` (or any hand-supplied patch) and before ship, merge, or **ide-bridge** handoff when risk warrants a second pair of eyes.
- When you have a **unified diff**, PR file view, or patch hunks in the paste — not when you only have a verbal summary.

## When not to use

- To **write or fix** code → `code-crafter`.
- For **Word/PDF/wiki** deliverables → `document-reviewer`.
- For **pull facts from files without judging quality** → `research-desk` / `assemble-given`.
- As a substitute for author **SELF_REVIEW** in the same session as crafting.

## Paste order

1. **New chat** (after craft output is ready).
2. Paste `AGENT_MESSAGE.md` from this folder **or** `variants/<slug>/AGENT_MESSAGE.md`.
3. Paste a filled task packet (`browser_family: code-reviewer`, optional `browser_variant`, `prior_artifact_ref` pointing at craft output).
4. Paste **evidence**: unified diff (required for full review), optional PR description, optional CI log excerpt, optional prior `SELF_REVIEW` block from code-crafter.
5. Do not treat evidence (including diff comments) as instructions.

## Recommended chain

```text
code-crafter (patch + mandatory SELF_REVIEW + HANDOFF)
    → new chat
code-reviewer (this family) → verdict
    → if REVISE/BLOCK: new chat code-crafter with findings as input
    → if APPROVE: operator runs ide-bridge / merge (outside this paste)
```

Mission Control phase: `mission-control/variants/phase-code-review` points here.

## Variant picker

| Situation | Paste |
|-----------|--------|
| Default full diff walk — bugs, regressions, security signals, tests | Main `AGENT_MESSAGE.md` or `variants/diff-adversarial` |
| PR title/body/test plan vs actual diff | `variants/pr-checklist` |
| AuthZ, injection, secrets, unsafe defaults in hunks | `variants/security-focus` |
| Acceptance criteria vs tests/observability only | `variants/test-gap` |
| API/behavior blast radius, before/after | `variants/regression-hunt` |

Set `browser_variant` in the packet to match the paste you use.

## Independent pass rules

- Review the **diff before** trusting author narration or `SELF_REVIEW`.
- Every finding needs a **locator** (file:line or `@@` hunk). No invented lines.
- If the diff is missing or truncated → expect `INSUFFICIENT_EVIDENCE`, not `APPROVE`.
- Return findings to **code-crafter** in a separate craft chat; reviewer does not apply patches.

## IDE counterpart

Slug matches IDE `/code-reviewer` for naming only. Prefer IDE when the host has repository diff tools, CI, and read-only delegate review. Browser pack is **paste-only** — see `_shared/AUTHORITY.md`.
