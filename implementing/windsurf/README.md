# Codeium Windsurf: AgentNexus Integration Guide

This guide details how to configure and run **AgentNexus** inside **Codeium Windsurf IDE** using **Cascade AI**.

---

## 1. Windsurf & Cascade AI Architecture

Windsurf features **Cascade**, an agentic AI engine that operates in two primary modes:
- **Chat Mode**: Read-only exploration, explanation, and architectural planning.
- **Write Mode**: Autonomous file editing, command execution, and multi-file refactoring.

Windsurf offers a generous free tier with recurring monthly credits. To maximize these credits without running out, AgentNexus provides strict context-pinning rules and structured workflows.

---

## 2. Configuring `.windsurfrules`

Windsurf automatically reads system rules from `.windsurfrules` in the root of the workspace.

To install the AgentNexus rules:
```bash
cp implementing/windsurf/windsurfrules.md .windsurfrules
```

Key guarantees enforced by `.windsurfrules`:
1. **KEEP-6 User-Facing Orchestrator Alignment**: Cascade adopts the persona of the requested orchestrator (`deep-research`, `plan-prep`, `use-master`, `daily-coder`, `researcher`, `research-messenger`).
2. **Preventing Re-Reading Bleed**: Cascade is instructed to avoid re-reading entire modules across subsequent turns, preserving your monthly free credits.
3. **Audited Mutating Work**: Cascade routes complex mutating changes through `ide-bridge daily-coder` or explicit user approval.

---

## 3. Workflows in Windsurf

Windsurf Cascade supports reusable workflow prompts. Pre-built workflows are provided in [`workflows/`](./workflows/):
- **Deep Research Workflow** (`workflows/deep_research_workflow.md`): Executes 8-phase research in Cascade Chat mode.
- **Daily Coder Workflow** (`workflows/daily_coder_workflow.md`): Formulates an artifact plan, requests approval, and triggers `ide-bridge`.

---

## 4. Token & Credit Thrift in Windsurf

To make your free Windsurf credits last throughout the month:
1. **Use Chat Mode for Recon**: Never use Write Mode for exploratory questions or searches. Chat Mode consumes fewer credits.
2. **Pin Files Manually**: Click the `+` icon or type `/pin <file>` only for the specific 1-2 files being modified, rather than indexing the entire project tree into Cascade's prompt.
3. **Reset Cascade Sessions**: Open a new Cascade thread (`Cmd + N`) after completing a discrete task. Retaining a 20-turn conversation burns exponential credits on every subsequent message.
