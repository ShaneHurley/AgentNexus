"""Recognize concrete executed-test evidence from supported runner summaries."""
import json
import re
from pathlib import PurePath

def runner_for(argv):
    if not isinstance(argv,list) or not argv: return None
    executable=PurePath(str(argv[0])).name
    if executable in {"pytest","py.test","pytest.exe","py.test.exe"}: return "pytest"
    if executable.startswith("python"):
        for index,arg in enumerate(argv[:-1]):
            if arg=="-m" and argv[index+1] in {"unittest","pytest"}: return argv[index+1]
    args=argv[1:]
    if executable in {"node","node.exe"}:
        for arg in args:
            if arg=="--": break
            if arg=="--test": return "node-test"
    if executable in {"npm","npm.cmd","npm.exe"} and args:
        if args[0] in {"test","t","tst"}: return "npm-test"
        if args[0] in {"run","run-script"} and len(args)>1 and args[1] in {"test","t","tst"}: return "npm-test"
    if executable in {"npx","npx.cmd","npx.exe"}:
        while args and args[0] in {"--yes","-y","--no-install"}: args=args[1:]
        if args and args[0]=="--": args=args[1:]
        if not args: return None
        executable=PurePath(str(args[0])).name
        args=args[1:]
    for runner in ("jest","vitest","playwright"):
        if executable in {runner,runner+".cmd",runner+".exe"}:
            if runner!="playwright" or (args and args[0]=="test"): return runner
    return None

def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError("Duplicate JSON field")
        result[key]=value
    return result

def _reject_constant(value):
    raise ValueError("Nonstandard JSON constant")

def _javascript_evidence(runner,result):
    # These bindings must be supplied independently by the trusted caller.
    evidence={"runner":runner,"recognized":True,"executed_tests":None,"skipped_tests":None,
              "positive":False,"reason":"Invalid JavaScript process status"}
    if type(result.get("returncode")) is not int or result["returncode"]!=0: return evidence
    if any(result.get(key,False) for key in ("timeout","timed_out","cancelled")): return evidence
    evidence["reason"]="Missing or invalid JavaScript report"
    raw=result.get("js_report")
    if not isinstance(raw,str): return evidence
    try:
        report=json.loads(raw,object_pairs_hook=_unique_object,parse_constant=_reject_constant)
    except (ValueError,TypeError,RecursionError):
        return evidence
    fields={"version","runner","execution_nonce","source_snapshot_sha256","passed","failed","skipped","interrupted"}
    if not isinstance(report,dict) or set(report)!=fields: return evidence
    if type(report["version"]) is not int or report["version"]!=1: return evidence
    for key in ("passed","failed","skipped","interrupted"):
        if type(report[key]) is not int or report[key]<0: return evidence
    evidence["reason"]="Invalid JavaScript report bindings"
    expected=result.get("expected_runner")
    if not isinstance(expected,str) or not isinstance(report["runner"],str): return evidence
    if report["runner"]!=runner or expected!=runner: return evidence
    nonce=result.get("execution_nonce")
    report_nonce=report["execution_nonce"]
    if not isinstance(nonce,str) or not nonce.strip(): return evidence
    if not isinstance(report_nonce,str) or not report_nonce.strip() or report_nonce!=nonce: return evidence
    digest=result.get("source_snapshot_sha256")
    report_digest=report["source_snapshot_sha256"]
    if not isinstance(digest,str) or re.fullmatch(r"[0-9a-fA-F]{64}",digest) is None: return evidence
    if not isinstance(report_digest,str) or re.fullmatch(r"[0-9a-fA-F]{64}",report_digest) is None: return evidence
    if digest!=report_digest: return evidence
    evidence.update(executed_tests=report["passed"]+report["failed"]+report["interrupted"],skipped_tests=report["skipped"])
    if report["failed"] or report["interrupted"]:
        evidence["reason"]="JavaScript report contains failed or interrupted tests"
    elif not report["passed"]:
        evidence["reason"]="No passed JavaScript tests executed"
    else:
        evidence.update(positive=True,reason="Positive bound JavaScript test report")
    return evidence

def execution_evidence(argv,result):
    runner=runner_for(argv)
    if runner in {"node-test","npm-test","jest","vitest","playwright"}:
        return _javascript_evidence(runner,result)
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
