# Browser pack profiles (RCC SSOT)

## SSOT vs `agent-core/profiles/`

| Location | Purpose |
|----------|---------|
| **`agents/shared/browser/profiles/*.profile.md`** | **SSOT for browser RCC** — Role / Context / Constraints / Browser tabs slots used when filling task packets and host-specific profile pastes for the v3 **family** model (`browser_family` + optional `browser_variant`). |
| **`agent-core/profiles/`** | Runtime/style YAML for the Python agent-core pipeline (tone ladders, F1–F4 writing frames). Use when wiring automated runs — not the primary paste source for browser hosts. |

On conflict for **browser paste operations**, this folder wins. Sync style facts from agent-core only when explicitly bridging a writing variant to a style profile.

## Files

One stub profile per consolidated family (Phase 1 skeleton). Expand during family-authoring phases.
