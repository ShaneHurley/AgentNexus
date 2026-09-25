# ide-bridge

Thin CLI that wraps **Daily Coder** and **Research Forge** console entry points. Sets `IDE_BRIDGE_ACTIVE=1` for child processes so IDE hooks can allow bridge-mediated work.

**Mock-by-default:** successful mock runs return exit code `1` (SIMULATED) unless `--no-mark-simulated` is passed on `run`. Live runs (`--live`) use RF/DC gates and return `0` only when the child CLI succeeds.

## Install (editable)

```bash
pip install -e agents/ide/bridge
```

## Commands

```text
ide-bridge doctor
ide-bridge plan-prep scaffold
ide-bridge daily-coder run --request "..." --repo <path> [--live] [--no-mark-simulated]
ide-bridge daily-coder approve <run_id>
ide-bridge daily-coder resume <run_id> [--live]
ide-bridge research-forge run --request <path-or-json> [--wave1] [--live] [--no-mark-simulated]
ide-bridge research-forge resume <run_id> [--answer CLQ-ID=value] [--live]
```

Do not reimplement Research Forge experiment gates or ledger logic in IDE chat — call this CLI instead.
