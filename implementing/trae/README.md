# Trae IDE: AgentNexus Integration Guide

This guide covers configuring and running **AgentNexus** inside **Trae IDE** (the adaptive AI IDE offering free access to Claude Sonnet and DeepSeek models).

---

## 1. Trae IDE Modes & AgentNexus Mapping

Trae features two primary interaction modes:
- **Chat Mode**: Context-aware Q&A, code explanation, and architecture review. Maps to `deep-research`, `plan-prep`, `researcher`, and `research-messenger`.
- **Builder Mode**: Multi-file autonomous code generation, project scaffolding, and terminal command execution. Maps to `use-master` and `daily-coder`.

---

## 2. Setting Up Trae Rules (`.trae/rules/project_rules.md`)

Trae loads workspace rules from `.trae/rules/project_rules.md`:

```bash
mkdir -p .trae/rules
cp implementing/trae/trae_rules.md .trae/rules/project_rules.md
```

---

## 3. Custom Agents in Trae

Trae allows creating Custom Agents in the Agent panel:
1. Click **Agent Settings -> Create Agent**.
2. Create agents for the **KEEP-6** roster:
   - **`deep-research`**: Enable *Read File*, *Search Codebase*, *Web Search*. Disable *Edit File* and *Terminal*.
   - **`plan-prep`**: Enable *Read File*, *Search Codebase*, *MCP Tools*. Disable *Edit File*.
   - **`daily-coder`**: Enable *Read File*, *Edit File*, *Terminal* (configured to invoke `ide-bridge`).

---

## 4. Audited Execution via Terminal

In Builder Mode, instruct Trae to run mutating actions via `ide-bridge`:
```bash
ide-bridge daily-coder run --request "Add validation to user schema" --profile M
```
