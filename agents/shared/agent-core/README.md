# agent-core

Shared capability contracts, registry snapshots, provider utilities, and deterministic services for AgentNexus.

Phase 2 adds versioned role/grant schemas, source adapters for IDE/DC/RF/personal metadata, six-layer permission intersection, compact authorized discovery, atomic reviewed snapshot activation/rollback, and a digest-pinned Docker worker. DC and RF enforce these contracts while retaining their workflow engines and approval gateways. Missing or contradictory authority fails closed; installing a capability does not grant execution rights.

Install this local distribution alongside the runtimes:

```bash
python -m pip install -e agents/shared/agent-core
python -m agent_core validate-registry
python -m agent_core compile-registry --repo /absolute/AgentNexus --output /absolute/snapshot-store
personal-store --help
writing-lint punctuation path/to/file.md
```

Compilation publishes a candidate without activating it. Activation requires an explicit current grant ceiling; rollback retains revocations and cannot widen permissions. Runtime source metadata must match the selected snapshot. The Docker worker requires a reviewed local image and running daemon, has no implicit image pull or host execution fallback, and does not apply edits to the host.

Full platform migration, durable shared sessions, unified memory, ModelResolver and SecretBroker remain later phases. Existing provider and personal-store utilities retain their own documented limits. See the root [technical reference](../../../TECHNICAL_REFERENCE.md) and [quickstart](../../../QUICKSTART.md) for current interfaces and validation scope.
