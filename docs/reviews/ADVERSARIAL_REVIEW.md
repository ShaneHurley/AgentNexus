# Adversarial Review of the Agent Ecosystem Upgrade

## Verdict

`CONDITIONALLY_APPROVE` for additive use. Do not treat runtime adapters as production-integrated until verified against the complete source repository.

## Review method

The design was challenged against scope, duplication, authority, data correctness, privacy, migration safety, testability, and future contributor readability. Findings were resolved during package construction when possible.

## Findings and resolutions

### 1. Shared roles could become mega-agents

Severity: high.

Risk: A generic role with many modes could recreate the monolithic assistant the architecture is intended to avoid.

Resolution: Every shared role has one primary outcome, versioned input and output contracts, a task-scoped permission list, and explicit forbidden actions. Style differences are profiles. Extraction, evaluation, and visualization remain separate roles.

### 2. A data agent could mix parsing with interpretation

Severity: high.

Risk: Parsing mistakes could become confident analytical claims.

Resolution: The workflow is split into structured extraction, deterministic calculation, evaluation, and visualization specification. Every computed result retains source and computation references.

### 3. Style enforcement could alter semantics

Severity: high.

Risk: A writing or code style pass could change requirements, behavior, uncertainty, or factual claims.

Resolution: The style role is findings-first, receives semantic invariants, labels semantic risk, and cannot approve its own patch. Deterministic lint handles punctuation and repeated text.

### 4. Shared contracts could widen permissions

Severity: critical.

Risk: A browser or low-privilege caller could inherit runtime tools.

Resolution: Permissions are supplied by the caller and intersected with the canonical maximum. Adapters may narrow but never widen. Browser projections declare no persistence and no external actions.

### 5. New package paths could break imports and links

Severity: high.

Risk: A full repository reorganization could break current package installation and documentation links.

Resolution: `agent-core/` is additive. Existing package paths remain unchanged. Folder moves are deferred. The application helper backs up replacement documentation and refuses other conflicts by default.

### 6. The complete source repository was not supplied

Severity: high.

Risk: Proposed adapters may not match current runtime APIs.

Resolution: Runtime adapters are documented specifications. The package ships executable standalone utilities and tests, but does not claim integration with unseen source. Integration requires code-level verification.

### 7. Registry and prompt duplication could drift

Severity: medium.

Resolution: `registry.yaml` is canonical for role identity and paths. Validation checks duplicate IDs, missing files, versions, and role folder structure. Projection generation reads canonical contracts.

### 8. Skill descriptions could create routing interference

Severity: medium.

Resolution: Skills have concise trigger descriptions and bounded bodies. The package retains the recommendation to keep approximately five to eight resident descriptors and load other skills on demand.

### 9. Writing rules could become repetitive or overly formal

Severity: medium.

Resolution: The writing profile uses four audience levels, defaults to minimal edits, and includes repetition and tone-consistency checks. Formality is calibrated rather than globally maximized.

### 10. Documentation could expose internal reasoning

Severity: medium.

Resolution: The decision record contains architecture conclusions, alternatives, evidence, risks, and trade-offs. It does not include hidden chain-of-thought or private internal reasoning.

## Residual risks

- Actual runtime adapter compatibility is unverified.
- Full prompt similarity analysis requires the source role folders.
- JSON Schema validation is lightweight unless the optional `jsonschema` dependency is installed.
- CSV support is production-ready for ordinary delimited text but does not replace spreadsheet-specific readers for XLSX files.
- Statistical evaluation is descriptive. Advanced inference requires a dedicated verified analytics tool.
- Browser projection generation remains experimental because the current browser pack documents no runtime synchronization.

## Release gates

Before production integration:

1. Verify imports and APIs against the complete repository.
2. Run existing Daily Coder, Research Forge, bridge, projection, and dashboard tests.
3. Compare shared roles against frozen caller-local baselines.
4. Confirm permission intersection at runtime.
5. Test with real CSV and XLSX workflows using approved spreadsheet readers.
6. Validate documentation links after merging.
7. Perform a human review of style and career privacy profiles.
