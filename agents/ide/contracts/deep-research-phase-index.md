# Deep Research — phase contract index

Load **one** contract file per active parent step. Do not preload the full pack at orchestrator entry.

| Step | Parent phase | Load when entering step |
|------|----------------|-------------------------|
| 1 | Frame | `#file:ide-agents/contracts/subagent-contracts.md` (Research Planner section only) |
| 2 | Fan-out lanes | `#file:ide-agents/contracts/subagent-contracts.md` (Common lane + assigned lane specialization). **Default:** six concurrent lanes. If `#file:ide-agents/config/token_experiments.json` has `conditional_deep_research_lanes: true`, Step 2 covers lanes 1–3 only; lanes 4–6 load this row when gap-tagged. If `lane_contract_shards: true`, use `#file:ide-agents/contracts/deep-research-lane-shards.md` instead of loading unrelated lane sections. |
| 3 | Frontier expand | `#file:ide-agents/contracts/subagent-contracts.md` (Targeted Gap Researcher + stop rules) |
| 4 | Integrate | `#file:ide-agents/contracts/subagent-contracts.md` (Evidence Integrator) + `#file:ide-agents/contracts/research-draft-1.0.schema.json` |
| 5 | Adversarial review | `#file:ide-agents/contracts/subagent-contracts.md` (Adversarial Evidence Reviewer) |
| 6 | Correction wave | `#file:ide-agents/contracts/subagent-contracts.md` (Targeted Gap Researcher) |
| 7 | Score | `#file:ide-agents/contracts/recommendation-scoring.md` + `#file:ide-agents/contracts/research-intelligence-packet-1.0.schema.json` |
| 8 | Messenger | Delegate to `research-messenger`; parent does not load messenger contracts |

**Cross-cutting (load once when first classifying claims, not at entry):**

- `#file:ide-agents/contracts/evidence-and-source-rubric.md`
- `#file:ide-agents/contracts/claim-enum-map.md`
- `#file:ide-agents/contracts/ecosystem-compatibility.md`
- `#file:ide-agents/contracts/output-template.md` (human report shape after scoring)
