# Architecture

The supported runtime is a single-host, artifact-driven workflow. SQLite is the only authoritative state. Immutable JSON artifacts contain evidence and outputs; they never decide the next phase by themselves. CLI and REST entry points call the same orchestrator.

For implementation detail (digests, repair/frontier cycles, provider wire formats), see [`TECHNICAL.md`](TECHNICAL.md).

## Flow

Default full tail:

`intake → size → [research] → [brainstorm] → decide → [test design] → plan → plan review → human approval → implementation → test authoring → test execution → code review → documentation → alignment → acceptance`

**`S_TRIVIAL`** (profile `S` + trivial keywords such as typo/rename/comment): same path but skips **test authoring** and **documentation**. **Alignment is kept** so the acceptance gate’s `require_alignment_pass` still holds. State-machine edges allow `IMPLEMENT→TEST_EXECUTE` and `CODE_REVIEW→ALIGNMENT`.

The master is the sole design authority. Researchers, brainstormers, and reviewers may inform or challenge decisions but cannot silently change scope. Phase transitions are transactional and idempotent. Run status is separate from phase and represents active, human-waiting, job-waiting, blocked, failed, complete, simulated, or cancelled work. A crash is recovered from committed SQLite state and immutable artifact references. The chosen workflow key is stored on the sizing artifact and reused on resume/repair.

## Adaptive fan-out

S tasks skip research and brainstorming. Trivial S tasks additionally skip test_author and documenter. M uses bounded research without brainstorming. L/XL add bounded, non-overlapping research lanes and brainstorming. Research may stop after a completed batch once enough cards report empty unknowns. Every provider call reserves budget before launch, including parallel lanes.

## Context

The original request, exact constraints, artifact hashes, current decision, and current acceptance criteria are pinned. Raw transcripts are not propagated. Each role receives the smallest packet needed for its job. Downstream roles that expect `plan_summary`, `implement_summary`, `verification_commands`, and related digests receive them from `_rebuild_packet` (bounded structured digests, not full artifact dumps).

## Execution boundary

Models propose tool calls. `PolicyGateway` authorizes and records every call before `ToolBroker` executes it. Writes require the reviewed plan hash, human approval, a matching file allowlist, and compare-and-swap content hashes. Long tests are durable jobs; no provider runs while a job is pending.

OpenAI-compatible providers send native `tool` role messages (when call IDs are present) and may request `json_object` response format when tools are not advertised. Anthropic and Gemini keep their existing adapters.

## Deployment

SQLite plus local workers is the complete supported deployment. `RunRepository` and `JobQueue` reserve the multi-host boundary; Postgres and distributed queue stubs fail closed until worker authentication, leases, and orphan recovery are implemented.

## Acceptance

Acceptance is code-owned. The gate requires pinned revision/configuration, schema-valid artifacts, approved plan, scoped diffs, command results, independent reviews, and alignment. Mock runs become `SIMULATED`, never verified completion.
