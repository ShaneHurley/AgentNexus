# Claim enum map (DC ↔ deep-research ↔ Research Forge)

Three ecosystems use **different** claim vocabularies. Do not assume string parity across ledgers, IDE prompts, or bridge validators. Use this map when translating or comparing packets; when in doubt, preserve the source enum and document the mapping rationale.

## Canonical enums (by system)

| System | Enum values | SSOT |
|--------|-------------|------|
| **Daily Coder (roles)** | `VERIFIED`, `INFERENCE`, `ASSUMPTION`, `HYPOTHESIS`, `UNKNOWN` | Role output tagging (`daily-coder-ecosystem/README.md`) |
| **Deep-research (IDE skill / contracts)** | `CONFIRMED`, `CORROBORATED`, `SUPPORTED`, `INFERRED`, `CONFLICTING`, `UNKNOWN`, `NOT_APPLICABLE` | `evidence-and-source-rubric.md` |
| **Research Forge (ledger)** | `VERIFIED`, `CORROBORATED`, `INFERENCE`, `ASSUMPTION`, `CONTESTED`, `UNKNOWN`, `REJECTED` | `research-forge/schemas/claim_status.schema.json` |

## Approximate correspondence (informative, not identity)

| DC tag | Deep-research class | RF `claim_status` | Notes |
|--------|---------------------|-------------------|-------|
| `VERIFIED` | `CONFIRMED` or `SUPPORTED` | `VERIFIED` | DR distinguishes single-lineage (`SUPPORTED`) vs authoritative primary (`CONFIRMED`). RF verifier sets `VERIFIED`. |
| `INFERENCE` | `INFERRED` | `INFERENCE` | Wording differs; all require explicit inference boundaries. |
| `ASSUMPTION` | *(no direct class)* | `ASSUMPTION` | DR uses explicit assumptions inside `INFERRED` or marks claim `UNKNOWN`. RF untagged claims default toward `ASSUMPTION`. |
| `HYPOTHESIS` | `INFERRED` (provisional) or `UNKNOWN` | `ASSUMPTION` or `INFERENCE` | DC exploratory tag; do not promote to RF `VERIFIED` without verifier path. |
| `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | Aligns closely. |
| *(no DC tag)* | `CORROBORATED` | `CORROBORATED` | Requires independent lineages in DR; RF has explicit corroboration state. |
| *(no DC tag)* | `CONFLICTING` | `CONTESTED` | DR preserves both sides; RF may transition via `CONTESTED`. |
| *(no DC tag)* | `NOT_APPLICABLE` | `REJECTED` or omit | DR lane/source N/A; RF rejection is stronger — do not equate without context. |

## Rules for IDE pack and bridge (M21)

1. **Deep-research agents** must emit DR enums only in research drafts and scored packets (`ide-agents/contracts/` schemas).
2. **Research Forge bridge** must emit RF enums only in RF ledger events — never silently remap DR `CONFIRMED` → RF `VERIFIED`.
3. **Daily Coder roles** keep DC tags in role outputs; cross-walk at integration boundaries via this file, not via prompt assumption.
4. **Messenger** displays DR classifications in the human report; machine packet uses DR claim classes in the research-intelligence schema.
5. **Recommendation eligibility** differs: RF allows `VERIFIED`, `CORROBORATED`, `INFERENCE` for recommendations; DR scoring uses its own bands in `recommendation-scoring.md` — see that rubric for unsupported → `EXPERIMENT` / harmful → `DO_NOT_ADOPT`.

## Anti-patterns

- Treating URL count or repeated derivatives as `CORROBORATED` / `CORROBORATED` in any system.
- Mapping `CONFLICTING` ↔ `REJECTED` without preserving minority evidence.
- Using IDE chat prose to override enum values in the machine packet.
