---
name: simpleide
description: Compact playbook for MEDIUM and LARGE simpleIDE tasks. Use for explicit task binding, criteria, bounded delegation, checks and recorded outcomes.
---
# simpleIDE

`SX` is `{SX}`. These installed commands discover the local runtime from subdirectories; global installations render an absolute path. Search before MEDIUM/LARGE work: `SX mem search "<keywords>"`; open relevant hits with `SX mem show <id>`. Pass --host/--session consistently to search/show for session attribution; --search-id disambiguates repeated matching searches. Direct access need not receive search credit.

Pick a fresh task slug. Record goal/size and all criteria. Associate a captured primary request with `SX mem add goal ... --task <slug> --size MEDIUM --request Pn`; otherwise create an unbound goal and explicitly `SX task bind <slug> --host <host> --session <id>`. Never choose a request or session from newest-row ordering. Terminal slugs are immutable; retry with a new slug and --retry-of.

For MEDIUM, use one worker by default, at most three independent owned pieces. Brief with references/brief-template.md. For costly coding mistakes use sx-tester independently. Inspect the result, run `SX check --task <slug>` and scope, then give sx-reviewer `SX pack --task <slug> --base <ref>` plus the actual diff. Fix real findings, rerun affected checks, record a result. Close explicitly with `SX task close <slug> --outcome accepted|failed|abandoned --result Pn --by assistant --refs "<evidence>"`. Results alone do not accept tasks. Only an actual user decision supports --by user. Export the record with SX mem export.

For LARGE read references/large.md; for code/research read the corresponding reference. Do roles yourself if subagent/model or hook correlation support is unavailable. No filesystem installation proves host enforcement. Inspect pending/unmatched dispatches with SX task dispatches; reconcile only against observed evidence.

Record uncertainties as questions. When answered, save a task decision, then explicitly `SX mem resolve Pquestion --decision Pdecision`. References alone do not resolve questions. Ask only about objective, permissions, compatibility or irreversible action; otherwise record a reversible assumption and proceed.

Save reusable verified lessons with SX mem lesson; --local keeps project facts local. Saving the same local lesson without --local promotes it to shared or visibly queues it for sync. At most two repair rounds; change the brief or model after repeated failure.
