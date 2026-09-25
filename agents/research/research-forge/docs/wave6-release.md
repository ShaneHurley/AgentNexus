# Wave 6 release — adapters, skills, routing, proposals, maintenance

Mock-by-default. No automatic merge of improvement proposals. Learned routing requires human promotion and cannot self-activate.

## Modules

| Group | Path | Scope |
|-------|------|--------|
| W6-A | `src/research_forge/wave6/sdk/` | Protocol, conformance, manifests, plugin registry, health, migration |
| W6-B | `src/research_forge/wave6/adapters/` | Scholarly, code repo, standards, internal, patent, dataset mocks + dedupe |
| W6-C | `src/research_forge/wave6/skills/` | Skill manifests, five method skills, router, version store |
| W6-D | `src/research_forge/wave6/routing/` | Event schema, quality filter, static baseline, offline train, shadow, promotion, guardrails |
| W6-E | `src/research_forge/wave6/proposals/` | Proposal schema, generator, replay, human merge, canary, changelog |
| W6-F | `src/research_forge/wave6/maintain/` | Source policy review, model revalidation, drift, adversarial fixtures, DR, deprecation |

## Config and fixtures

- `config/wave6.yaml`, `config/wave6_plugins.yaml`
- `fixtures/wave6_routing_events.json`, `fixtures/wave6_proposal_failures.json`

## Tests

```bash
pytest tests/test_wave6.py -q
```

## Wave 5 boundary

Wave 6 does not implement Director Packet builder or Director call paths (Wave 5). No files under `wave5/`.
