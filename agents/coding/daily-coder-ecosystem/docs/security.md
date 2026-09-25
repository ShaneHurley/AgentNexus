# Security Model

Treat every model as untrusted. Prompts communicate intent; runtime code enforces capabilities.

- The tool broker denies unlisted role/tool combinations.
- Filesystem paths are resolved, jailed to the repository root, checked against deny globs, and constrained by the approved plan allowlist for writes.
- Network access is denied unless a read-only adapter is explicitly configured. External writes require human approval.
- Secrets and credential-like paths are denied.
- Tool calls, artifacts, transitions, model assignments, usage, and approvals must be auditable.
- Skill creation and promotion are separate privileges. No skill self-promotes.
- Existing files require compare-and-swap hashes for writes, preventing stale reads from overwriting user edits.
- URL fetch revalidates every redirect, rejects non-public addresses, caps body size, and permits text content only.
- Provider secrets use the OS keyring when available. APIs and SQLite expose identifiers and fingerprints, never values.
- The REST service requires a bearer token by default.

Application checks are not a security boundary against a compromised host. Before high-trust production use, add OS-level sandboxing, TLS, external identity management, signed approvals, and per-provider egress controls.
