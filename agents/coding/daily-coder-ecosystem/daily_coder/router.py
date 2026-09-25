import re
from .workflow import workflow_for

HIGH_RISK={"migration","database","schema","security","authentication","authorization","concurrency","delete","payment","production","public api","breaking"}
AMBIGUOUS={"unclear","investigate","unknown","compare options","figure out","not sure"}
TRIVIAL={
    "typo","rename","comment","docstring","bump version","changelog",
    "spelling","whitespace","formatting","lint fix","fix lint","cosmetic",
    "punctuation","missing period","add period","readme typo","update comment",
    "one-line","single line","single-line",
}

def _trivial_phrase(t):
    return any(x in t for x in TRIVIAL)

def trivial_signal_for(text, score):
    """True only for contained S requests with a trivial phrase (no multi-file/risk/design load)."""
    t=text.lower()
    if score != 0 or not _trivial_phrase(t):
        return False
    files=re.search(r'\b(\d+)\s+files?\b',t)
    if files and int(files.group(1)) > 1:
        return False
    if any(x in t for x in HIGH_RISK):
        return False
    return True

def size_request(text):
    t=text.lower(); score=0; reasons=[]
    files=re.search(r'\b(\d+)\s+files?\b',t)
    if files and int(files.group(1))>3: score+=2; reasons.append("multi-file")
    hits=sorted(x for x in HIGH_RISK if x in t)
    if hits: score+=3; reasons.append("risk:"+",".join(hits))
    if any(x in t for x in ["refactor","architecture","cross-cutting","new system"]): score+=2; reasons.append("broad-design")
    ambiguity=sorted(x for x in AMBIGUOUS if x in t)
    if ambiguity: score+=1; reasons.append("ambiguity:"+",".join(ambiguity))
    profile="S" if score==0 else "M" if score<=2 else "L" if score<=5 else "XL"
    trivial=trivial_signal_for(text, score)
    return {"profile":profile,"score":score,"reasons":reasons or ["contained-explicit-request"],
            "ambiguous":bool(ambiguity) and score<=2,
            "trivial_signal":trivial}

def workflow_key(profile, trivial_signal=False):
    """Map profile + trivial signal to a durable workflow key."""
    if profile == "S" and trivial_signal:
        return "S_TRIVIAL"
    return profile

def phases_for(profile_or_workflow: str):
    return workflow_for(profile_or_workflow)
