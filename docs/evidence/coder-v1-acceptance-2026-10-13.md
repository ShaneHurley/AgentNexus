# Codex coder acceptance evidence — October 13, 2026

## Candidate and tested behavior

Source baseline: `cd4d44a9e22d863e1ddae4e756f28142b6b019cd`. Candidate policy: `coder-v1/1`, explicit task authority, one concurrent Codex invocation. Reviewed transport: `codex-cli 0.162.0-alpha.17.2`, `gpt-6.1-sol`, medium effort, ChatGPT subscription.

The public supervisor completed planning, authorized patching, isolated tests, independent model review, and acceptance. A real summarizer defect was corrected in a separate worktree: decimal text no longer outranks a valid bullet as a numbered-list item. Regression tests cover the defect, valid numbered markers including tabs, and zero maximum points.

## Recorded trials

| Trial | Run ID | Runtime status | Actual model calls | Reported input + output tokens |
|---|---|---|---:|---:|
| Initial bug (budget stopped before review) | `3ce8a95d-a8e7-41e2-9607-e38014695f1c` | FAILED | 6 | 58,893 |
| Bug fixture | `bb90f8ec-9f10-4825-a5be-81f83a69a196` | COMPLETE | 5 | 50,137 |
| Feature fixture | `4032c12f-176d-4d4b-bce6-723a19367fc5` | COMPLETE | 4 | 42,479 |
| Fenced planner handoff | `194fd24c-6517-413e-b513-5e447ee5ae9c` | COMPLETE | 4 | 40,562 |
| First recovery (cancelled after boundary defect) | `e2fd87d1-f5f1-4762-8dd3-6407605ed60a` | CANCELLED | 3 | 29,907 |
| Second recovery (transport misunderstanding) | `017ce4fa-6868-42a6-9de2-00361b59d99f` | FAILED | 5 | 48,704 |
| Recovery after accepted write | `4de3af38-826d-4b91-978f-366fe750a8a8` | COMPLETE | 4 | 40,936 |
| Bug repeat | `1fa50a7b-59c8-458d-be98-aac9eeb33f25` | COMPLETE | 4 | 40,822 |
| Feature repeat | `96d34b92-fc7e-4092-93b5-fe063d55810e` | COMPLETE | 4 | 42,865 |
| Real summarizer task | `6d6e3639-344f-4c03-996d-6231dd384e0f` | COMPLETE | 8 | 99,126 |

These trials total **47 actual model calls and 494,431 reported tokens**, including failed/cancelled attempts. Scripted operator patch providers and deterministic runtime roles are not counted as model calls. Historical pre-candidate attempts in the original checkout remain retained separately: 16 actual model calls and 199,505 reported tokens, all acknowledged and no outstanding reservation at reconciliation. Their private requests are excluded from this report.

The completed trials have recorded usage and zero outstanding supervisor reservations. Subscription cash attribution is unknown; zero known API cash does not mean the subscription has no cost. Native provider-usage receipts preserve cache/reasoning details separately.

## Recovery and interventions

Recovery run `4de3af38-826d-4b91-978f-366fe750a8a8` deliberately exited 75 after durable IMPLEMENT and accepted patch receipt **57**. Ordinary public resume completed all five isolated tests and review. The final write-receipt list remained exactly `[57]`; the patch was not applied twice. Four model invocations reported 40,936 tokens, settled once across the two supervisor segments.

The fenced-handoff harness changed completed planner presentation only and recorded the intervention; permissions and usage were unchanged. Offline negative tests separately prove delivery to the intended recipient after formatting repair fails.

Operator infrastructure edits used frozen bridge plans and PolicyGateway receipts. Apply-only operator runs intentionally finish FAILED because they stop before autonomous acceptance; their later tests and independent review are recorded separately. They are never represented as autonomous coder successes.

An implementation response once mistook the inference-only native sandbox for a prohibition on proposing external gateway requests. The completed failed run remains recorded. Transport instructions now explain that proposals are JSON data, may be denied by the gateway, and confer no direct filesystem permission.

## Isolation and checks

Runner pin: `sha256:39213c61028595edc53ad5e19e27c9d7351039fa7da390e6f632d65346527425`.
The runner was built from a digest-pinned Python base with locked, hash-verified test dependencies. Task commands used disabled networking and bounded resources in secret-excluding snapshots. Receipts retain actual source hashes, image, argv, exit status, duration, and bounded output. Container pass/fail/timeout/cancellation/cleanup checks were exercised.

Before the final summarizer transfer: 1,233 repository tests passed, one live-operation test skipped by its opt-in setting, and 45 subtests passed. Native Daily Coder unittest checks passed 130 tests. Strict source checks, projection checks, capability audit, and publication preflight passed. Final repository/CI results are reported on the draft PR for the final commit.

## Local operation and limitations

Follow [the device quickstart](../coder-v1.md) and use `tools/coder-fixtures/prepare_contract.py` to bind the exact request and workspace. The example deliberately starts with a defect and an immutable five-test oracle.

The acceptance-only daily ceiling amendment was explicitly authorized at 750,000 tokens, recorded in the local authority artifacts, and restored to 500,000 before the final packaged-example smoke. Consumed tokens and failed trials were preserved.

This is a contained candidate limited to one to three concrete paths. Larger/high-risk work uses existing larger workflows. Deterministic gates prove scope and evidence consistency; semantic confidence depends on actual tests and independent model review. These observations are not a general reliability-rate estimate. Cursor, Antigravity, research, and everyday connector execution remain later milestones. Roadmap #33's private project acceptance remains open.

References: #26, #27, #28, #29, #30, #84 (task authority), #85 (tolerant handoffs).
