# First-release folder tree (frozen)

| Path | Owner / authoritative state | Created |
|------|-----------------------------|---------|
| `src/research_forge/ledger/` | Append-only event log | W0 |
| `src/research_forge/registries/` | Projections from ledger | W0 |
| `src/research_forge/policy/` | Authorization decisions | W0 |
| `src/research_forge/budget/` | Spend/reserve state (derived + events) | W0 |
| `schemas/` | JSON schema definitions | W0 |
| `config/` | Static policy/budget defaults | W0 |
| `orchestrator/` | Phase DAG (no runtime yet) | G0/W0 placeholder |
| `agents/*/` | Role prompts (empty until W1+) | G0 placeholder |
| `adapters/*/` | Provider adapters | W0 mock |
| `services/*/` | Host service mirrors | G0 placeholder |

No two modules write the same authoritative store: only the ledger append path is authoritative.
