# Wave 2 release — bounded fan-out

## Scope

Wave 2 adds difficulty-gated, non-overlapping discovery fan-out on top of Wave 1 charter output:

- **W2-A** `wave2.landscape` — angle taxonomy, terminology map, lane generation and merge review
- **W2-B** `wave2.scout` — lane contract, progressive mock search, bounded candidate records
- **W2-C** `wave2.scheduler` — ownership, concurrency caps, deduping registry stream, deterministic fan-in
- **W2-D** `wave2.curator` — query fingerprints, multi-axis scores, triage statuses, derivative clusters
- **W2-E** `wave2.saturation` — round metrics, stop rules, snowball eligibility, early success
- **W2-F** `wave2.context` + `services/context_manager.py` — pinned projection API and telemetry
- **W2-G** `wave2.dashboard` — ledger-derived duplicate/yield/budget metrics
- **W2-H** `wave2.evaluation` — matched experiment report, routing rule, Wave 2 audit helper

Entry point: `FanOutOrchestrator` in `research_forge.wave2.fanout`.

## Configuration

- `config/wave2.yaml` — scheduler, saturation, scout caps, routing gates
- `config/scoring.yaml` — curator dimension weights and routing score thresholds

## Tests

Unit/contract tests: `tests/test_wave2.py` (mock search only; no live network).

Fixtures: `fixtures/wave2_curator_regression.json`, `fixtures/wave2_dashboard_events.json`.

## Wave 3 handoff

Wave 3 should consume frozen fan-in sources and triage decisions from ledger events (`source_registered`, `audit`, `evidence_added`). Methods Reviewer and Contradiction Mapper activate on load-bearing sources identified by curator `DEEP_READ` / `FOLLOW_CITATIONS` statuses. Context Manager pinned charter and unresolved contradictions must be passed into W3 frozen-evidence roles unchanged.
