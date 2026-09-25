import re
from pathlib import Path

ROOT = Path(r"c:\Users\WZ69B7\Downloads\research-forge")
extract = (ROOT / "_extract_sec19.txt").read_text(encoding="utf-8")
body_core = (ROOT / "_body_core.txt").read_text(encoding="utf-8")
body_tail = (ROOT / "_body_tail.txt").read_text(encoding="utf-8")

todo_map = [
    ("g0-a-decisions", "#### Group G0-A", "Gate G0 acceptance"),
    ("g0-b-handoff", "#### Group G0-B", "Gate G0 acceptance"),
    ("w0-a-scaffold", "### W0-A —", "Wave 0 exit gate"),
    ("w0-b-schemas", "### W0-B —", "Wave 0 exit gate"),
    ("w0-c-ledger", "### W0-C —", "Wave 0 exit gate"),
    ("w0-d-registries", "### W0-D —", "Wave 0 exit gate"),
    ("w0-e-policy", "### W0-E —", "Wave 0 exit gate"),
    ("w0-f-budget", "### W0-F —", "Wave 0 exit gate"),
    ("w0-g-mock", "### W0-G —", "Wave 0 exit gate"),
    ("w0-h-hash", "### W0-H —", "Wave 0 exit gate"),
    ("w0-i-exit", "### W0-I —", "Wave 0 exit gate"),
    ("w1-a-livegate", "### W1-A —", "Wave 1 exit gate"),
    ("w1-b-clarifier", "### W1-B —", "Wave 1 exit gate"),
    ("w1-c-charter", "### W1-C —", "Wave 1 exit gate"),
    ("w1-d-search", "### W1-D —", "Wave 1 exit gate"),
    ("w1-e-reader", "### W1-E —", "Wave 1 exit gate"),
    ("w1-f-extractor", "### W1-F —", "Wave 1 exit gate"),
    ("w1-g-verifier", "### W1-G —", "Wave 1 exit gate"),
    ("w1-h-composer", "### W1-H —", "Wave 1 exit gate"),
    ("w1-i-orch", "### W1-I —", "Wave 1 exit gate"),
    ("w1-j-baseline", "### W1-J —", "Wave 1 exit gate"),
    ("w2-a-landscape", "### W2-A —", "Wave 2 exit gate"),
    ("w2-b-scout", "### W2-B —", "Wave 2 exit gate"),
    ("w2-c-scheduler", "### W2-C —", "Wave 2 exit gate"),
    ("w2-d-curator", "### W2-D —", "Wave 2 exit gate"),
    ("w2-e-saturation", "### W2-E —", "Wave 2 exit gate"),
    ("w2-f-context", "### W2-F —", "Wave 2 exit gate"),
    ("w2-g-dashboard", "### W2-G —", "Wave 2 exit gate"),
    ("w2-h-exit", "### W2-H —", "Wave 2 exit gate"),
    ("w3-a-methods", "### W3-A —", "Wave 3 exit gate"),
    ("w3-b-contradiction", "### W3-B —", "Wave 3 exit gate"),
    ("w3-c-skeptic", "### W3-C —", "Wave 3 exit gate"),
    ("w3-d-falsify", "### W3-D —", "Wave 3 exit gate"),
    ("w3-e-followup", "### W3-E —", "Wave 3 exit gate"),
    ("w3-f-auditor", "### W3-F —", "Wave 3 exit gate"),
    ("w3-g-exit", "### W3-G —", "Wave 3 exit gate"),
    ("w4-a-ideators", "### W4-A —", "Wave 4 exit gate"),
    ("w4-b-portfolio", "### W4-B —", "Wave 4 exit gate"),
    ("w4-c-fusion", "### W4-C —", "Wave 4 exit gate"),
    ("w4-d-experiment", "### W4-D —", "Wave 4 exit gate"),
    ("w4-e-fabrication", "### W4-E —", "Wave 4 exit gate"),
    ("w4-f-exit", "### W4-F —", "Wave 4 exit gate"),
    ("w5-a-packet", "### W5-A —", "Wave 5 exit gate"),
    ("w5-b-director", "### W5-B —", "Wave 5 exit gate"),
    ("w5-c-handofftax", "### W5-C —", "Wave 5 exit gate"),
    ("w5-d-challenge", "### W5-D —", "Wave 5 exit gate"),
    ("w5-e-exit", "### W5-E —", "Wave 5 exit gate"),
    ("w6-a-sdk", "### W6-A —", "Wave 6 exit gate"),
    ("w6-b-adapters", "### W6-B —", "Wave 6 exit gate"),
    ("w6-c-skills", "### W6-C —", "Wave 6 exit gate"),
    ("w6-d-routing", "### W6-D —", "Wave 6 exit gate"),
    ("w6-e-proposals", "### W6-E —", "Wave 6 exit gate"),
    ("w6-f-maintain", "### W6-F —", "Wave 6 exit gate"),
]

