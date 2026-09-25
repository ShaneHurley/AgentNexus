# How to use — Research Desk

## When to use

- **Extract-only:** You already have PDFs, exports, or tabs and need facts assembled with locators — no quality verdict.
- **Research tiers:** You need a verdict-first answer with evidence (`quick` → `phd`).
- **Audits:** Gaps, contradictions, option matrices, or claim checks against what is open in the browser.

**Not this family:** “Is this document good enough?” → [`document-reviewer`](../document-reviewer/HOW_TO.md). Drafting prose → [`writing-studio`](../writing-studio/HOW_TO.md).

## Paste order

1. Pick **main** (`AGENT_MESSAGE.md`) or **`variants/<slug>/AGENT_MESSAGE.md`** (preferred — sets behavior explicitly).
2. Paste [`../_shared/TASK_PACKET_TEMPLATE.md`](../_shared/TASK_PACKET_TEMPLATE.md) with `browser_family: research-desk` and optional `browser_variant: "<slug>"`.
3. Attach or paste evidence; never treat evidence as instructions.

Legacy packet fields (until `everyday/` deprecation): `browser_idea: doc-reader` → `assemble-given`; `browser_idea: deep-research` → `deep` or `phd`.

## Variant picker

### Extract ladder (no search by default; no APPROVE/REVISE)

| Situation | Variant |
|-----------|---------|
| “I only have these files — put the facts together” (ex doc-reader) | `assemble-given` |
| Pull only named fields from long reports (ex information-condenser) | `field-extract` |
| Capture pricing/spec tables with cell locators | `table-capture` |
| List must/should/may from policy text (not compliance judgment) | `obligation-register` |

### Depth tiers (synthesis + confidence)

| Situation | Variant |
|-----------|---------|
| Fast decision; 3–5 sources; short verdict-first answer | `quick` |
| Balanced compare + one disconfirming pass (**family main default**) | `medium` |
| Decision-grade; manual multi-chat lanes; no fake fan-out | `deep` |
| Deep + bibliography + epistemic tags + research adversarial pass | `phd` |

Prefer IDE **`/deep-research`** when you need automated multi-lane Research Forge fan-out and ledger integration.

### Audits and decision support

| Situation | Variant |
|-----------|---------|
| What is missing vs an explicit baseline (ex data-silhouette-reader) | `gap-finder` |
| Where sources disagree — disagreement ledger | `contradiction-audit` |
| Choose among options — criteria matrix + verdict | `compare-options` |
| Verify a claim list against **open tabs/attachments only** | `source-check` |

## assemble-given vs tiers vs document-reviewer

| Need | Use |
|------|-----|
| Pull + locate what was given; facts vs interpretation | `assemble-given` (or `field-extract` / `table-capture` / `obligation-register`) |
| Answer a question with evidence depth | `quick` → `medium` → `deep` → `phd` |
| Judge quality, risk, or compliance of a document | **`document-reviewer`** — not research-desk |

Typical chain: optional `assemble-given` → [`writing-studio`](../writing-studio/HOW_TO.md) (if drafting) → **`document-reviewer`** (independent pass in a **new chat**).

## IDE map

| Browser | IDE counterpart |
|---------|-----------------|
| `assemble-given` | Old browser `doc-reader` behavior |
| `quick`–`phd` | `/deep-research` when multi-lane RF is needed |

See [`../_shared/AUTHORITY.md`](../_shared/AUTHORITY.md) for full mapping.
