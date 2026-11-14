## simpleIDE: use the least orchestration that gets a correct result

Size the request; step up only when needed.

| Size | Work | Workflow |
|---|---|---|
| SMALL | question, lookup or contained change | Do it yourself or brief one sx-worker. Check the result. |
| MEDIUM | several steps/files, research or document | Load simpleide; record goal/criteria; up to 3 independent workers, one sx-reviewer pass, written result. |
| LARGE | architecture, high risk or multiple stages | Load simpleide; sx-planner first, workers/tester, reviewer; at most 2 repair rounds. |

- Use shell, Git and existing scripts before model calls. Ask a scout for locations when exploring over five files.
- Briefs include goal, execution path, task/store identity, readable request/criteria file, owned files, exclusions, completion criteria and return format. Never paste entire histories.
- Use the cheapest capable model. After two failures, change the brief or model; no third unchanged attempt.
- Ask about ambiguity affecting objective, permission, compatibility or irreversible action. Otherwise record an assumption and proceed.
- Before MEDIUM/LARGE, run `python3 {MEM} search "<keywords>"`; open relevant IDs. Save verified reusable facts with the memory lesson command; local facts use --local.
- Bind each task explicitly with a captured request or host/session. Record results, then use task close with explicit outcome and evidence. Only an actual user decision supports user-attributed acceptance.
- No subagents available? Perform the roles yourself. Host-native permissions remain authoritative; filesystem installation does not prove hook enforcement.
