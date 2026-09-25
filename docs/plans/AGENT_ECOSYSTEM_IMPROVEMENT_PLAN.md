# Agent Ecosystem Improvement Plan

## 1. Goal

Reduce duplicated agent behavior, make shared delegates usable across IDE and runtime orchestration, improve data and style workflows, and reorganize the repository so a future GitHub visitor can understand it quickly without breaking current entry points.

## 2. Current problems

### Duplication

Planning, plan review, source reading, summarization, style transformation, test design, execution verification, and documentation appear in multiple surfaces with different names.

### Authority ambiguity

Browser roles, IDE projections, runtime roles, skills, and deterministic services are adjacent but not always visibly distinguished.

### Data-analysis risk

A single broad data agent would mix parsing, calculations, interpretation, and chart selection, making errors difficult to attribute.

### Folder discoverability

Runtime packages, IDE canonical sources, generated projections, browser procedures, research documents, and redirects sit at the same conceptual level.

### Prompt drift

Copying a role into multiple packages allows permissions, status vocabulary, and review rubrics to diverge.

## 3. Target repository structure

The migration should be incremental. Do not move stable packages in the first phase.

```text
ai_agents/
├── README.md
├── AGENTS.md
├── agent-core/                    # new canonical shared layer
│   ├── README.md
│   ├── registry.yaml
│   ├── shared-agents/
│   │   ├── source-inspector/
│   │   ├── evidence-synthesizer/
│   │   ├── artifact-style-enforcer/
│   │   ├── structured-data-extractor/
│   │   ├── data-evaluator/
│   │   ├── visualization-specifier/
│   │   ├── planner/
│   │   ├── plan-reviewer/
│   │   ├── evaluation-designer/
│   │   ├── execution-verifier/
│   │   ├── failure-diagnostician/
│   │   └── documentation-curator/
│   ├── profiles/
│   │   ├── style/
│   │   ├── data/
│   │   ├── review/
│   │   └── documentation/
│   ├── schemas/
│   │   ├── common/
│   │   ├── data/
│   │   ├── planning/
│   │   └── review/
│   ├── services/
│   │   ├── policy/
│   │   ├── ledger/
│   │   ├── routing/
│   │   ├── validation/
│   │   └── calculations/
│   ├── adapters/
│   │   ├── daily-coder/
│   │   ├── research-forge/
│   │   ├── ide/
│   │   └── browser/
│   └── tests/
├── daily-coder-ecosystem/         # existing runtime
├── research-forge/                # existing runtime
├── gui/                           # control UI (package agent_dashboard)
├── ide-agents/                    # user-facing canonical IDE agents + bridge
├── agents/daily-task/browser/       # browser RCC v3 families (paste harness)
├── skills/                        # on-demand user and domain procedures
├── docs/
│   ├── README.md
│   ├── architecture/
│   ├── plans/
│   ├── decisions/
│   ├── guides/
│   ├── reference/
│   └── research/
└── .cursor/ .claude/ .github/     # generated projections only
```

## 4. Why `agent-core/`

`ide-agents/` should remain authoritative for user-facing IDE roles and bridge behavior. It should not become the canonical home for every runtime delegate.

`agent-core/` provides a neutral home for contracts used by Daily Coder, Research Forge, IDE adapters, browser adapters, and skills. Runtime packages depend on a versioned core contract rather than importing each other’s prompts.

## 5. Folder contract

Each shared role folder contains:

```text
<role>/
├── README.md
├── contract.yaml
├── prompt.md
├── model.yaml
├── tools.yaml
├── permissions.yaml
├── input.schema.json
├── output.schema.json
├── profiles/
├── examples/
├── tests/
└── CHANGELOG.md
```

Do not copy general platform policy into every prompt. Reference validated contracts and inject only task-relevant rules.

## 6. Documentation structure

### Root `README.md`

Must answer in the first screen:

* What the repository does.
* Which six agents users invoke.
* Which packages are runtimes versus adapters.
* Where shared subagents live.
* How to run validation.

### Root `AGENTS.md`

Contains only user-facing IDE agents, authority order, generation rules, and audited-write instructions.

### `agent-core/README.md`

Explains shared versus domain-specific roles and links every role to its contract.

### `docs/architecture/`

* ecosystem map
* authority and trust boundaries
* state and ledger
* routing
* tool gateway
* shared-subagent architecture

### `docs/plans/`

Versioned implementation plans and migration sequences.

### `docs/decisions/`

Short decision records for major choices, including shared-role consolidation and the split data workflow.

### `docs/guides/`

Contributor, operator, browser, IDE, and new-agent authoring guides.

### `docs/reference/`

Schemas, status vocabulary, error codes, registry fields, folder conventions, and compatibility tables.

### `docs/research/`

Master specification, research library, references, and evidence reviews.

## 7. Migration map

| Existing item | Target | Method |
|---|---|---|
| Runtime planner prompts | `agent-core/shared-agents/planner` | Extract shared contract; keep runtime adapter |
| Browser planner | Browser adapter generated or manually checked against shared contract | Preserve draft-only status |
| Runtime/browser plan reviewers | `agent-core/shared-agents/plan-reviewer` | Share rubric and status schema |
| Browser doc-reader and code recon contracts | `source-inspector` profiles | Keep separate tool bindings |
| Research synthesizer/report assembly | `evidence-synthesizer` | Standardize evidence packet |
| Tone/style roles | `artifact-style-enforcer` profiles | Keep browser persona for interactive use |
| Spreadsheet/data inspection | Four-stage data workflow | No monolithic data agent |
| Test author and experiment review | `evaluation-designer` adapters | Domain-specific output generators |
| Test execution and experiment running | `execution-verifier` contract | Separate permission profiles |
| Documentation roles | `documentation-curator` profiles | Preserve package-local authority |

