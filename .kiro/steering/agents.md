# AgentNexus — Kiro Agent Roster & Rules

## Project overview

This is the **AgentNexus** monorepo: an evidence-first research and artifact-driven coding system.
Canonical agent definitions live in `agents/ide/canonical/`. This steering file makes them available in Kiro.

**Do not edit agent projections directly.** The SSOT is `agents/ide/canonical/`.
To regenerate all IDE projections run: `python agents/ide/scripts/sync_ide_agents.py`

---

## User-facing orchestrators (invoke these)

| Slash | Agent | Purpose |
|-------|-------|---------|
| `/deep-research` | deep-research | Eight-phase evidence research; sole parent of lane subagents |
| `/research-messenger` | research-messenger | ASSEMBLE / ECOSYSTEM / COMBINED packets; exactly 17 handoffs |
| `/plan-prep` | plan-prep | Planning context report (Glean-first when MCP configured) |
| `/use-master` | use-master | Master DAG dispatch + ide-bridge; no direct file edits |
| `/daily-coder` | daily-coder | Bridge-only parent — `ide-bridge daily-coder` for mutating runs |
| `/researcher` | researcher | Read-only codebase recon (Daily Coder researcher projection) |

There is **no** `/daily`, `/career`, or seventh orchestrator.

---

## Authority tiers

| Tier | Agents | Can edit files? |
|------|--------|-----------------|
| read-only | deep-research, research-messenger, plan-prep, researcher, all lane scouts | No |
| bridge-parent | use-master, daily-coder | Via `ide-bridge` only |
| delegate-only | All other specialists | Never user-invocable |

**Master never expands user authority.** Mutating, audited work always goes through `ide-bridge daily-coder` (PolicyGateway + plan_hash).

---

## Bridge CLI (audited writes)

```bash
ide-bridge doctor
ide-bridge daily-coder run --request "<mission>" --repo <path> [--live]
ide-bridge daily-coder approve <run_id>
ide-bridge daily-coder resume <run_id>
```

Exit codes: `0` COMPLETE · `1` SIMULATED · `2` PARTIAL · `3` BLOCKED · `4` policy denied.
Default is mock; pass `--live` only with documented gates.

---

## Delegate-only specialists (do not invoke directly)

These are dispatched only by parent orchestrators:

`master-orchestrator` · `planner` · `brainstormer` · `sizer` · `charter-planner` · `intake-clarifier`
`implementer` · `test-designer` · `test-author` · `test-executor` · `code-reviewer` · `alignment-checker`
`failure-diagnostician` · `skill-curator` · `documenter` · `frontier-advisor` · `plan-reviewer`
`source-scout` · `citation-verifier` · `principal-director` · `report-composer` · `adversarial-skeptic`
`evidence-extractor` · `internal-authority-scout` · `official-standards-scout` · `academic-evidence-scout`
`practitioner-implementation-scout` · `failure-unfavorable-scout` · `alternatives-analogy-scout`
`research-planner` · `research-messenger` · `targeted-gap-researcher` · `evidence-integrator`
`adversarial-evidence-reviewer` · `recommendation-scorer`

---

## Key file locations

| What | Path |
|------|------|
| Canonical agent definitions | `agents/ide/canonical/` |
| Kiro steering (this file) | `.kiro/steering/agents.md` |
| Kiro agent skills | `.kiro/steering/` |
| Cursor projections | `.cursor/agents/` |
| Claude Code projections | `.claude/agents/` |
| GitHub Copilot projections | `.github/agents/` |
| IDE bridge | `agents/ide/bridge/` |
| Shared skills | `agents/shared/skills/` |
| Architecture docs | `docs/architecture/` |
| IDE agent guide | `docs/ide-agents/ide-agent-pack.md` |
