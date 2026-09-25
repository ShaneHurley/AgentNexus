# Run phase transitions (Wave 0 freeze)

Legal phases: `init` → `clarifying` → `planning` → `discovering` → `reading` → `extracting` → `verifying` → `composing` → `auditing` → `completed`.

Terminal: `completed`, `failed`, `cancelled`.

Resume requires matching charter_hash, policy_version, schema_version; terminal phases return `PLAN_STALE`.

Illegal fixture cases (must fail): skip from `init` to `composing`; resume after `completed`; version mismatch on resume.
