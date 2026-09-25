# F3 rollback: `deep-research/research-forge/` → `research-forge/`

> **Historical rollback note (pre-v2 path names).** Current layout uses `agents/research/research-forge/`, `agents/coding/daily-coder-ecosystem/`, and `agents/ide/`. Commands below are updated to v2 physical paths.


**Phase:** F3 (Research Forge physical nest under `deep-research/`)  
**Owner:** migration PR author  
**Max rollback time:** ~10 minutes (folder move + path/doc/projection revert)

## When to roll back

- CI Research Forge pytest step fails after merge and cannot be fixed forward quickly.
- Downstream automation still hard-codes top-level `research-forge/` as a **directory** (not PyPI/CLI name).

## Rollback (git checkout with history)

From repository root:

```bash
git mv deep-research/research-forge research-forge
```

Then revert F3 commits that touched:

- `.github/workflows/ci.yml` (`working-directory: deep-research/research-forge` → `research-forge`)
- `ai_agents_repo/src/ai_agents_repo/paths.py` (legacy `rf` map → `research-forge` at repo root if rolling back dual-map policy)
- `gui/config/agents.json` (`package_root` / `workspace_root`)
- `agents/ide/scripts/import_rf_agents.py` and regenerated `MANIFEST.yml` / `canonical/*.md` / projections
- Root `README.md`, `docs/README.md`, `deep-research/README.md`, and doc links under `docs/` pointing at `deep-research/research-forge/`

Re-run smoke:

```bash
cd agents/research/research-forge
pip install -e ".[dev]"
pytest -q
python agents/ide/scripts/import_rf_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
```

Regenerate inventory baseline:

```bash
python ai_agents_repo/scripts/generate_path_consumer_inventory.py
```

## Without git

```powershell
Move-Item -Path deep-research\research-forge -Destination research-forge
```

Then restore the same file edits as above.

## Evidence to attach after rollback

- Research Forge `pytest -q` exit code 0
- `import_rf_agents.py --check` and `sync_ide_agents.py --check` exit code 0
- `python -m ai_agents_repo.validate --phase F0` exit code 0 (if layout maps restored consistently)
