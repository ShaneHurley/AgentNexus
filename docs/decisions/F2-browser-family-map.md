# F2 — Browser RCC v3 family map (frozen)

**Status:** Frozen at F2a (domain reorg). **Layout:** v2 physical paths; **F6c complete** — root `browser agent/` tombstone removed.

## Ten families (exact IDs)

| Family ID | Domain root (repo-relative) | IDE counterpart (soft) |
|-----------|----------------------------|-------------------------|
| `plans-and-places` | `daily-task/browser/families/plans-and-places` | — |
| `kitchen-cooking` | `daily-task/browser/families/kitchen-cooking` | — |
| `learning-coach` | `daily-task/browser/families/learning-coach` | — |
| `writing-studio` | `daily-task/browser/families/writing-studio` | personal skills / style profiles |
| `thinking-lab` | `daily-task/browser/families/thinking-lab` | — |
| `mission-control` | `daily-task/browser/families/mission-control` | `/use-master` (paste-only; not DAG) |
| `code-crafter` | `coder/browser/code-crafter` | `/daily-coder` + ide-bridge |
| `code-reviewer` | `coder/browser/code-reviewer` | `/code-reviewer` |
| `document-reviewer` | `coder/browser/document-reviewer` | — |
| `research-desk` | `deep-research/browser/research-desk` | `/deep-research` |

**Naming lock:** Browser coding family stays **`code-crafter`** (never renamed to `daily-coder`).

## Shared browser pack

| Role | Path |
|------|------|
| Federated index | `agents/shared/browser/MANIFEST.index.json` |
| Operator harness | `agents/shared/browser/_shared/` |
| RCC profiles | `agents/shared/browser/profiles/` |
| Build / QA | `agents/shared/browser/scripts/build_self_contained_agents.py` |
| Router entry | `agents/daily-task/ROUTER.yaml`, `agents/daily-task/driver.py` |

## Legacy disposition (F6c — complete)

| Former path | Current location |
|-------------|------------------|
| Root `browser agent/` (tombstone) | **Deleted** — use federated paths below |
| Ten v3 family trees | `agents/daily-task/browser/families/`, `agents/coding/browser/`, `agents/research/browser/` |
| `_shared/`, `profiles/`, `scripts/` | `agents/shared/browser/` |
| `everyday/`, `_deprecated/v2-everyday/` | **Historical** — see `agents/shared/browser/_deprecated/` if retained |
| Engineering stubs | `agents/coding/browser/` + research shard |

## Non-goals (F2)

- Daily Task / Mission Control as IDE user-facing orchestrators (KEEP-6 unchanged).
