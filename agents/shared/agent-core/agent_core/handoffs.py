"""Presentation recovery without granting authority or inventing verdicts."""
from __future__ import annotations
import hashlib,json
import jsonschema

ALIASES={"files_changed":"changed_files"}
SENSITIVE_KEYS=frozenset({"apikey","secret","secretkey","clientsecret","password","passwd","token","accesstoken","refreshtoken","idtoken","bearer","authorization","privatekey","credentials"})
def _mask_quoted_keys(text,depth=0):
    if depth>8: return "[REDACTED nested raw value]"
    decoder=json.JSONDecoder()
    edits=[]; index=0
    while index<len(text):
        if text[index]!='"':
            index+=1; continue
        try: value,end=decoder.raw_decode(text,index)
        except ValueError:
            index+=1; continue
        if not isinstance(value,str):
            index=end; continue
        following=end
        while following<len(text) and text[following].isspace(): following+=1
        key="".join(char for char in value.lower() if char not in "_- ")
        if following<len(text) and text[following]==":" and key in SENSITIVE_KEYS:
            beginning=following+1
            while beginning<len(text) and text[beginning].isspace(): beginning+=1
            try: _,value_end=decoder.raw_decode(text,beginning)
            except ValueError: value_end=len(text)
            edits.append((beginning,value_end,'"'+ "[REDACTED]" +'"'))
            index=value_end
        else:
            clean=_mask_quoted_keys(value,depth+1) if '"' in value else value
            if clean!=value: edits.append((index,end,json.dumps(clean,ensure_ascii=False)))
            index=end
    for beginning,end,replacement in reversed(edits):
        text=text[:beginning]+replacement+text[end:]
    return text

def sanitized_raw(value):
    from daily_coder.tool_broker import redact
    raw=value if isinstance(value,str) else json.dumps(value,sort_keys=True,default=str)
    bounded=raw.encode()[:32000].decode(errors="replace")
    clean=redact(_mask_quoted_keys(bounded))
    return clean.encode()[:32000].decode(errors="ignore")
def normalize(value,schema):
    serialized=value if isinstance(value,str) else json.dumps(value,sort_keys=True,default=str)
    if len(serialized.encode())>32000:
        return None,["role output exceeds recovery bound"]
    candidates=[]
    def consider(item):
        if isinstance(item,dict):
            item=dict(item)
            for old,new in ALIASES.items():
                if old in item and new not in item and new in schema.get("properties",{}):
                    item[new]=item.pop(old)
        try: jsonschema.validate(item,schema)
        except jsonschema.ValidationError: return
        candidates.append(item)
    if not isinstance(value,str):
        consider(value)
    else:
        text=value.lstrip("\ufeff").strip()
        if text.startswith("```") and text.endswith("```"):
            lines=text.splitlines()
            if len(lines)>=3: text="\n".join(lines[1:-1]).strip()
        try: consider(json.loads(text))
        except ValueError: pass
        if not candidates:
            decoder=json.JSONDecoder()
            for index,char in enumerate(text):
                if char not in "{[": continue
                try: item,_=decoder.raw_decode(text,index)
                except ValueError: continue
                consider(item)
    if len(candidates)==1:
        return candidates[0],[]
    return None,["ambiguous schema-valid objects" if len(candidates)>1 else "role output incomplete or invalid"]
def incomplete(value,*,run_id,role,phase,invocation_id,recipient,contract_hash):
    raw=sanitized_raw(value)
    return {"_incomplete_handoff":{"schema_version":1,"run_id":run_id,"producer":role,"recipient":recipient,"phase":phase,"invocation_id":invocation_id,"task_contract_hash":contract_hash,"raw":raw,"raw_sha256":hashlib.sha256(raw.encode()).hexdigest(),"validation_problems":["role output incomplete or invalid"],"payload":None,"delivery":"pending","acknowledgment":"pending"}}
def is_incomplete(value):
    return isinstance(value,dict) and "_incomplete_handoff" in value
