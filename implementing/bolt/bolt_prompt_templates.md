# Bolt.new Prompt Templates for AgentNexus

Use these prompt templates in Bolt.new (`https://bolt.new`) to generate robust, clean applications in a single turn.

---

## 1. Full-Stack Agent Dashboard Prototype

```text
Build a modern, high-performance web dashboard for monitoring multi-agent runs in AgentNexus.

TECH STACK:
- React 18 + Vite + TypeScript
- Tailwind CSS + Lucide React icons
- Lightweight mock WebSocket client simulating real-time agent state updates

FEATURES:
1. Orchestrator Overview: Display status cards for the KEEP-6 orchestrators (deep-research, research-messenger, plan-prep, use-master, daily-coder, researcher).
2. Live Run Monitor: A real-time timeline showing phase progression (PLAN -> READY_TO_BUILD -> IMPLEMENT -> REVIEW -> ACCEPTANCE).
3. Token & Budget Gauge: Visual meters for token usage across profiles S, M, L, XL with warning at 70%, checkpoint at 80%, and hard stop at 90%.
4. Evidence Table: Searchable table displaying extracted claims with status badges (VERIFIED, SUPPORTED, UNKNOWN).
5. Dark/Light Mode: Modern clean dark-first engineering aesthetic with responsive layout.

Generate modular, fully functional components with TypeScript types and zero placeholder comments.
```

---

## 2. Interactive Data & Spec Viewer

```text
Build an interactive parameter and datasheet explorer for AgentNexus.

TECH STACK:
- React + Tailwind CSS
- Recharts for data visualization
- Lucide React icons

FEATURES:
1. File Drop Zone: Allow dragging and dropping JSON fact tables exported from AgentNexus.
2. Parameter Grid: Filterable and sortable grid displaying parameters, units, confidence scores, and provenance locators.
3. Conflict Highlighter: Dedicated tab flagging conflicting values detected across different sources.
4. Export: Button to export validated parameters back to formatted JSON or Markdown.
```
