# Sources Hub — Next-Agent Research Packet

**Purpose.** One place to look back at every supplied link, paper, and high-value addition while planning or building the **modular, token-frugal daily-driver agent ecosystem**.

**Do not implement from this folder alone.** The executable build contract is:

→ [`../agent_orchestration_master_spec.md`](../agent_orchestration_master_spec.md) **Part D**

This folder is the **evidence and orientation layer** for that spec.

---

## Files in this folder

| File | What it is | When to open it |
|---|---|---|
| [`../REFERENCES.md`](../REFERENCES.md) | Clean bibliography (titles + links by topic) | Fast lookup / cite a paper |
| [`original_corpus_S01-S26.md`](original_corpus_S01-S26.md) | Source-by-source cards for the original 26 URLs (+ Plans Don't Persist resolution) | Need a specific paper's claims, limitations, and design implication |
| [`architecture_synthesis.md`](architecture_synthesis.md) | Cross-source control loop, components, contradictions, recommended sequence | First pass before touching topology or ledger design |
| [`priority_additions_by_plan_gap.md`](priority_additions_by_plan_gap.md) | Extra papers from [ai-agent-papers](https://github.com/masamasa59/ai-agent-papers), ordered by **plan gap** then importance | Filling gaps the original 26 do not close |
| [`next_agent_checklist.md`](next_agent_checklist.md) | Investigation/planning checklist mapped to master-spec sections | Starting a planning or implementation turn |

## Companion corpus (in docs/research/)

| File | Coverage |
|---|---|
| [`../agent_orchestration_research_library.md`](../agent_orchestration_research_library.md) | ~324 sources, 16 types, TIER 1–3 |
| [`../agent_orchestration_research_brief.md`](../agent_orchestration_research_brief.md) | Long-form methods/numbers for original corpus |

---

## Reading order for the next investigation agent

1. **[`architecture_synthesis.md`](architecture_synthesis.md)** — what the corpus jointly justifies.
2. **Master spec Part A (A1–A24) + Part D** — decisions and build contract.
3. **Original cards S01–S04** (practitioner) then **S07, S09, S11–S13, S17–S18, S23–S24** (full-text academic).
4. **[`priority_additions_by_plan_gap.md`](priority_additions_by_plan_gap.md)** Gap G1–G5 only (TIER-A rows).
5. Dive into the research library **by type**, not by scrolling: Type 2 (topology) → Type 4 (context/plans) → Type 5 (routing/cost) → Type 7–8 (skills) → Type 9–10 (eval/failure).

## Evidence-depth legend

| Marker | Meaning |
|---|---|
| `FULL` | Full page/PDF body available in prior work |
| `ABS` | Abstract (or abs page) only — do not lock implementation numbers without full text |
| `INDEX` | Catalogued from curated index + abstract metadata |
| `RESOLVED` | Title/URL mismatch fixed; confirm with owner if needed |

## Plan this corpus exists to support (one-line)

**Fan-out cheap read-only research → one master decides → exact zero-wiggle plans → low-tier mechanical implementers → adversarial plan/code/test review → alignment gate → optional frontier escalation on a compressed brief only.**
