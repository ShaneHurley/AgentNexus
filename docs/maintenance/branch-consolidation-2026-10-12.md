# Branch consolidation — 2026-10-12

The six Codex delivery branches for PRs #18–#23 were already squash-merged into main. Their original commit IDs differ from the squash commits; the remaining ahead counts do not imply missing features. They are archived instead of being merged again.

The unique Workshop route additions from `copilot/add-workshop-tab` are integrated into the current authenticated dashboard. `copilot/coding-workshop-dashboard` and `copilot/custom-agents-issues` point to an existing main ancestor and contain no additional delivery work.

Recent supervised Codex compatibility, subscription accounting, replay and bounded-context evaluation changes are consolidated as source, tests and operator documentation. This does not establish a completed game implementation or proven token savings. The latest game investigation stopped with a Codex `turn_failed` response and unknown usage; its reservation and evidence remain local. Production context optimization remains disabled.

Old remote branch tips are retained as `archive/2026-10-12/<original-branch-name>` tags before branch deletion. Local branch histories are preserved in a private Git bundle and private archive refs. Worktree contents, ignored runtime state and historical evidence remain local; deleting branches is not deletion of those files.

Publication starts from cleaned main commit `935026cd5029d4a671a18f7b155ddf8225e57cd3`. Credential-containing recovery ancestry, runtime databases and the machine-specific native operator grant are excluded. The owner's portable fail-closed Codex hook changes are retained. Credential revocation remains an owner action; archiving does not erase old Git objects.

Required checks: independent source review of Workshop/hooks, full offline pytest suite, native DC validation, canonical imports/projection synchronization, correctness lint and redacted publication preflight. GitHub Linux/macOS CI must pass on the exact integration head before merge. No live model calls or API spending are required for branch cleanup.
