"""Recognize concrete executed-test evidence from supported runner summaries."""
import re
from pathlib import PurePath

def runner_for(argv):
    if not isinstance(argv,list) or not argv: return None
    executable=PurePath(str(argv[0])).name
    if executable in {"pytest","py.test","pytest.exe","py.test.exe"}: return "pytest"
    if executable.startswith("python"):
        for index,arg in enumerate(argv[:-1]):
            if arg=="-m" and argv[index+1] in {"unittest","pytest"}: return argv[index+1]
    return None

def execution_evidence(argv,result):
    runner=runner_for(argv)
    evidence={"runner":runner,"recognized":runner is not None,"executed_tests":None,"skipped_tests":None,
              "positive":runner is None,"reason":"Explicit assertion command uses recorded argv and exit status"}
    if runner is None: return evidence
    text="\n".join(str(result.get(key,"")) for key in ("stdout","stderr"))
    text=re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]","",text)
    evidence.update(positive=False,reason="Recognized test runner has no unambiguous positive execution summary")
    if runner=="unittest":
        counts=re.findall(r"(?m)^Ran (\d+) tests? in [^\r\n]+$",text)
        summaries=re.findall(r"(?m)^OK(?: \(([^\r\n]*)\))?\s*$",text)
        if len(counts)!=1 or len(summaries)!=1: return evidence
        total=int(counts[0]); skipped_values=re.findall(r"(?:^|,\s*)skipped=(\d+)(?:,|$)",summaries[0])
        skipped=int(skipped_values[0]) if len(skipped_values)==1 else 0
        if len(skipped_values)>1 or skipped>total: return evidence
    else:
        summaries=[]
        for line in text.splitlines():
            line=line.strip().strip("=").strip()
            match=re.fullmatch(r"((?:\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)(?:, )?)+) in [^\r\n]+",line)
            if match: summaries.append(match.group(1))
            elif re.fullmatch(r"(?:no tests ran|no tests collected)(?: in [^\r\n]+)?",line): summaries.append("")
        if len(summaries)!=1: return evidence
        pairs=re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)",summaries[0])
        counts={}
        for count,status in pairs:
            status={"error":"errors","warning":"warnings"}.get(status,status)
            if status in counts: return evidence
            counts[status]=int(count)
        skipped=counts.get("skipped",0)
        total=sum(counts.get(status,0) for status in ("passed","failed","errors","skipped","xfailed","xpassed"))
        if counts.get("failed",0) or counts.get("errors",0): return evidence
    executed=total-skipped
    evidence.update(executed_tests=executed,skipped_tests=skipped,positive=executed>0,
                    reason="Positive executed-test summary" if executed>0 else "No non-skipped tests executed")
    return evidence
