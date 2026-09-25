# Next-Agent Investigation & Planning Checklist

**Goal.** Plan (then later build) the modular, token-frugal daily-driver agent ecosystem **without losing the user’s requirements**.

**Authoritative build text.** [`../agent_orchestration_master_spec.md`](../agent_orchestration_master_spec.md) — especially **Part D**.  
**Evidence hub.** This `sources/` folder + the research library/brief.

---

## 0. Intake (do not skip)

- [ ] Confirm this is a **design/planning** turn (or implementation turn with human acceptance of Part D).
- [ ] Read [`README.md`](README.md) → [`architecture_synthesis.md`](architecture_synthesis.md).
- [ ] Skim master spec **Part A (A1–A24)** and **Part C (tensions)**.
- [ ] Record blocking unknowns: target tasks, risk tier, permissions, cost/latency budgets, baseline (G01/G05).

---

## 1. Preserve the user’s non-negotiable intent

Do not drop any of these when rewriting or scaffolding:

| Intent | Where encoded |
|---|---|
| Fan-out cheap read-only research first | Part D Phase 1 |
| One master owns all decisions/thinking/planning | Part D Phase 2 |
| Hot-swappable models via specialist folders | Part D.9 |
| Exact zero-wiggle implementer tasks | Part D Phase 4–6 |
| Token-frugal; rare frontier on compressed brief | Part D.3 |
| Adaptive sizing (trivia skips fan-out) | Part D Phase 0 |
| Brainstormer with honest “nothing found” | Part D Phase 3 |
| Adversarial plan + code + test review | Part D Phases 5, 7 |
| Documenter proposal-only | Part D Phase 10 |
| Alignment / drift control | Part D.7 / Phase 9 |
| Control-word prompt skeleton (OBSERVE→VALIDATE, ADVERSARIAL, claim tags) | Part D.4 |
| Meaningful testing policy | Part D.6 |
| Swiss-army extensibility by **addition** | Part D.2 #16, D.9 |

If you rewrite wording, **diff against this table** and restore anything missing.

---

## 2. Evidence pass before architecture lock

| Decision | Read first | Sources |
|---|---|---|
| Fan-out vs single agent | Gap G1 Tier A | `priority_additions_by_plan_gap.md` |
| Plan/ledger/context | Gap G2 Tier A + S17b/S18 | `original_corpus_S01-S26.md` |
| Routing / frontier rationing | Gap G3 Tier A | same |
| Skills lifecycle | Gap G4 Tier A + S10–S15 | same |
| Eval / review / field baseline | Gap G5 Tier A + S09 | same |
| Tool surface | S02, S09 | original corpus |
| Specialist contracts | S01, S03, S07 | original corpus |

Deep dive only as needed: [`../agent_orchestration_research_library.md`](../agent_orchestration_research_library.md) by **Type**, TIER 1 first.

---

## 3. Planning outputs (produce these artifacts)

When planning (not yet implementing), emit:

1. **Target profile** — tasks, risk tier, permissions, budgets, DoD metrics (or explicit `UNKNOWN` + owner question).
2. **Topology recommendation** — with **strong single-agent baseline** comparison plan.
3. **Phase graph** — Phase 0–10 from Part D mapped to concrete folders/agents.
4. **Contract stubs** — one specialist folder layout with schemas (no silent expansion of roles).
5. **Eval harness sketch** — 20 held-out tasks, failure taxonomy, pass-all-k, cost-per-verified-pass.
6. **Risk register** — Part C tensions + skill security + collaboration gap.
7. **Open questions** — only decision-critical items (G01–G06 style).

---

## 4. Implementation order (when authorized)

Follow master spec **Part E** if present; otherwise this default:

1. Run ledger + event schemas  
2. Policy gateway (deny-by-default)  
3. Typed handoff schemas + claim tags  
4. Sizing gate + alignment checker  
5. Recon workers (read-only) + master  
6. Planner + plan reviewer  
7. Implementer + worktree isolation  
8. Test author / executor + code reviewer  
9. Frontier advisor (rationed) + brainstormer  
10. Skill registry (human merge only)  
11. Trajectory eval harness + baselines  

**Stop condition:** Do not add agents or autonomous skill rewrite until held-out eval detects sequencing/retrieval/regression failures.

---

## 5. Control-word reminder (every new prompt)

```text
ROLE: <one job>
1. OBSERVE → 2. REFLECT → 3. ACT → 4. VALIDATE → 5. STOP
ALWAYS / NEVER / IF THEN / STRICT / ONLY / BUDGET
Claim tags: VERIFIED | INFERENCE | ASSUMPTION | UNKNOWN
Review roles also: ADVERSARIAL
```

Topic keywords do not replace enforceable checks.

---

## 6. Integrity checks before you finish a turn

- [ ] No detail from the user’s plan was dropped (table in §1).
- [ ] Every recommendation cites a source ID or marks `INFERENCE`/`UNKNOWN`.
- [ ] Citation note: Plans Don't Persist = `2606.22953`, not `2605.21902`.
- [ ] Unfavorable evidence listed (fan-out can hurt; bad plans hurt; skills can poison).
- [ ] Companion links still point to master spec + this sources hub.
- [ ] No claim of authorization to deploy/spend/write production systems.

---

## 7. Related trees

| Path | Use |
|---|---|
| `../../daily-coder-ecosystem/` | Existing scaffold — align, do not fork blindly |
| `../../research-forge/` | Separate research product; do not conflate |
| [`../README.md`](../README.md) | Documentation index |
