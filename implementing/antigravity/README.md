# Google Antigravity: Unified IDE & Agent View Integration

This guide provides instructions and configuration files for running **AgentNexus** inside **Google Antigravity IDE** and its integrated **Agent View**.

---

## 1. Overview of Antigravity Architecture

Google Antigravity pairs an AI-native code editor with a persistent **Agent View** sidebar. Antigravity natively supports:
- **Autonomous Multi-Turn Execution**: Long-running goal pursuit via `/goal` and systematic planning via `/plan`.
- **Subagent Hierarchies**: Dynamic subagent invocation (`invoke_subagent`, `define_subagent`, `send_message`) with independent conversation contexts.
- **Sandboxed Terminal Execution**: Runs commands in a secure local sandbox (`BypassSandbox: false`), preventing accidental network leakage and safeguarding your environment.
- **Interactive Generative UI & Artifacts**: Rich markdown artifacts, mermaid diagrams, and live interactive HTML widgets.
- **Customization System**: Skill libraries, system rules (`<user_rules>`), and MCP tool servers.

By mapping AgentNexus into Antigravity, you get full access to **Gemini 2.0 / 3.x Flash and Pro** with 1M+ token context windows at **zero cost** for interactive development.

---

## 2. Setting Up Antigravity Rules

Antigravity automatically reads workspace rules from files placed in the project root or `.gemini/rules/`.

To configure Antigravity for AgentNexus:
1. Ensure the root [`AGENTS.md`](../../AGENTS.md) is present (Antigravity automatically injects this into the system prompt).
2. For stricter rule enforcement, copy [`rules.md`](./rules.md) to your workspace or user rules directory:
   ```bash
   mkdir -p .gemini/rules
   cp implementing/antigravity/rules.md .gemini/rules/agentnexus.md
   ```

---

## 3. Registering AgentNexus Subagents in Antigravity

Antigravity allows the parent agent to spawn specialized subagents. You can define the AgentNexus KEEP-6 orchestrators and key delegates using the definitions in [`subagents.json`](./subagents.json).

### User-Facing Orchestrator Subagents

| Subagent | Role | Antigravity TypeName | Purpose |
|---|---|---|---|
| **deep-research** | Lead Evidence Researcher | `deep-research` | Eight-phase deep research; sole invoker of research scouts |
| **research-messenger** | Research Packet Assembler | `research-messenger` | Generates 17-handoff structured packets without doing ad-hoc research |
| **plan-prep** | Architecture & Repo Context Scout | `plan-prep` | Gathers Glean/repo context before master planning |
| **use-master** | Master Mission Dispatcher | `use-master` | Formulates Master DAGs; coordinates specialists |
| **daily-coder** | Audited Codebase Operator | `daily-coder` | Dispatches mutating changes through `ide-bridge` |
| **researcher** | Read-Only Codebase Explorer | `researcher` | Bounded read-only investigation and recon |

---

## 4. Bridging Personal & Shared Skills

AgentNexus ships on-demand skills under [`agents/shared/skills/`](../../agents/shared/skills/):
- **Personal Skills**: `career-tools` (`resume-tailor`, `interview-prep`, `opportunity-review`), `deadline-triage`, `lab-preflight`, `professor-email`, `study-hints`.
- **Shared Skills**: `claim-auditor`, `datasheet-extractor`, `structured-data-evaluator`, `visualization-specifier`, `writing-improver`.

To make these skills accessible directly to Antigravity:
```bash
# Link shared skills to Antigravity local skills folder
mkdir -p ~/.gemini/antigravity/skills
ln -sfn "$(pwd)/agents/shared/skills/shared/writing-improver" ~/.gemini/antigravity/skills/writing-improver
ln -sfn "$(pwd)/agents/shared/skills/shared/claim-auditor" ~/.gemini/antigravity/skills/claim-auditor
ln -sfn "$(pwd)/agents/shared/skills/shared/visualization-specifier" ~/.gemini/antigravity/skills/visualization-specifier
```

---

## 5. Executing Audited Writes via `ide-bridge`

In Antigravity's Agent View, the model has write tools, but according to AgentNexus architectural doctrine, **mutating engineering runs must be audited by Daily Coder's PolicyGateway**.

Run mutating commands through the included bridge helper:
```bash
# Check runtime health
python implementing/antigravity/antigravity_bridge.py doctor

# Run a guarded daily-coder task
python implementing/antigravity/antigravity_bridge.py run --request "Add unit tests for payment helper" --repo .

# Scaffold planning context
python implementing/antigravity/antigravity_bridge.py plan-prep
```

This ensures `IDE_BRIDGE_ACTIVE=1` is exported and all actions are recorded in the Daily Coder ledger.
