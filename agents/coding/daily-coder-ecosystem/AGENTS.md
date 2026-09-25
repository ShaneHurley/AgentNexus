# Repository Instructions

## Purpose
Maintain a small, auditable orchestration runtime. Prefer deterministic enforcement over prompt-only policy.

## Before changing code
1. Read `README.md`, `docs/architecture.md`, and the nearest role or skill file.
2. Identify the exact acceptance criterion and affected invariant.
3. Make the smallest reversible edit.

## Required checks
```bash
python -m unittest discover -s tests -v
python -m daily_coder validate
```

## Hard boundaries
- NEVER bypass `ToolBroker` for role-originated tool calls.
- NEVER treat JSON artifacts as authoritative run state; SQLite is authoritative.
- NEVER let a role broaden its own permissions, budget, scope, or model tier.
- NEVER mark a run complete from model prose; completion requires the acceptance gate.
- ALWAYS pin the request, repository revision, configuration hash, and artifact hashes in the run record.
