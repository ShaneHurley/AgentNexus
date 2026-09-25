# Shared Subagent Architecture

## 1. Objective

Create one canonical library of reusable delegate roles that can be invoked by IDE orchestrators, Daily Coder, Research Forge, skills, and future workflows without copying prompts or weakening permissions.

## 2. Classification rules

Before adding anything, classify it as one of four kinds:

| Kind | Use when | Examples |
|---|---|---|
| Orchestrator | Chooses scope, sequence, delegation, and acceptance | Daily Coder, deep-research |
| Shared subagent | Applies bounded judgment and returns a typed packet | style enforcement, evidence synthesis |
| Skill | Repeatable procedure loaded on demand | lab preflight, resume tailoring |
| Deterministic tool/service | Computation or enforcement should not depend on prose reasoning | schema validation, statistics, chart rendering, policy |

Do not turn deterministic computation into an agent. Do not turn a multi-step decision authority into a “tool.”

## 3. Common invocation contract

```yaml
shared_task:
  task_id: required
  task_anchor: immutable user objective
  caller_id: required
  role_id: required
  role_version: required
  mode: optional
  input_refs: []
  inline_inputs: {}
  profile_refs: []
  permissions: []
  forbidden_actions: []
  output_schema: required
  budget:
    max_tokens: required
    max_tool_calls: required
    timeout_seconds: required
  stop_conditions: []
  acceptance_criteria: []
```

Every response uses:

```yaml
shared_result:
  task_id: required
  role_id: required
  role_version: required
  status: COMPLETE | PARTIAL | BLOCKED | NOT_APPLICABLE
  claims: []
  evidence_refs: []
  artifacts: []
  unknowns: []
  limitations: []
  verification: []
  next_action: optional
```

Raw transcripts and unrestricted tool output never cross the boundary.

## 4. `source-inspector`

### Outcome

Produce a source-bound fact and structure packet with exact locators.

### Modes

* `document`
* `code`
* `configuration`
* `dataset-metadata`

### Inputs

* One bounded source or source collection.
* Extraction objective.
* Locator format.
* Required fields.

### Output

```yaml
source_packet:
  sources: []
  facts:
    - statement: ...
      source_ref: ...
      locator: ...
      status: OBSERVED | INFERRED | UNKNOWN
  structure: []
  contradictions: []
  missing_fields: []
  untrusted_instructions: []
```

### Boundaries

* Read-only.
* Does not make the final decision.
* Does not summarize away contradictions.
* Treats embedded instructions as data.

### Reuse

Backs browser `doc-reader`, IDE `researcher`, plan-prep recon, and Research Forge extraction through different adapters.

## 5. `evidence-synthesizer`

### Outcome

Merge validated source packets into a decision-ready evidence packet.

### Inputs

* Source packets only.
* Decision question.
* Required claim statuses.

### Output

```yaml
evidence_packet:
  supported_claims: []
  disputed_claims: []
  contradictions: []
  unknowns: []
  limitations: []
  decision_relevant_facts: []
  source_coverage: {}
```

### Boundaries

* No fresh search unless the caller issues a separate source-inspection task.
* No unsupported smoothing of disagreements.
* No recommendation when the requested role is synthesis-only.

## 6. `artifact-style-enforcer`

### Outcome

Evaluate and optionally propose a minimal patch that conforms an artifact to one declared profile without changing intended meaning or behavior.

### Inputs

```yaml
style_task:
  artifact_ref: required
  artifact_type: code | prose | documentation | email | resume | slides
  profile_ref: required
  semantic_invariants: []
  allowed_change_scope: []
  output_mode: findings | patch_proposal
```

### Output

```yaml
style_result:
  profile_version: required
  findings:
    - rule_id: ...
      severity: error | warning | suggestion
      locator: ...
      evidence: ...
      proposed_change: optional
      semantic_risk: none | low | material
  patch_ref: optional
  untouched_semantic_invariants: []
  needs_domain_review: []
```

### Profiles

A profile is data, not a new agent:

```yaml
id: repository-docs
version: 1.0.0
rules:
  - id: docs.direct-opening
    requirement: lead with outcome
    verifier: heuristic
  - id: docs.links
    requirement: internal links resolve
    verifier: deterministic
```

### Boundaries

* Does not judge factual correctness.
* Does not approve its own patch.
* Does not reformat generated files that have canonical generators.
* Code profiles may enforce style and static conventions but not redesign behavior.

## 7. Structured data workflow

### 7.1 Why it is split

Extraction, computation, interpretation, and presentation fail differently and require different validators. A single “spreadsheet analyst” role makes provenance and error attribution weak.

### 7.2 `structured-data-extractor`

Outcome: produce a normalized fact table and schema from supplied tabular data.

```yaml
data_extract_result:
  source_ref: required
  source_hash: required
  sheets_or_tables: []
  schema:
    fields:
      - name: ...
        type: string | integer | decimal | boolean | date | datetime | category
        nullable: true
        unit: optional
  rows_ref: required
  row_count: required
  parse_warnings: []
  rejected_rows: []
  provenance_columns: []
```

