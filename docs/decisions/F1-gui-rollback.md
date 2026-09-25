# F1 rollback: `gui/` → `agent-dashboard/`

**Phase:** F1 (physical GUI folder rename)  
**Owner:** migration PR author  
**Max rollback time:** ~5 minutes (single folder rename + path/doc revert)

## When to roll back

- CI `GUI` / Agent Dashboard smoke step fails after merge and cannot be fixed forward quickly.
- Downstream automation still hard-codes `agent-dashboard/` as a **directory** (not PyPI name).

## Rollback (git checkout with history)

From repository root:

```bash
git mv gui agent-dashboard
```

Then revert F1 commits that touched:

- `.github/workflows/ci.yml` (`working-directory: gui` → `agent-dashboard`)
- `ai_agents_repo/src/ai_agents_repo/paths.py` (`gui_root()` legacy map → `agent-dashboard` if rolling back before dual-map policy)
- Root `README.md`, `docs/README.md`, `.env.example`, and doc links under `docs/` pointing at `gui/`

Re-run smoke:

```bash
cd agent-dashboard
pip install -e ../daily-coder-ecosystem
pip install -e .
python -m unittest discover -s tests -v
```

Regenerate inventory baseline:

```bash
python ai_agents_repo/scripts/generate_path_consumer_inventory.py
```

## Without git

```powershell
Rename-Item -Path gui -NewName agent-dashboard
```

Then restore the same file edits as above.

## Evidence to attach after rollback

- Smoke unittest exit code 0
- `python -m ai_agents_repo.validate --phase F0` exit code 0 (if layout maps restored consistently)