gates = {}
for m in re.finditer(
    r"\*\*(Gate G0 acceptance|Wave [0-6] exit gate):\*\* (.+)", extract
):
    gates[m.group(1)] = m.group(2)


def slice_group(header_prefix):
    start = extract.find(header_prefix)
    if start == -1:
        raise KeyError(header_prefix)
    rest = extract[start + 1 :]
    nxt = len(rest)
    for pat in [r"\n#### Group ", r"\n### W", r"\n## Wave", r"\n## 19\.2"]:
        m = re.search(pat, rest)
        if m and m.start() < nxt:
            nxt = m.start()
    block = extract[start : start + 1 + nxt]
    ids = re.findall(r"\*\*(RF-[A-Z0-9-]+)", block)
    return ids[0], ids[-1]


overview = (
    "Build Research Forge — a standalone, read-only, evidence-first deep research agent with "
    "weak-model-safe one-card-at-a-time task execution, clarification and Research Charter gates, "
    "multi-lane fan-out, claim verification, idea portfolios, adversarial scrutiny, compressed "
    "Principal Research Director synthesis, and doctoral-grade human + machine packets under hard budgets."
)

parts = ["---", "name: Research Forge", f'overview: "{overview}"', "todos:"]
for tid, hdr, gate_key in todo_map:
    first, last = slice_group(hdr)
    done = gates[gate_key]
    content = f"{first}–{last}; Done when: {done}"
    esc = content.replace('"', '\\"')
    parts.extend([f"  - id: {tid}", f'    content: "{esc}"', "    status: pending"])
parts.extend(["isProject: false", "---", ""])

intro = """**This plan supersedes the shorter deep-researcher ecosystem draft.** It incorporates the user's Research Forge master build specification and the full detailed work-breakdown (§19 WBS with RF-* task cards).

# Research Forge — Master Build Plan

**Working name:** Research Forge  
**Status:** Design specification locked into this plan; **implementation NOT authorized** until you explicitly say execute  
**Authority:** Complete WBS and gates below are binding once execution is approved.

"""

section19 = """## 19. Detailed implementation waves and WBS (§19)

When execution is approved, implement in wave order. Every checkbox below is an independent task card for weak models.

## How weak models execute

"""

auth = """
---

**Authorization reminder:** Implementation is **NOT authorized** until you explicitly approve execution. Gate G0 (§21 decisions + §22 handoff) must pass before live Wave 1+; Wave 0 scaffold may proceed only with accepted UNKNOWNs as specified in §19.1.
"""

full = (
    "\n".join(parts)
    + intro
    + body_core
    + "\n\n"
    + section19
    + extract
    + "\n\n"
    + body_tail
    + auth
)

out_path = Path(
    r"c:\Users\WZ69B7\.cursor\plans\deep_researcher_ecosystem_38ffc398.plan.md"
)
out_path.write_text(full, encoding="utf-8")
count = sum(1 for ln in full.split("\n") if ln.startswith("- [ ] **RF-"))
print("checkboxes_output", count)
print("todos", len(todo_map))
