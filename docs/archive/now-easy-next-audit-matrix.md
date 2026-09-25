# NOW / Easy-NEXT audit matrix

**Access / refresh:** 2026-09-23  
**Purpose:** S0a — verify NOW claims without treating green CI alone as closing PARTIAL items.

Status legend: **CONFIRMED** | **PARTIAL** | **NOT_RERUN** | **DEFERRED**

---

## Recommendation rows

| ID | Claim | Code / doc evidence | Tests | Status |
|----|-------|---------------------|-------|--------|
| **REC-08** | RF CLI missing-run / resume flows | `research-forge/tests/test_cli.py`; `cli.py` resume/status | pytest suite covers resume | **CONFIRMED** |
| **REC-06** | Dashboard RF resume fail-closed + live gate + HTTP map | `adapters/research_forge.py` load-first; `validate_decisions_for_gate`; `server.py` `_resume_http_status`; `runs.js` capability-gate | `agent-dashboard/tests/test_research_forge_resume.py` | **CONFIRMED** (post S5) |
| **REC-04** | Optional `RF_EXPERIMENT_SANDBOX=docker` | `experiments/kinds.py`; `.env.example` | No dedicated docker sandbox test | **PARTIAL** — **S8 DEFERRED** |
| **REC-02** | Security checklist | `security-review-checklist.md`; GH rows marked Shipped (S6c) | N/A | **PARTIAL** → improved; live adapters at scale still open |
| **L47** | Live resume same gate as `run --live` | CLI + dashboard adapter preflight | Dashboard resume HTTP tests | **CONFIRMED** (checked) |

---

## Doc surfaces (S1 / S1+)

| Surface | Prior issue | Post-fix status |
|---------|-------------|------------------|
| `docs/architecture-overview.md` | Claimed resume `NOT_IMPLEMENTED` | **Fixed** — shipped CLI resume/status |
| `docs/research-forge-deep-dive.md` | Stub / not implemented | **Fixed** |
| `docs/build-roadmap.md` Future table | Resume + GitHub false negatives | **Fixed**; NEXT has RESUME-GATE/TEST notes |
| `daily-coder-ecosystem/README.md` | RF CLI resume in gaps | **Fixed** |
| `docs/README.md` hub | Corpus-only; missing truth table | **Fixed** — code hub + `#supported-today-truth-table` |
| Checklist → truth table link | Broken anchor | **Fixed** via restored README |

---

## Easy-NEXT implementation rows

| Slice | Status |
|-------|--------|
| S2 Agents GUI (nowrap / split / hint) | **CONFIRMED** in `styles.css` + `agents.js` |
| S3a Hub `AGENT_DASHBOARD_TOKEN` | **CONFIRMED** in `server.py` / `__main__.py` |
| S3b DC child argv token | **DEFERRED** |
| S4a LIVE_PROVIDERS CI assert | **CONFIRMED** (`test_live_providers_sync.py` + CI install DC) |
| S4b Import SSOT | **DEFERRED** |
| S5 Resume bundle | **CONFIRMED** |
| S6 Truth table / roadmap | **CONFIRMED** |
| S7 Root ruff/mypy | **DEFERRED** |
| S8 Docker sandbox test | **DEFERRED** |

---

## S0b test attachment

Re-run recorded when executing this refresh (see agent session logs). Green package tests do **not** by themselves close **REC-04** or remaining **REC-02** live-adapter scope.