## 8. Implementation phases

### Phase 0 - Inventory and freeze

* Export the full specialist registry.
* Record role name, primary outcome, callers, tools, permissions, input/output shape, and tests.
* Identify copied text and semantically equivalent roles.
* Freeze new shared-role additions during the inventory.

Exit: every current role has an owner and classification.

### Phase 1 - Contract foundation

* Create `agent-core/registry.yaml`.
* Add common task, result, evidence, finding, artifact, and error schemas.
* Add registry lint and semantic-version checks.
* Add authority and projection rules.

Exit: empty shared roles can validate against the registry contract.

### Phase 2 - First three consolidations

Implement:

1. `planner`
2. `plan-reviewer`
3. `artifact-style-enforcer`

Choose these first because they are easy to compare against existing outputs and do not require data execution infrastructure.

Exit: Daily Coder and at least one IDE/browser adapter use the same canonical contract without privilege widening.

### Phase 3 - Data workflow

Implement:

1. `structured-data-extractor`
2. deterministic calculation/query service
3. `data-evaluator`
4. `visualization-specifier`

Exit: supplied CSV/XLSX fixtures produce traceable normalized data, reproducible calculations, defensible findings, and valid display specifications.

### Phase 4 - Research and documentation consolidation

Implement:

* `source-inspector`
* `evidence-synthesizer`
* `documentation-curator`

Exit: Research Forge, plan-prep, and documentation closeout exchange the same bounded evidence format.

### Phase 5 - Evaluation and diagnostics

Implement:

* `evaluation-designer`
* `execution-verifier`
* `failure-diagnostician`

Exit: coding tests, research experiments, data checks, and skill scenarios use common result and failure schemas while retaining domain permissions.

### Phase 6 - Projection and folder cleanup

* Generate or validate IDE projections.
* Add browser parity checks without claiming runtime sync prematurely.
* Add navigation indexes and deprecation redirects.
* Move research documents into `docs/research/` only after inbound-link checks pass.

Exit: no dead links; generated files are clearly labeled; legacy paths redirect.

## 9. Validation strategy

### Contract tests

* Required fields.
* Unknown-field behavior.
* Version compatibility.
* Permission narrowing.
* Stable error codes.

### Cross-surface parity

Assert primary outcome, forbidden actions, claim statuses, and output schema agree across runtime, IDE, browser, and skill adapters.

### Behavioral A/B tests

Compare canonical shared role versus each old duplicate on frozen tasks. Accept consolidation only when quality does not regress and cost/maintenance improves.

### Security tests

* Untrusted instructions in source material.
* Caller attempts to widen tools.
* Cross-domain data request.
* Browser projection claims persistence.
* Shared role tries to approve its own work.

### Data tests

* Missing versus zero.
* Mixed types.
* Duplicate headers.
* Multiple tables per sheet.
* Formulas and cached values.
* Units and currencies.
* Date parsing.
* Outlier handling.
* Misleading chart request.
* Causal claim from descriptive data.

## 10. Metrics

* Duplicate contract count.
* Shared-role reuse count.
* Router precision.
* Schema-validation failures.
* Cross-surface drift findings.
* Unsupported-claim rate.
* Data extraction accuracy.
* Calculation reproducibility.
* Reviewer usefulness and false-positive rate.
* Tokens and latency per verified result.
* Artifact survival or user acceptance rate.
* Time for a new contributor to find the correct entry point.

## 11. GitHub readability checklist

* Root README has an architecture diagram and “start here” commands.
* Every top-level folder has a one-paragraph README.
* Generated directories contain a visible generated-file warning.
* Canonical sources link to projections, not vice versa only.
* Registry provides a searchable role table.
* Role names use consistent kebab-case.
* Redirect-only folders are clearly marked and time-bounded.
* Documentation links are relative and validated in CI.
* Examples use realistic but non-sensitive fixtures.
* Each role page includes “use when,” “do not use when,” input, output, and verification.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Shared role becomes a mega-agent | One outcome, typed modes, separate data stages |
| Canonical layer adds indirection | Strong indexes, generated docs, caller examples |
| Migration breaks existing paths | Compatibility adapters and redirect tests |
| Browser role implies hard enforcement | Explicit draft-only status and parity tests |
| Style agent changes semantics | Semantic invariants and independent review |
| Data agent fabricates analysis | Executable calculations and provenance-bound findings |
| Shared tools widen access | Caller-scoped capabilities evaluated at gateway |
| Registry grows without bound | Ownership, usage metrics, review dates, retirement gates |

## 13. Definition of done

* One canonical contract exists for every shared responsibility.
* Shared roles have two or more demonstrated callers.
* Deterministic work is performed by tools, not language-model guesses.
* Browser, IDE, and runtime adapters preserve authority boundaries.
* Existing user-facing entry points remain stable.
* The repository can be understood from root README → architecture → role registry → package docs.
* Consolidation reduces duplicated contracts without reducing verified quality.

## Sources

Based on the supplied master specification, research library/brief, repository overview, IDE roster, browser pack, and Research Forge overview.