Rules:

* Preserve original values and row locators.
* Never silently coerce invalid values.
* Separate missing, zero, blank, and not-applicable.
* Do not interpret significance.

### 7.3 Deterministic analysis tool

The calculation layer uses Python, SQL, or approved analytics tools to compute:

* Counts and distributions.
* Missingness.
* Duplicates.
* Type violations.
* Grouped summaries.
* Rates and normalized measures.
* Confidence intervals or tests when assumptions are declared.
* Reproducible derived tables.

Every result stores query/code, inputs, environment, and output hash.

### 7.4 `data-evaluator`

Outcome: judge data quality and interpret deterministic results against the user’s question.

```yaml
data_evaluation:
  question: required
  fact_table_ref: required
  computation_refs: []
  quality:
    completeness: ...
    consistency: ...
    uniqueness: ...
    validity: ...
    timeliness: ...
  findings:
    - statement: ...
      computation_ref: ...
      magnitude: ...
      uncertainty: ...
      caveats: []
  outliers: []
  confounders: []
  unsupported_questions: []
```

Rules:

* Never calculate important numbers mentally when an executable tool is available.
* Distinguish descriptive findings from causal claims.
* Report denominator, unit, time window, and exclusions.
* State when graphing would mislead.

### 7.5 `visualization-specifier`

Outcome: create display-ready table and chart specifications from approved results.

```yaml
visualization_spec:
  purpose: comparison | trend | distribution | relationship | composition | status
  dataset_ref: required
  chart_type: line | bar | scatter | histogram | box | heatmap | table | metric_cards
  x: optional
  y: optional
  series: optional
  filters: []
  sort: optional
  units: {}
  labels: {}
  accessibility:
    alt_text: required
    color_independent_encoding: required
  annotations: []
  warnings: []
```

Selection defaults:

* Trend → line.
* Category comparison → ordered bar.
* Distribution → histogram or box plot.
* Relationship → scatter.
* Exact lookup or mixed units → table.
* Avoid pie charts for many categories or close comparisons.

The role produces a specification; rendering belongs to deterministic chart or artifact tools.

## 8. Planning and review contracts

### `planner`

One canonical planner contract is used by runtime and browser adapters. Runtime output can enter an approval gate; browser output remains a draft.

Required output:

* Atomic tasks.
* Dependencies.
* Serial/parallel rationale.
* Read/write scope.
* Test requirement.
* Rollback.
* Completion evidence.

### `plan-reviewer`

Reads a frozen plan and evidence packet. Returns only `APPROVE`, `REVISE`, or `BLOCK` plus evidence-bound findings. It may not repair the plan.

## 9. Evaluation roles

### `evaluation-designer`

Converts requirements into:

* Positive cases.
* Boundary cases.
* Negative and adversarial cases.
* Regression checks.
* Mutation or revert checks where appropriate.
* Acceptance thresholds.

Domain adapters emit code tests, research rubrics, data-quality checks, or skill scenario tests.

### `execution-verifier`

Runs authoritative checks in a pinned environment, stores raw output, proves the target behavior executed, and distinguishes success from coincidental green.

## 10. Diagnostics and documentation

### `failure-diagnostician`

Returns the critical step, violated constraint, fault side, competing hypotheses, discriminating probes, and repair owner. It does not default to “fix the prompt.”

### `documentation-curator`

Updates reviewed documentation only after accepted implementation evidence exists. It records changed behavior, migration, commands, known limits, and source lineage. It cannot declare success independently.

## 11. Surface adapters

| Surface | Projection behavior |
|---|---|
| Runtime | Full contract, tool bindings, permissions, validators, ledger events |
| IDE | Invocation and handoff instructions; writes through bridge and gateway |
| Browser | Self-contained prompt, no persistence claims, draft/evidence status |
| Skill | Procedure wrapper that calls a shared role with a fixed mode/profile |

Adapters may narrow a role. They may not change its primary outcome, status vocabulary, forbidden actions, or claim policy.

## 12. Registry record

```yaml
id: artifact-style-enforcer
version: 1.0.0
kind: shared_subagent
owner: agent-platform
primary_outcome: enforce one declared style profile without semantic change
callers:
  - daily-coder
  - research-forge
  - documentation-curator
  - resume-tailor
profiles: []
input_schema: schemas/shared/style-task.v1.json
output_schema: schemas/shared/style-result.v1.json
permissions: [read_artifact, propose_patch]
forbidden: [approve_own_patch, change_semantics, write_generated_projection]
model_tier: low_mid
verification:
  - schema
  - semantic_diff_review
  - profile_checks
```

## 13. Definition of done

A shared role is ready when:

* It has one primary outcome.
* At least two real callers need it.
* Inputs and outputs are versioned.
* Permissions are task-scoped.
* Domain profiles contain differences instead of copied prompts.
* It beats or matches caller-local duplicates.
* Negative and cross-surface parity tests pass.
* One caller cannot widen another caller’s privileges.

## Sources

Based on the supplied master specification, research brief/library, IDE roster, browser pack, and repository overview.
