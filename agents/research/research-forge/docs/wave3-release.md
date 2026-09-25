# Wave 3 release — scrutiny layer

## Scope

Mock-by-default scrutiny on frozen fan-in packets: methods review, contradiction mapping, adversarial skeptic, falsification design, bounded follow-up, and independent audit with veto.

## Roles (agents/)

- `methods_reviewer` — checklists, comparability, stats limitations, leakage, recomputation sandbox
- `contradiction_mapper` — proposition registry, evidence matrix, gaps
- `adversarial_skeptic` — frozen evidence challenges, round cap
- `falsification_designer` — discriminating tests only (no implementation recommendations)
- `followup_coordinator` — authorized single-round lane reuse
- `research_auditor` — checklist, sampling seed, critical veto

## Configuration

`config/wave3.yaml` — skeptic rounds, follow-up max rounds, auditor sample rate, calibration thresholds.

## Fixtures

- `fixtures/wave3_scrutiny_packet.json` — exit-gate packet (methods flags, contradiction, audit adversarial)
- `fixtures/wave3_methods_fixtures.json` — RF-W3-A-08 detection cases

## Tests

`tests/test_wave3.py` — unit/contract coverage for W3-A through W3-G.

## Wave 4 handoff

Wave 4 ideation should consume:

- Verified evidence cards and `acceptance_blocked=false` audit clearance (or explicit human override event)
- `contradictions` / `gaps` with resolution status — unresolved high-relevance gaps constrain recommendations
- `falsification.tests` ranked for experiment architect seeding
- Pinned charter and unresolved contradictions from Context Manager unchanged
- Methods `eligibility_downgrade` flags — downgraded sources must not support recommendation-eligible claims without repair

Do not start ideators while `audit.veto` is true or follow-up rounds exceed config max without ledger authorization events.
