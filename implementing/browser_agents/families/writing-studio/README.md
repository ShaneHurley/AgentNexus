# Writing Studio (`writing-studio`)

Browser family for typed prose deliverables. Authors run an adversarial **self-review** before claiming send-ready; independent **document-reviewer** is a separate paste in a new chat.

## Thought process
1. Anchor on packet objective and acceptance criteria.
2. CLASSIFY main vs variant (see [HOW_TO.md](HOW_TO.md)).
3. Bounded plan → draft from evidence only → **SELF_REVIEW** → revised draft.
4. Evidence-tagged REPORT per embedded contract.

## Variant catalog

| Variant | Why it exists |
|---------|----------------|
| `tech-doc` | Technical documentation from specs/tabs; scannable procedures and UNKNOWN gaps. |
| `email` | Professional email: subject, concise body, clear next step (no invented thread context). |
| `study-guide` | Learning aid with terms, summaries, and practice mapped to sources. |
| `homework` | Rubric-aligned help with academic integrity posture (scaffold vs ghostwrite). |
| `personal-project` | Personal/creative prose; creative license only when packet allows. |
| `resume` | Action + scope + result bullets from supplied experience only. |
| `cover-letter` | Posting-aligned letter tied to verified resume facts. |
| `github-readme` | Developer README markdown from repo context. |
| `github-issue` | Issue template with repro and environment from evidence. |
| `ads-marketing` | 3–5 platform-sized variants with **COMPLIANCE_FLAGS** for risky claims. |
| `form-explain` | Plain-language duties/deadlines/exceptions with locators (ex bureaucracy-translator). |
| `tone-match` | Style match from **authorized** samples only (ex voice-tone-chameleon). |
| `slack-update` | Short internal update with lead sentence and ask. |
| `meeting-notes` | Decisions, owners, actions, open questions from transcript/notes. |
| `self-review-only` | Mandatory SELF_REVIEW gate on an existing draft; snippets only if allowed. |

## Lineage
- Professional email/resume/cover letter: `ai_profile_professional_writing.md`
- Ads copy: `ai_profile_ads_copywriter.md`
- Everyday prism: `bureaucracy-translator` → `form-explain`; `voice-tone-chameleon` → `tone-match`
