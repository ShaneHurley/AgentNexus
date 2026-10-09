# VS Code: AgentNexus Integration Guide

This guide covers setting up **AgentNexus** inside **Visual Studio Code**, utilizing **GitHub Copilot Chat**, **Continue.dev**, and native terminal workflows.

---

## 1. GitHub Copilot Agent Projections

VS Code Copilot supports agent files placed in `.github/agents/`. AgentNexus automatically projects all 41 agents into this directory with full YAML frontmatter, tool declarations, and handoff rules:

```bash
# Verify or regenerate projections
python agents/ide/scripts/sync_ide_agents.py
```

### Accessing Agents in Copilot
1. Open the GitHub Copilot Chat panel (`Ctrl + Cmd + I` on macOS or `Ctrl + Alt + I` on Windows/Linux).
2. Click the **Agents dropdown** at the top of the chat panel.
3. Select one of the user-facing orchestrators:
   - `deep-research`
   - `research-messenger`
   - `plan-prep`
   - `use-master`
   - `daily-coder`
   - `researcher`

### Handoffs & Human Gates (`send: false`)
In Copilot projections, sequential transitions (e.g. `plan-prep` $\rightarrow$ `use-master` $\rightarrow$ `daily-coder`) use `send: false`. This creates a **soft human approval gate**: Copilot drafts the transition packet, but you must click send or edit the prompt before dispatching the next phase.

---

## 2. Workspace Instructions (`.github/copilot-instructions.md`)

To enforce repository rules across all standard Copilot chats:
```bash
cp implementing/vscode/copilot-instructions.md .github/copilot-instructions.md
```

This ensures Copilot adheres to KEEP-6 boundaries, prevents unauthorized direct file editing during research, and points developers to `ide-bridge`.

---

## 3. Zero-Cost Free-Tier AI in VS Code via Continue.dev

For developers seeking to run free-tier models (DeepSeek V3, DeepSeek R1, Gemini 2.0 Flash, Ollama) directly inside VS Code without paying for Copilot subscriptions:

1. Install the **Continue** extension from the VS Code Marketplace (`Continue.continue`).
2. Copy [`continue_config.json`](./continue_config.json) to your Continue configuration:
   - macOS: `~/.continue/config.json`
   - Windows: `%USERPROFILE%\.continue\config.json`
   - Linux: `~/.continue/config.json`
3. Add your free API keys for Google Gemini (from Google AI Studio) or DeepSeek.

---

## 4. Audited Writes via VS Code Integrated Terminal

To execute audited code changes and tests:
```bash
# Ensure bridge is installed
pip install -e agents/ide/bridge

# Execute mutating run
ide-bridge daily-coder run --request "Implement user auth route" --profile M

# Review the plan diff, then approve:
ide-bridge daily-coder approve --run-id <run-id> --plan-hash <hash>
```
