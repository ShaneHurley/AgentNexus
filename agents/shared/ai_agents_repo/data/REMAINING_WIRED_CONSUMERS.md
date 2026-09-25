# Remaining path consumers (F0c follow-up)

Critical path wired in F0:

- `agents/ide/scripts/sync_ide_agents.py`
- `agents/ide/scripts/import_daily_coder_agents.py`
- `agents/ide/scripts/import_rf_agents.py`
- `agents/ide/scripts/audit_prompt_bytes.py`
- `agents/ide/bridge/ide_bridge/dc_runner.py`

Regenerate full list:

```bash
python agents/shared/ai_agents_repo/scripts/generate_path_consumer_inventory.py
```

Filter baseline hits where `classification == "pending_wire"`.
