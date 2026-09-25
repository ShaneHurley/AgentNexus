# Research Messenger — mode contract index

Load contracts **for the active mode only**; do not read the full `skill_refs` list up front.

| Mode | Load when mode is selected |
|------|----------------------------|
| ASSEMBLE | `#file:ide-agents/contracts/research-messenger-skill-reference.md` + `#file:ide-agents/contracts/messenger-output-contract.md` |
| ECOSYSTEM | `#file:ide-agents/contracts/ecosystem-compatibility.md` + `#file:ide-agents/contracts/messenger-output-contract.md` |
| COMBINED | `#file:ide-agents/contracts/research-messenger-skill-reference.md` + `#file:ide-agents/contracts/messenger-output-contract.md` + `#file:ide-agents/contracts/ecosystem-compatibility.md` |

**Shared (load once when normalizing ledgers or rendering report):**

- `#file:ide-agents/contracts/output-template.md`
- `#file:ide-agents/contracts/recommendation-scoring.md` (validate inherited arithmetic only)
- `#file:ide-agents/contracts/research-intelligence-packet-1.0.schema.json` (machine packet validation)
