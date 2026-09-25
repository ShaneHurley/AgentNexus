# ai-agents-repo

Installable layout control plane for the **ai_agents** monorepo (F0 migration).

```bash
pip install -e ./agents/shared/ai_agents_repo
python -m ai_agents_repo.validate --phase F0
pytest agents/shared/ai_agents_repo/tests -q
```

See `docs/decisions/ADR-REPO-LAYOUT-2026-09.md`.
