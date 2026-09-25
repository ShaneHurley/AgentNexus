# Wave 5 release — Principal Research Director

## Scope

Mock-by-default Director synthesis on compressed, fidelity-checked packets: one authorized intellectual call, optional XL challenge path, handoff taxonomy, and exit evaluation.

## Roles (agents/)

- `principal-director` — structured synthesis only; no search/reader/shell/write tools

## Configuration

- `config/wave5.yaml` — packet token ceiling, mock provider, handoff policy version

## Fixtures

- `fixtures/wave5_synthesis_source.json` — scrutiny + portfolio slice for packet build and orchestrator
- `fixtures/wave5_handoff_tasks.json` — matched handoff strata and regression fingerprint
- `fixtures/wave5_exit_tasks.json` — Director vs no-Director value expectations
- `fixtures/wave5_one_call_fixtures.json` — idempotency and forbidden-field cases

## Tests

`tests/test_wave5.py` — coverage for RF-W5-A through RF-W5-E.

## Wave 6 handoff

Do not extend adapter SDK or skill routing here. Wave 6 may wire live provider adapters to `DirectorProvider.complete_fn` and register `director_synthesis` in external tooling; this wave keeps mock responses under `wave5/mock_responses.py`.
