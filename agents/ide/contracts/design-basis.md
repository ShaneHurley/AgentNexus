# Design Basis

The workflow adapts established agent-system patterns without treating them as proof of effectiveness:

- **ReAct:** alternate evidence gathering and reasoning instead of relying on unsupported internal reasoning.
- **AutoGen and CAMEL:** use specialized roles with bounded objectives and explicit message contracts.
- **MetaGPT and ChatDev:** standardize handoffs, artifacts, review, and test responsibilities.
- **AgentBench:** evaluate trajectories and tool behavior, not answer fluency alone.
- **Glean Agent Builder:** use ordered workflow steps, branches, reusable sub-agents, per-step memory, targeted outputs, Preview, Debug, drafts, and versions.

Operational consequences:

- Glean Workflow steps are ordered. Evidence lanes are logically independent; concurrency requires runtime trace evidence.
- The parent alone invokes subagents. Subagents never invoke one another.
- Large searches remain isolated in lanes; compact ledgers return to the parent.
- Tool and payload ceilings require bounded work, lineage deduplication, and explicit `PARTIAL` status.
- Narrow read-only tools and resources reduce accidental authority and improve reliability.
- Preview, Debug, golden evaluations, and gradual promotion are required before broad sharing.

Primary design references:

- https://docs.glean.com/agents/how-agents-work
- https://docs.glean.com/agents/concepts/flow
- https://docs.glean.com/agents/concepts/memory
- https://docs.glean.com/agents/concepts/agent-builder
- https://docs.glean.com/agents/create-powerful-agent
- https://arxiv.org/abs/2210.03629
- https://arxiv.org/abs/2308.08155
- https://arxiv.org/abs/2303.17760
- https://arxiv.org/abs/2308.00352
- https://aclanthology.org/2024.acl-long.810/
- https://openreview.net/forum?id=zAdUB0aCTQ

These references explain the design lineage. They do not establish that this particular workflow improves repository outcomes; that remains an empirical question for the evaluation suite.
