# Tool Adapter Contract

Register tools in `config/tools.json`, then implement a broker method that validates arguments, authorizes the calling role, applies path/network/write policy, executes the tool, redacts sensitive output, and records immutable evidence.

Local filesystem, repository, allowlisted command, patch, and test tools are implemented. Read-only URL fetch and Brave Search are implemented when network policy and credentials enable them. A role sees only schemas for tools in its allowlist.

All role-originated calls must enter through `PolicyGateway.execute`; direct broker invocation is reserved for runtime-owned evidence collection. Repository writes additionally require a matching approved plan hash and file allowlist.

Email and calendar tools must remain disabled unless the user explicitly requests them. External writes require a separate human approval token. A role prompt cannot activate a disabled tool.
