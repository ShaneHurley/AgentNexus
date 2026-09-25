# Research Desk (`research-desk`)

Evidence assembly and researched answers in browser-only hosts — from **no-verdict extract** through **phd-tier** diligence.

## Thought process

1. Anchor on packet objective and acceptance criteria.
2. **CLASSIFY** extract vs research vs audit (see [`HOW_TO.md`](./HOW_TO.md) picker).
3. Bounded plan with observable stop condition.
4. Evidence-tagged ACT → VALIDATE → REPORT.

## Quick picker

| You want… | Variant |
|-----------|---------|
| Facts from files only (ex doc-reader) | `assemble-given` |
| Named fields / tables / obligations only | `field-extract`, `table-capture`, `obligation-register` |
| Help me decide (verdict-first) | `quick` → `medium` (main default) → `deep` → `phd` |
| Missing info, disagreements, matrix, tab-only claim check | `gap-finder`, `contradiction-audit`, `compare-options`, `source-check` |
| Is this doc good enough? | **`document-reviewer`** — not here |

## Variant catalog

| Variant | Why it exists |
|---------|----------------|
| `assemble-given` | Ex doc-reader: inventory + locators; facts vs interpretation; IPI-safe; no search. |
| `field-extract` | Named fields only; ex information-condenser. |
| `table-capture` | Pricing/spec tables with cell locators. |
| `obligation-register` | Must/should/may extract only — not compliance judgment. |
| `quick` | 3–5 sources; verdict-first (Researcher profile shape). |
| `medium` | Comparison + one disconfirming pass (family main default). |
| `deep` | Manual multi-chat lanes; no fake fan-out (ex browser `deep-research`). |
| `phd` | Deep + adversarial + bibliography + epistemic tags. |
| `gap-finder` | Negative space / missing information; ex data-silhouette-reader. |
| `contradiction-audit` | Disagreement ledger across sources. |
| `compare-options` | Decision matrix with explicit criteria. |
| `source-check` | Verify claims against open tabs only. |

## Files

- [`AGENT_MESSAGE.md`](./AGENT_MESSAGE.md) — family main (defaults to **medium** when no variant paste)
- [`HOW_TO.md`](./HOW_TO.md) — operator picker and chains
- [`TECH.md`](./TECH.md) — harness notes
- `variants/<slug>/` — specialized pastes
