# Token-efficiency experiments (Daily Coder)

Feature flags for this package live under `config/`. Full cross-repo guide:

**[docs/ide-agents/token-efficiency-experiments.md](../../docs/ide-agents/token-efficiency-experiments.md)**

Quick reference:

| Flag / field | File | Default |
|--------------|------|---------|
| `documentation_curator_after_document` | `config/token_experiments.json` | `false` |
| `early_stop_min_cards` | `config/budgets.json` (per profile; **M** pins `2`) | `2` if omitted |
