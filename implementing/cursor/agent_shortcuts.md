# Cursor Agent Shortcuts & Command Palette Quick Reference

This cheat sheet summarizes the fastest ways to navigate, invoke, and control AgentNexus agents in Cursor.

---

## 1. Quick Invocations

| Action | Shortcut / Input | Target Agent |
|---|---|---|
| Deep Architecture Research | `@deep-research` | Runs 8-phase evidence research |
| Assemble Hand-off Report | `@research-messenger` | Generates 17 structured handoffs |
| Repo Recon Before Planning | `@plan-prep` | Summarizes existing context |
| Master Mission Execution | `@use-master` | Builds task DAG and dispatches specialists |
| Audited Coding Run | `@daily-coder` | Prepares plan and dispatches `ide-bridge` |
| Fast Code Recon | `@researcher` | Bounded read-only symbol lookup |

---

## 2. Composer & Chat Hotkeys (macOS / Linux / Windows)

| Action | macOS | Windows / Linux | Purpose in AgentNexus |
|---|---|---|---|
| **Open Chat** | `Cmd + L` | `Ctrl + L` | Quick queries and read-only recon |
| **Open Composer** | `Cmd + I` | `Ctrl + I` | Multi-file code generation and editing |
| **Full-Screen Composer** | `Cmd + Shift + I` | `Ctrl + Shift + I` | Architecture and deep refactor work |
| **New Chat Session** | `Cmd + N` | `Ctrl + N` | **Crucial**: Reset context window between phases |
| **Reference File** | `@filename` | `@filename` | Pull specific file into context |
| **Reference Symbol** | `@SymbolName` | `@SymbolName` | Pull specific function/class (saves tokens) |
| **Reference Docs** | `@Docs` | `@Docs` | Reference framework documentation |

---

## 3. Workflow Recipes

### Recipe A: Investigating a Bug
1. Press `Cmd + L` to open Cursor Chat.
2. Type: `@researcher Locate where PolicyGateway checks tool allowlists and verify error handling.`
3. Review the read-only findings.

### Recipe B: Executing an Audited Feature
1. Open Chat (`Cmd + L`).
2. Type: `@plan-prep Analyze existing budget thresholds in config/budgets.json.`
3. Review context, then switch to terminal (`Ctrl + ~`).
4. Run:
   ```bash
   ide-bridge daily-coder run --request "Update early stop threshold for profile M" --profile M
   ```
5. Inspect the generated plan diff, then approve:
   ```bash
   ide-bridge daily-coder approve --run-id <run-id> --plan-hash <hash>
   ```
