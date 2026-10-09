# Execution record: ANX-0 / ANX-4 / ANX-5

Approved plan: 2026-10-09-agentnexus-roadmap.md. Root integration owner coordinates two disjoint workers per epic. No paid calls or credential operations.

- ANX-0: in progress. Original main and unpublished commits retained. Recovery archive and consistent SQLite backup stored in the original checkout's ignored .agentnexus/recovery directory. Curated baseline starts at origin/main 6fc01cb; local snapshot 85bf938 excludes operator history and untracks 6,906 environment/runtime files without deleting their local copies. Six packages install in a fresh Python 3.10 environment from uv.lock.
- ANX-4: pending baseline merge/CI. Contract freeze, then provider/broker and resolver/evaluation lanes.
- ANX-5: pending ANX-4 merge/CI. Storage/retrieval and personal/portability lanes.
- ANX-6/7: backlog, not implementation scope.

Ruling: source-maintenance gateway context permits approved Python modules and documentation whose names contain secret/credential; actual credential-data files stay denied. Filename globs were otherwise preventing authorized edits to the scanner/broker implementation. Every source write uses a bridge-approved run, CAS precondition and PolicyGateway receipt.

ANX-0 acceptance: fresh locked Python 3.10 whole suite 707 tests and 23 subtests passed; 121 native DC unittest tests passed; DC validate, both canonical import checks, projection sync, Ruff correctness and redacted preflight passed. Independent review's commit metadata gap corrected (10 focused preflight tests pass after fix). Original recovery commits retained on local codex/recovery-baseline-local; curated publication history derives from origin/main and replaces the copied scanner credential with obvious dummy data. The hosted CI and merge gates remain pending.
