# Ecosystem Compatibility

Emit exactly one handoff for each role in this canonical order. Use `NOT_APPLICABLE` with a concrete reason instead of omitting a role.

1. `Master` — objective, priority, dependencies, safe parallel branches, serial reasons, acceptance gates.
2. `Planner` — task DAG, owners, conflicts and resources, prerequisites, validation order.
3. `Worker` — bounded outcome, constraints, affected paths and interfaces, forbidden scope, completion evidence.
4. `Reviewer` — independent risks, invariants, unfavorable checks, reconstruction evidence, rejection criteria.
5. `Test` — semantic requirements, falsifiable assertions, negatives, coverage gaps, mutation checks.
6. `Tester` — authoritative commands, environment, raw evidence, freshness, coincidental-green threats.
7. `Question` — smallest unresolved decision-critical questions and authoritative answer source.
8. `Idea` — alternatives, trade-offs, assumptions, reversibility, falsification, selection criteria.
9. `Debug` — symptoms, competing hypotheses, discriminating probes, controls, stop conditions.
10. `Integration` — boundary contracts, timing and order, lifecycle, compatibility, observability, failure propagation.
11. `CARLA` — API and version, world lifecycle, synchronization, ports and resources, actors, sensors, Traffic Manager, reproduction.
12. `Scenario` — schema meaning, compatibility, producers and consumers, migrations, behavioral negatives.
13. `HMI` — state meaning, warning priority, stale or unknown behavior, accessibility, codec and transport constraints.
14. `Performance` — baseline, environment, workload validity, repetitions, distributions, contamination.
15. `ROS2` — types, units, frames, timestamps and clocks, QoS, lifecycle, launch, compatibility and failure behavior.
16. `Environment` — host and namespace, paths, versions, dependencies, resources, freshness and preflight.
17. `GUI` — parity, accessibility, state flow, IPC and security, fallback, packaging, evidence needs.

## Handoff contract

Every handoff contains:

```json
{
  "role": "canonical role name",
  "disposition": "RECOMMENDED|DEFER|DO_NOT_ADOPT|NOT_APPLICABLE",
  "reason": "...",
  "recommendation_ids": [],
  "fact_ids": [],
  "objective": "...",
  "constraints": [],
  "inputs": [],
  "required_outputs": [],
  "acceptance_criteria": [],
  "dependencies": [],
  "risks": [],
  "recommended_action": "..."
}
```

Handoffs are proposals only. Research agents never execute, authorize, dispatch, or imply completion of them. A `NOT_APPLICABLE` handoff still includes all fields, with empty arrays where appropriate and a reason explaining why the role adds no decision value.
