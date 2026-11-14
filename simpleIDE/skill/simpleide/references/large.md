# LARGE task

1. Create a readable request/criteria artifact with `SX pack --task <slug> --base <ref>`. Give `sx-planner` that Markdown path, content hash and source store/record identities, then record its goal, criteria, assumptions, and interface decisions. Ask only questions that change objective, permission, compatibility or irreversible action.
2. Freeze names, signatures, schemas, and file ownership. Dispatch independent workers and an independent tester in one turn. Use separate worktrees if writers could overlap.
3. Merge pieces in declared order, then run checks on the integrated revision while reviewer reads `sx pack` and the actual diff. Never test a half-merged tree.
4. Give one focused repair brief for each real failure. Run affected checks again; stop after two repair rounds and report unresolved failures.
5. Verify each criterion against evidence. Record tests and result, explicitly close the task with outcome/actor/evidence, export the task, and use `sx-writeup` for a final document.
