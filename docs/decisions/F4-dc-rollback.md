# F4 rollback: `coder/daily-coder-ecosystem/` → `daily-coder-ecosystem/`

> **Historical rollback note (pre-v2 path names).** Current layout uses `agents/research/research-forge/`, `agents/coding/daily-coder-ecosystem/`, and `agents/ide/`. Commands below are updated to v2 physical paths.


**Phase:** F4 (Daily Coder ecosystem physical nest under `coder/`)  
**Owner:** migration PR author  
**Max rollback time:** ~10 minutes (folder move + path/doc/CI revert)

## When to roll back

- CI Daily Coder unittest/benchmark step fails after merge and cannot be fixed forward quickly.
- Downstream automation still hard-codes top-level `daily-coder-ecosystem/` as a **directory** (not PyPI/CLI name).

## Rollback (git checkout with history)

From repository root:

```bash
git mv coder/daily-coder-ecosystem daily-coder-ecosystem
```

Then revert F4 commits that touched:

- `.github/workflows/ci.yml` (`working-directory: coder/daily-coder-ecosystem` → `daily-coder-ecosystem`; GUI `pip install -e ../coder/daily-coder-ecosystem`)
- `ai_agents_repo/src/ai_agents_repo/paths.py` (legacy + v2 `dc` map → `daily-coder-ecosystem` at repo root)
- `ai_agents_repo/src/ai_agents_repo/layout.py` (nested vs root DC detection)
- `gui/config/agents.json` (`repo_root`)
- `agent-core/registry.yaml` (`token_experiments` config path if updated)
- Root `README.md`, `docs/README.md`, `coder/README.md`, and doc links pointing at `coder/daily-coder-ecosystem/`

Re-run smoke:

```bash
cd agents/coding/daily-coder-ecosystem
pip install -e .
python -m unittest discover -s tests -v
daily-coder benchmark --baseline baselines/orchestration-v1.json --gate
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
```

Regenerate inventory baseline:

```bash
python ai_agents_repo/scripts/generate_path_consumer_inventory.py
```

## Without git

```powershell
Move-Item -Path coder\daily-coder-ecosystem -Destination daily-coder-ecosystem
```

Then restore the same file edits as above.

## Evidence to attach after rollback

- Daily Coder `python -m unittest discover -s tests -v` and benchmark gate exit code 0
- `import_daily_coder_agents.py --check` and `sync_ide_agents.py --check` exit code 0
- `python -m ai_agents_repo.validate --phase F0` exit code 0 (if layout maps restored consistently)
