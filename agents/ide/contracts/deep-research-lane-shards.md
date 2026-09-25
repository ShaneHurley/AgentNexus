# Deep Research — lane contract shards (experiment stub)

**Status:** opt-in only. **Default:** `lane_contract_shards: false` in `#file:ide-agents/config/token_experiments.json`.

When the flag is **off**, Step 2 in `#file:ide-agents/contracts/deep-research-phase-index.md` loads the Common lane section plus the assigned lane specialization from `#file:ide-agents/contracts/subagent-contracts.md` (current behavior).

When the flag is **on**, load **only** the shard named for the lane scout being invoked, then the Common lane header (minimal cross-lane rules):

| Lane scout | Shard section (within `subagent-contracts.md`) |
|------------|--------------------------------------------------|
| internal-authority-scout | Internal Authority Scout |
| official-standards-scout | Official Standards Scout |
| academic-evidence-scout | Academic Evidence Scout |
| practitioner-implementation-scout | Practitioner Implementation Scout |
| failure-unfavorable-scout | Failure / Unfavorable Scout |
| alternatives-analogy-scout | Alternatives / Analogy Scout |

Do not preload other lane shards in the same parent turn. Full pack preload remains forbidden.

**Promotion (not measured here):** enable only after benchmark shows ≥15% token reduction on deep-research runs with no decline in adversarial PASS rate.
