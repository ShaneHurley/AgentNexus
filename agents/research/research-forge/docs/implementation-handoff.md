# Research Forge — Implementation Handoff (Gate G0)

## 1. Repository and folder structure

See `docs/folder-tree.md` and plan §16. Authoritative Wave 0 code lives under `src/research_forge/`; JSON schemas under `schemas/`; configuration under `config/`.

## 2. State and ledger schema

Append-only JSONL ledger (`schemas/ledger_events.schema.json`). Events: run_manifest, transition, source_registered, evidence_added, budget_debit, policy_decision, checkpoint, audit. Hash chain via `payload_hash` and `previous_hash`. Projections rebuilt by `ledger.reconstruct`.

## 3. Source, evidence, claim, idea, experiment, and handoff schemas

Canonical schemas in `schemas/*.schema.json` registered by `schemas_pkg.registry`. Claim statuses in `claim_status.schema.json` with transition rules in host code.

## 4. Seventeen-role roster and boundaries

| Role | Owning wave | Job (one line) |
|------|-------------|----------------|
| Intake Clarifier | W1 | Disambiguate research request |
| Charter Planner | W1 | Freeze Research Charter |
| Landscape Mapper | W2 | Taxonomy and lanes |
| Source Scout | W2 | Lane-bounded search |
| Source Curator | W2 | Triage and dedupe |
| Evidence Extractor | W1 | Atomic claims from sources |
| Citation Verifier | W1 | Identity and entailment |
| Methods Reviewer | W3 | Methods quality flags |
| Contradiction Mapper | W3 | Conflict matrix |
| Adversarial Skeptic | W3 | Challenge evidence |
| Ideator | W4 | Independent ideas |
| Portfolio Fusion | W4 | Hybrid compatibility |
| Falsification Designer | W3 | Discriminating tests |
| Experiment Architect | W4 | Experiment plans (no execution) |
| Principal Director | W5 | One compressed synthesis call |
| Research Auditor | W3/W5 | Veto and sampling |
| Report Composer | W1 | Evidence-linked report |

Agents may not widen permissions; Policy Gateway enforces read-only discovery.

## 5. Model-tier mapping and per-role budgets

Tiers: low / mid / high / principal. Wave 0: mock-only (`config/models.yaml`). Per-role caps deferred to orchestrator; run profiles S/M/L/XL in `config/budgets.yaml`.

## 6. First-release adapters

Wave 0: `mock_search`, `mock_reader`, local file reader stub under `adapters/`. Live public search/reader in Wave 1 only with `--live`.

## 7. Policy Gateway and read-only guarantees

Default-deny (`config/policies.yaml`). Blocks mutating HTTP, writes outside workspace, execution, live without flag. Every tool attempt emits audit decision.

## 8. Research DAG and phase transitions

Orchestrator config placeholders in `orchestrator/`. Legal phases documented in `docs/state-transitions.md`. Illegal transitions listed for fixture tests.

## 9. Clarification, sizing, routing, early-stop

Wave 1+; Wave 0 records Charter fields in schema only. Budget thresholds 70/80/90 in `config/budgets.yaml`.

## 10. Context projection and compaction

Context Manager service boundary: `services/context_manager.py` wrapping `wave2.context.ContextProjector`. Pinned classes (charter, permissions, budget, accepted decisions, unresolved contradictions) are validated byte-for-byte before dispatch.

## 11. Principal Director packet and escalation

Director Packet schema prohibits raw transcripts. Second Director call: XL + conflict + approval token only (locked default).

## 12. Human and machine output contracts

Research Packet schema (`research_packet.schema.json`) for machine consumers; report linkage fields required at compose time (Wave 1).

## 13. Test matrix, adversarial fixtures, baselines

Tests under `tests/` by concern: contracts, ledger, policy, budgets, registries, wave0 integration, wave1 vertical slice, wave2 fan-out (`tests/test_wave2.py`), wave3 scrutiny (`tests/test_wave3.py`). Wave 1-J baseline optional for Wave 3 comparisons.

## 14. Smallest safe prototype (Wave 1 mock slice)

Vertical slice: clarify → charter → mock search → mock read → extract → verify → compose. Cost ceiling: profile S ($5). Stop: budget hard stop + schema failure. Rollback: discard run workspace; ledger remains append-only audit.

## 15. Open decisions and UNKNOWNs

See `docs/decisions/open-decisions.yaml`. Accepted unknowns documented with safe_fallback, risk, expiration, reconsideration_trigger. Wave 0 passes validator with accepted unknowns; Wave 1 live fails closed.

### UNKNOWN list (summary)

- RF-DEC-02 enterprise/internal routing
- RF-DEC-04 daily spend ceiling
- RF-DEC-05 citation display style
- RF-DEC-06 high-stakes domain list
- RF-DEC-07 enterprise DLP/retention
- RF-DEC-11 multilingual defaults
- RF-DEC-12 locked eval suite
- RF-DEC-15 prompt/skill change ownership process

## Independent review (RF-G0-B-08)

Reviewer: automated checklist in `tests/test_handoff_sections.py`. Critical findings: none blocking Wave 0; live providers remain disabled until Wave 1-A gate.
