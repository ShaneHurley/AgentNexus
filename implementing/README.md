# AgentNexus: Universal IDE & Worker Implementation Hub

Welcome to the **AgentNexus Implementation Hub**. This directory provides production-ready configuration files, prompt templates, rule sets, execution bridges, and step-by-step guides for deploying AgentNexus's **KEEP-6 user-facing orchestrators**, **35 delegate specialists**, and **10 browser agent families** across every modern IDE, AI worker, and browser platform.

---

## Supported IDEs & Workers

| Folder | Platform / Environment | Primary Agent Surface | Key Strengths / Role |
|---|---|---|---|
| [`antigravity/`](./antigravity/) | **Google Antigravity IDE & Agent View** | Built-in Subagents, Skills, Slash Commands | Native integration, sandboxed terminal, 1M+ token context via Gemini |
| [`cursor/`](./cursor/) | **Cursor IDE** | `.cursor/agents/`, `.cursor/rules/`, Hooks | Agent picker, `@agent` mentions, soft least-privilege hooks, Composer |
| [`vscode/`](./vscode/) | **VS Code & GitHub Copilot** | `.github/agents/*.agent.md`, Continue, Cline | Copilot agent dropdown, `@copilot` agent participant, workspace rules |
| [`windsurf/`](./windsurf/) | **Codeium Windsurf IDE** | Cascade AI, `.windsurfrules`, Workflows | Context pinning, zero-redundancy reading, Cascade workflows |
| [`kimi/`](./kimi/) | **Moonshot Kimi (Web & API)** | Web Chat, K1.5 / K1 preview, 2M context | Massive context document analysis, large codebases, research extraction |
| [`deepseek/`](./deepseek/) | **DeepSeek (V3 & R1 Reasoning)** | Web Chat, R1 Prompt Packs, API | Deep chain-of-thought adversarial review, plan verification, low-cost API |
| [`glm/`](./glm/) | **Zhipu AI GLM (GLM-4 & BigModel)** | Web Chat, BigModel API | Structured fact tables, bilingual reasoning, documentation curation |
| [`bolt/`](./bolt/) | **StackBlitz Bolt.new** | Web-based Full-Stack Sandbox | Rapid interactive MVP prototyping, instant sandboxed execution |
| [`kirocrew/`](./kirocrew/) | **Kiro Crew & CrewAI** | `kirocrew` CLI + CrewAI Python Scripts | Persistent background agent workspace & hierarchical multi-agent teams |
| [`claude_code/`](./claude_code/) | **Anthropic Claude Code** | Terminal CLI, `.claude/agents/` | Slash commands (`/agents`), compact tool-gated terminal execution |
| [`cline_roo_code/`](./cline_roo_code/) | **Cline & Roo Code Extensions** | Custom Modes (`.roomodes`, `.clinerules`) | Strict role-based tool allowlists, autonomous terminal execution |
| [`zed/`](./zed/) | **Zed Editor AI Assistant** | Slash Commands (`/file`, `/prompt`), Rules | High-speed native editor assistant, focused file transformations |
| [`aider/`](./aider/) | **Aider CLI** | Terminal Pair Programmer (`--architect`) | Git-aware diffing, two-model architect/editor workflow |
| [`trae/`](./trae/) | **Trae IDE** | Builder & Chat Modes, Custom Agents | Free access to Claude Sonnet & DeepSeek models |
| [`jetbrains/`](./jetbrains/) | **JetBrains IDEs & Junie** | `.junie/guidelines.md`, AI Assistant, Continue | IntelliJ / PyCharm autonomous agent & prompt library |
| [`openhands/`](./openhands/) | **OpenHands (OpenDevin)** | `.openhands/microagents/` | Open-source Docker-sandboxed autonomous software engineer |
| [`lovable_v0/`](./lovable_v0/) | **Lovable.dev & Vercel v0** | Web UI & Full-Stack Builders | Free-tier rotation backup for Bolt.new UI prototyping |
| [`browser_agents/`](./browser_agents/) | **Browser Agents & Web Chats** | Paste Packs, 10 Families, 60+ Variants | Zero-install copy-paste packs for ChatGPT, Claude.ai, Gemini, Kimi, etc. |

---

## Free-Tier AI Optimization

Make sure to read the master guide:
👉 **[`FREE_TIER_AGENT_CHAINING_GUIDE.md`](./FREE_TIER_AGENT_CHAINING_GUIDE.md)**

This document details how to daisy-chain the free tiers of Google Gemini (Antigravity), DeepSeek R1, Kimi (2M context), Bolt.new, Windsurf, Zhipu GLM, and Claude into an automated, multi-stage pipeline that delivers enterprise-grade software and research at **\$0.00** total cost.

---

## Core Architecture Principles (KEEP-6)

1. **User-Facing Orchestrators (KEEP-6)**:
   - Direct user invocation is strictly limited to six orchestrators: `deep-research`, `research-messenger`, `plan-prep`, `use-master`, `daily-coder`, and `researcher`.
   - All other 35 roles are **delegate-only** specialists invoked by these parents.
2. **Context Slicing (`ROLE_INPUTS`)**:
   - Never forward raw transcripts across agents. Slice only the required prompt packet and task anchor to prevent token explosion.
3. **Audited Mutating Writes**:
   - File edits and test executions that mutate the workspace must go through `ide-bridge` (setting `IDE_BRIDGE_ACTIVE=1`) to be audited and guarded by Daily Coder's `PolicyGateway`.
