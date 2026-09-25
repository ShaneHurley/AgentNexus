# Research Basis

The design incorporates recurring findings from the research corpus. Full cards and gap-prioritized additions:

**[`../../docs/research/sources/`](../../docs/research/sources/README.md)**

Authoritative build contract:

**[`../../docs/architecture/agent_orchestration_master_spec.md`](../../docs/architecture/agent_orchestration_master_spec.md)** Part D

## Recurring findings (short)

- Start with simple composable workflows; add autonomy only when it improves measured outcomes.
- Give tools clear names, bounded inputs, useful errors, and token-efficient responses.
- Repository instruction files should be concise and operational; oversized always-on context can reduce performance and increase cost.
- Plans and critical state must live outside model context and be re-injected.
- Research fan-out is useful only when lanes are independent and bounded — and only when it beats a strong single-agent baseline.
- Keep reasoning in the master; keep workers narrow, cheap, and read-only for recon.
- Skills primarily stabilize procedures; poor granularity, brittle assumptions, retrieval noise, and accretion create negative transfer.
- Skill updates need issue memory, adaptive edit scope, verifier-grounded admission, pruning, and **human governance**.
- Independent review, deterministic checks, and execution evidence beat self-reported confidence.
- Escalate to frontier models only on a compressed decision brief, never on raw transcripts.
- Budgets and permissions are enforced in host code, not prompts.

Primary link list: [`../SOURCES.md`](../SOURCES.md).
