# Installing the Agent Ecosystem Upgrade

## Scope

This package is an additive upgrade prepared from the supplied repository documentation. It does not contain the original runtime source, so it does not replace Daily Coder or Research Forge implementation files.

It adds `agents/shared/agent-core/`, reusable skills under `agents/shared/skills/`, updated documentation, schemas, tests, and adapter specifications. Existing runtime and generated IDE paths remain intact.

## Recommended installation

1. Create a branch.
2. Back up or commit local changes.
3. Extract this archive at the repository root.
4. Review changes to `README.md`, `AGENTS.md`, browser documentation, and Research Forge documentation.
5. Install and validate:

```bash
python -m pip install -e agents/shared/agent-core
python -m agent_core validate-registry
python -m unittest discover -s agents/shared/agent-core/tests -v
# Legacy: scripts/validate_upgrade.py is not in this repo — skip or verify before use
```

6. Integrate runtime adapters one package at a time.
7. Run existing repository tests before merging.

## Safe application helper

> **Legacy / verify before use:** `scripts/apply_upgrade.py` and `scripts/validate_upgrade.py` are **not** present in the current v2 tree. Prefer `pip install -e agents/shared/agent-core` and package tests above.

If you still have those scripts from an older upgrade archive:

```bash
python scripts/apply_upgrade.py --target /path/to/ai_agents
python scripts/apply_upgrade.py --target /path/to/ai_agents --apply
```

The helper does not overwrite a conflicting file unless `--replace-docs` is supplied. When replacement is enabled, it stores the previous file under `.agent-upgrade-backup/`.

## Important limitation

The supplied material contained repository documentation rather than the complete source tree. Adapter modules are therefore specifications and examples until verified against the actual runtime APIs. This limitation is recorded in the adversarial review and migration plan.
