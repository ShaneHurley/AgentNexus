# Folder Conventions

- Use kebab-case for agent and skill folders.
- Put canonical shared roles in `agent-core/shared-agents/`.
- Put reusable style, data, review, and documentation profiles in `agent-core/profiles/`.
- Put cross-role schemas in `agent-core/schemas/`.
- Keep domain adapters under the caller's adapter namespace.
- Mark generated files clearly and do not edit them directly.
- Keep research evidence under `docs/research/` and implementation decisions under `docs/decisions/`.
