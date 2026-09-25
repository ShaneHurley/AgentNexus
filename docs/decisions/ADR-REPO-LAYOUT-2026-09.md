# ADR: Repository layout contract (F0)

Status: Accepted (F0 control plane)  
Date: 2026-09-23

## Context

The monorepo will move from a **legacy** physical tree (`ide-pack/ide-agents/`, top-level engines, `browser agent/`) to a **v2 domain** tree (`shared/ide-agents/`, `gui/`, `coder/`, `deep-research/`, federated browser families). Path consumers must keep working during migration without CWD-only guessing or silent fallback.

## Decision

1. **Marker file** — Repository root carries `.ai-agents-layout` (JSON) with `layout_version` and `layout` (`legacy` | `v2`).
2. **Installable package** — `ai_agents_repo` (editable in dev) exposes discovery, layout selection, physical roots, and `resolve_ref()` for in-process tools.
3. **Layout precedence** — `explicit argument` > `AI_AGENTS_LAYOUT` env > marker > auto-detect. Any lower-precedence signal that **disagrees** with the chosen layout **fail closed**.
4. **Mixed trees** — Legacy and v2 hub/engine anchors must not coexist (e.g. both `ide-pack/ide-agents` and `shared/ide-agents` MANIFEST, or both `daily-coder-ecosystem/` and `coder/`). Reject with `LayoutError`.
5. **Logical references** — Persisted `#file:` strings keep the **`ide-agents/` logical prefix** in canonical prompts. In-process resolvers map that prefix to the physical IDE hub (`ide_pack_root()`): `ide-pack/ide-agents/` (legacy layout) or `agents/ide/` (v2 agents hub).

## `#file:` strategy (F0d — in-process vs editor-native)

| Approach | Role in this repo |
|----------|-------------------|
| (1) Rewrite persisted `#file:` to v2 physical paths | Deferred until F5; high churn in canonical + contracts |
| **(2) Generate projections with paths that resolve via audit** | **Preferred for CI** — sync continues to emit `#file:ide-agents/...`; `audit_prompt_bytes.py` resolves via `resolve_ref()` |
| (3) Filesystem compatibility alias | Not relied on (Windows + CI symlink/junction proof not in scope for F0) |
| (4) Teach editor parser to call logical resolver | **Not proven in F0** — Cursor / Claude / Copilot loaders are out-of-process |

**Combined policy for F0–F5:**

- **Canonical SSOT:** logical `ide-agents/` prefixes (unchanged).
- **In-process tools:** `resolve_ref()` + `audit_prompt_bytes.py` (implemented).
- **Projections:** remain generated; byte audit is the gate before merge.
- **Editor-native loading:** manual verification checklist only — see [`docs/ide-agents/file-ref-verification-checklist.md`](../ide-agents/file-ref-verification-checklist.md).

We do **not** claim editor `#file:` resolution is proven until checklist items are executed on each IDE.

## `resolve_ref()` security

- Accepted prefixes only (`ide-agents/`, `skills/`, … — see package).
- Reject absolute paths, `..`, unknown prefixes.
- After `Path.resolve()`, path must stay under `repo_root()` (symlink escape fail closed).

## F1 physical rename (2026-09-23)

- **`agent-dashboard/` → `gui/`** on disk (`git mv` when using git). Python distribution and import name stay **`agent_dashboard`** / PyPI-style name `agent-dashboard`.
- **`.ai-agents-layout` may still say `legacy`** until F6b; both **legacy and v2** path maps in `ai_agents_repo.paths` resolve `gui_root()` to **`gui/`** after F1.
- Service strings in HTTP/JSON (`"service": "agent-dashboard"`) are unchanged in F1; folder branding in docs uses **`gui/`**.

## Consequences

- F1+ moves update path maps inside `ai_agents_repo` only; consumers import the package instead of string literals.
- Flipping default layout to v2 (F6b) updates the marker and removes legacy anchors — no silent fallback.
- External personal scripts outside CI remain **accepted residual risk** unless inventoried.

## References

- Package: `agents/shared/ai_agents_repo/`
- Validator: `python -m ai_agents_repo.validate --phase F0`
- Inventory baseline: `agents/shared/ai_agents_repo/data/path_consumer_inventory.baseline.json`
