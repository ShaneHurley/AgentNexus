# Project agents (IDE)

This repository ships a full roster of **delegate-only** specialists plus **six user-facing orchestrators**. Invoke the six below directly; parents delegate everything else.

**Operator guide (per-IDE setup):** [`agents/ide/README.md`](agents/ide/README.md)  
**Architecture:** [`docs/ide-agents/ide-agent-pack.md`](docs/ide-agents/ide-agent-pack.md)  
**Personal skills:** [`docs/personal-skills/README.md`](docs/personal-skills/README.md)

## User-facing agents (invoke these)

| Agent | Purpose |
|-------|---------|
| **deep-research** | Eight-phase evidence research; sole invoker of lane subagents |
| **research-messenger** | ASSEMBLE / ECOSYSTEM / COMBINED packets; exactly 17 handoffs |
| **plan-prep** | Planning context report (Glean-first when MCP configured) |
| **use-master** | Master DAG dispatch + bridge; no native file edits |
| **daily-coder** | Bridge-only parent — `ide-bridge daily-coder` for mutating runs |
| **researcher** | Read-only codebase recon (Daily Coder researcher projection) |

There is **no** `/daily`, `/career`, or seventh orchestrator. Student/career workflows use on-demand skills in [`agents/shared/skills/`](agents/shared/skills/).

## Where files live

| IDE | Path |
|-----|------|
| Cursor | `.cursor/agents/<name>.md` (and user skills under `~/.cursor/skills`) |
| VS Code Copilot | `.github/agents/<name>.agent.md` — Agents dropdown |
| Claude Code | `.claude/agents/<name>.md` — `/agents` |

Generated from `agents/ide/canonical/` — do not edit projections by hand. Run `python agents/ide/scripts/sync_ide_agents.py` after canonical changes.

## Audited writes

Use **`ide-bridge`** (see [`agents/ide/bridge/README.md`](agents/ide/bridge/README.md)). IDE hooks assist only; PolicyGateway remains authoritative. Personal career writes use `personal-store` with visible diff + confirmation (soft-confirm), not the engineering gateway.
