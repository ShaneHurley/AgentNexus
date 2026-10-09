# JetBrains IDEs (IntelliJ, PyCharm, WebStorm & Junie): AgentNexus Guide

This guide covers deploying **AgentNexus** inside **JetBrains IDEs** (PyCharm, IntelliJ IDEA, WebStorm) using **JetBrains Junie**, **JetBrains AI Assistant**, and the **Continue.dev** plugin.

---

## 1. JetBrains Junie Setup (`.junie/guidelines.md`)

**Junie** is JetBrains' autonomous coding agent. It reads repository rules and workflows from `.junie/guidelines.md`.

Install the guidelines:
```bash
mkdir -p .junie
cp implementing/jetbrains/junie_guidelines.md .junie/guidelines.md
```

---

## 2. JetBrains AI Assistant Prompt Library

To add the KEEP-6 orchestrators to JetBrains AI Assistant:
1. Open **Settings / Preferences -> Tools -> AI Assistant -> Prompt Library**.
2. Click `+` to add custom prompts for:
   - **Deep Research**: Paste the canonical body from `agents/ide/canonical/deep-research.md`.
   - **Plan Prep**: Paste the canonical body from `agents/ide/canonical/plan-prep.md`.
   - **Researcher**: Paste the canonical body from `agents/ide/canonical/researcher.md`.

---

## 3. Free-Tier Models in JetBrains via Continue Plugin

1. Install the **Continue** plugin from the JetBrains Marketplace.
2. Copy `implementing/vscode/continue_config.json` to `~/.continue/config.json`.
3. Use Gemini 2.0 Flash (free via Google AI Studio), DeepSeek R1, or local Ollama directly inside PyCharm or IntelliJ IDEA at \$0 cost.
