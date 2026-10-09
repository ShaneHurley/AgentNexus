# Cursor IDE: AgentNexus Integration Guide

This guide details how to configure and operate the full **AgentNexus** suite inside **Cursor IDE**.

---

## 1. How AgentNexus Operates in Cursor

Cursor provides three AI interaction modes:
1. **Agent Picker / `@` Agent Mentions**: Directly invoke any of the KEEP-6 orchestrators or specialized delegates.
2. **Composer**: Multi-file editing and terminal execution.
3. **Cursor Hooks (`.cursor/hooks.json`)**: Pre-tool and pre-command lifecycle scripts that provide **soft least-privilege** enforcement (blocking read-only agents from mutating files).

---

## 2. Generating Projections & Installing Hooks

Cursor discovers agents under `.cursor/agents/`. These are automatically projected from canonical sources:

```bash
# 1. Sync canonical agents into .cursor/agents/
python agents/ide/scripts/sync_ide_agents.py

# 2. Run the automated hooks setup script
bash implementing/cursor/hooks_setup.sh
```

This populates:
- `.cursor/agents/` (41 agents with frontmatter deny-lists).
- `.cursor/hooks.json` (hooks configuration).
- `.cursor/hooks/` (enforcement scripts).

---

## 3. The KEEP-6 User-Facing Orchestrators in Cursor

Open the agent dropdown in Cursor Chat or type `@<agent-name>`:

| Orchestrator | Cursor Trigger | Behavior & Authority |
|---|---|---|
| **deep-research** | `@deep-research` or `/deep-research` | **Read-Only**: Conducts 8-phase evidence research; delegates to scouts. Never edits files. |
| **research-messenger** | `@research-messenger` | **Read-Only**: Formats scored evidence packets into 17 standard handoffs. |
| **plan-prep** | `@plan-prep` | **Read-Only**: Surveys repo, configs, and documentation prior to master planning. |
| **use-master** | `@use-master` | **Master Dispatcher**: Generates execution DAG; delegates atomic tasks to specialists. |
| **daily-coder** | `@daily-coder` | **Audited Coding**: Dispatches mutating tasks to `ide-bridge daily-coder`. |
| **researcher** | `@researcher` | **Read-Only**: Bounded codebase recon on symbols, files, and call graphs. |

All other 35 agents (scouts, reviewers, implementers, evaluators) are **delegate-only**.

---

## 4. Cursor Composer & Mutating Work

When performing code modifications:
- For pack development, Cursor Chat/Composer can edit directly with user oversight.
- For audited Daily Coder / Research Forge runs, execute via the bridge in the integrated terminal:
  ```bash
  ide-bridge daily-coder run --request "Refactor auth middleware" --profile M
  ```
  The bridge sets `IDE_BRIDGE_ACTIVE=1`, allowing the action to pass Cursor's soft hooks.

---

## 5. Token Efficiency in Cursor

Cursor sessions accumulate chat history quickly. Follow these guidelines:
- **Use `@agent` selectively**: Tag `@researcher` for targeted searches instead of pasting whole files.
- **Reference symbols instead of files**: Type `@SymbolName` to pull only the definition rather than an entire 2,000-line module.
- **Start fresh chats per phase**: When transitioning from Research to Plan or Plan to Implement, click **New Chat** (Cmd+N / Ctrl+N) and pass only the summary state packet.
