# Wave 4 release — portfolios, fusion, experiments

## Scope

Mock-by-default ideation on scrutiny-cleared packets: independent ideators, immutable idea registry, fusion with lineage, experiment plans (no execution), fabrication checks, and exit evaluation.

## Roles (agents/)

- `ideator` — isolated opportunity-type assignments, candidate cards, NO DEFENSIBLE IDEA
- `portfolio_fusion` — compatibility matrix, explicit hybrid components
- `experiment_architect` — discriminating experiment contract per surviving idea

## Configuration

`config/wave4.yaml` — parallel ideators, repair cap, portfolio rules.

## Fixtures

- `fixtures/wave4_ideation_packet.json` — orchestrator slice with abstention
- `fixtures/wave4_diversity_fixtures.json` — paraphrase / generic / renamed-module cases
- `fixtures/wave4_fabrication_fixtures.json` — invented source, novelty, template defaults
- `fixtures/wave4_exit_tasks.json` — locked exit strata and expert expectations

## Tests

`tests/test_wave4.py` — unit/contract coverage for W4-A through W4-F.

## Wave 5 handoff

Principal Director should consume:

- `IdeationOrchestrator.run` output: `ideas`, `dimension_scores`, `experiments`, `rejected_alternatives`, `hybrid`, `interaction_review`
- Registry events (`registry_events`) for lineage and supersession audit
- Scrutiny clearance (`scrutiny.acceptance_blocked=false`) or explicit `human_override` ledger event
- Fabrication-clean, promotion-eligible ideas only in Director Packet load-bearing set
- Experiments with explicit `next_steps` (no automatic scale-up paths)
- Unresolved abstentions (`abstentions`) preserved as honest unknowns, not dropped

Do not dispatch Director while Wave 4 portfolio audit reports `critical` findings or while experiments lack rollback/stop rules.
