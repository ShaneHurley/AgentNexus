# Comparison protocol and results

Pending nine real tasks: three SMALL, three MEDIUM, three LARGE, mixed across code, research and documents. Write acceptance criteria before each run. Run each task with A (single strong agent), B (simpleIDE), and C (AgentNexus where applicable). The user judges acceptance. Record cost or tokens, time, dispatch count, and real reviewer findings. Do not substitute synthetic tasks or inferred costs for observed runs.

| Task | Size/type | Criteria | Arm | Accepted | Cost/tokens | Time | Dispatches | Real findings | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 1–9 | pending | pending | A/B/C | pending | pending | pending | pending | pending | pending |

After results: compare cost per accepted task by size. If B does not beat A, trim the process for that size or use one agent. If the MEDIUM reviewer finds a real issue fewer than roughly one in five times, drop it there. If independent tests add no catches, limit them to LARGE. Offer unused lessons after 90 days for pruning. Treat close differences as ties.

The AgentNexus keep/port/retire audit follows this comparison. No components are retired before the evidence is collected.

## Recording after the November 11 repair

Freeze each task's criteria and starting revision before A/B/C; use isolated stores and controlled shared-memory carryover for each arm, and vary arm order. Preserve failed/abandoned attempts in denominators. A result record is evidence only. Record an actual user's decision before `task close ... --by user --refs <decision evidence>`; assistant closure and legacy-unverified outcomes are separate. The actor flag alone cannot prove consent.

Record actual elapsed time, usage source and token/cost coverage with stats; incomplete coverage is unknown, not zero or a complete cost total. Pending dispatch intents are not observed launches. CLI fixtures and the small qualification exercises are not comparison tasks. No nine-task outcomes, user acceptance decisions, comparative savings or reviewer catch rates have been collected during this repair.

Three tasks per size are a pilot, insufficient to establish a roughly one-in-five reviewer catch rate. Report uncertainty, treat close results as ties, and expand only when the decision depends on the difference. The keep/port/retire decision remains pending actual comparison evidence.
