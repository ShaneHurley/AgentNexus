# Authority and Role Map



This pack is an operational projection for paste-based browser hosts. It does not replace the Python everyday-agent runtime, audited enterprise tools, PolicyGateway, or a human decision owner.



## Banners (read first)



| Claim | Rule |

|-------|------|

| **Browser ≠ PolicyGateway** | Chat pastes produce PROPOSED artifacts. Audited repo mutation, gateway hashes, and bridge ledger state require operator-run **ide-bridge** (or IDE agents) with visible output — never infer from browser prose. |

| **Browser ≠ IDE `/use-master`** | `mission-control` sequences paste phases only. Full DAG dispatch, bridge parent, and native tooling live in IDE `/use-master` — see `ide-agents/canonical/use-master.md`. |

| **Adversarial reviewers do not execute fixes** | `code-reviewer` and `document-reviewer` emit verdicts and findings; they MUST NOT rewrite the artifact as the author. Run in a **new chat** after the producer family. |

| **Self-review ≠ independent review** | `code-crafter` and `writing-studio` require author **SELF_REVIEW** before final output; independent reviewers are still recommended before ship/send. |



On conflict, the embedded contract in the active `AGENT_MESSAGE.md`, the shared contract (`CORE_AGENT_CONTRACT.md`), and the current task packet govern the browser session; the runtime package governs runtime behavior. Browser output must never claim runtime worker fan-out, PolicyGateway enforcement, live enterprise search, persistent memory, audited writes, or tool execution without visible host evidence.



---



## Browser v3 families ↔ IDE counterparts



Prefer IDE agents when the host has bridge, repo access, or multi-lane research tooling.



| Browser `browser_family` | IDE counterpart | Prefer IDE when |

|--------------------------|-----------------|-----------------|

| `code-crafter` | `/daily-coder` + **ide-bridge** | Audited writes, real test/lint runs, PolicyGateway path |

| `code-reviewer` | `/code-reviewer` (or Bugbot-style review) | Repo-native diff review, CI context |

| `document-reviewer` | *(none — browser-first)* | Word/PDF/wiki adversarial review in browser tabs |

| `mission-control` | `/use-master` | Full mission DAG + bridge orchestration |

| `research-desk` (tiers) | `/deep-research` | Multi-lane RF when depth and tooling exist |

| `research-desk` / `assemble-given` | *(browser doc-reader lineage)* | Supplied-files extract in any host; no IDE required |

| `research-desk` (read-only recon packet) | `/researcher` | IDE codebase scan; browser = paste + tabs only |

| `plan-prep-researcher` *(engineering stub)* | `/plan-prep` | Glean/MCP plan context in IDE |

| `planner` *(engineering stub)* | planner canonical agent | Frozen plan artifacts in repo |

| `plan-reviewer` *(engineering stub)* | plan-reviewer canonical agent | Plan gate before implement |

| `writing-studio` | personal skills / style profiles | Long-form automation with `agent-core/profiles` |

| `plans-and-places`, `kitchen-cooking`, `learning-coach`, `thinking-lab` | everyday runtime Compass/Atlas/Prism *(legacy labels)* | v2 archive [`_deprecated/v2-everyday/`](../_deprecated/v2-everyday/README.md); prefer v3 families — legacy table below |



**Slug alignment:** Browser `code-reviewer` matches IDE `/code-reviewer` by name; behavior differs — browser = paste harness only.



---



## Legacy `browser_idea` → v3 family / variant (orphan prevention)



| Legacy `browser_idea` or path | v3 target |

|-------------------------------|-----------|

| `daily-coder` | `code-crafter` / `patch-draft` |

| `doc-reader` | `research-desk` / `assemble-given` |

| `deep-research` | `research-desk` / `deep` or `phd` |

| `contextual-concierge` | `plans-and-places` / `trip-itinerary` \| `packing-list` \| `errand-route` |

| `experience-architect` | `plans-and-places` / `event-run-of-show` \| `discover-events` \| `dietary-cross-check` |

| `sous-chef-pantry-master` | `kitchen-cooking` / `recipe` \| `allergy-diet-scan` \| `meal-plan` |

| `hyper-specific-learner` | `learning-coach` / `teach` \| `socratic` \| `quiz` \| `flashcards` \| `study-plan` \| `rubric-review` \| `exam-prep` |

| `knowledge-cartographer` | `learning-coach` / `map-topic` |

| `cognitive-friction-adapter` | `learning-coach` / `mental-model` |

| `thread-weaver` | `learning-coach` / `source-synthesis` |

| `friction-generator` | `thinking-lab` / `idea-stress-test` \| `pre-mortem` \| `decision-reversibility` |

| `asymmetric-risk-auditor` | `thinking-lab` / `cascade-risk` |

| `data-silhouette-reader` | `research-desk` / `gap-finder` \| `writing-studio` / `form-explain` |

| `information-condenser` | `research-desk` / `field-extract` |

| `bureaucracy-translator` | `research-desk` / `obligation-register` *(extract)* or `thinking-lab` *(plain-language)* |

| `voice-tone-chameleon` | `writing-studio` / `tone-match` |



Engineering folders at pack root (`plan-prep-researcher`, `planner`, `plan-reviewer`, `daily-coder`, `doc-reader`, `deep-research`) are **redirect stubs**; new work should use v3 family paths above (see each stub’s README).



---



## Genre labels (everyday pack — v2, until moved)



Atlas, Prism, and Compass are **organizational labels** for the 13 everyday browser roles under `everyday/`. For engineering role meaning (`deep-research`, `daily-coder`, etc.), **ide-agents/canonical/** and **ide-agents/contracts/** win on conflict.



| Browser role | Runtime parent | Runtime modes |

|---|---|---|

| hyper-specific-learner | Atlas | learn, quiz, rubric_review, flashcards, study_plan |

| knowledge-cartographer | Atlas | cartograph, negative_space, thread_weave |

| friction-generator | Prism | friction, pivot, investor_grill |

| experience-architect | Compass | event, diet_scan |

| contextual-concierge | Compass | travel, packing, errand_plan |

| sous-chef-pantry-master | Compass | kitchen, diet_scan |

| voice-tone-chameleon | Prism | voice_match |

| information-condenser | Prism | condense |

| bureaucracy-translator | Prism | bureaucracy, obligation_register |

| asymmetric-risk-auditor | Prism | risk_audit |

| data-silhouette-reader | Prism | negative_space, form_check |

| cognitive-friction-adapter | Atlas | cognitive_adapt |

| thread-weaver | Atlas | thread_weave |



On conflict between this table and v3 `browser_family` packets, the filled packet + active family `AGENT_MESSAGE.md` win for the current session.

