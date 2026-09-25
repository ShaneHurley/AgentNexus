import json
from pathlib import Path
class SchemaError(ValueError): pass
class SchemaRegistry:
    def __init__(self,root): self.root=Path(root)
    def validate(self,name,value):
        schema=json.loads((self.root/f"{name}.schema.json").read_text())
        self._check(schema,value,"$"); return value
    def _check(self,s,v,p):
        typ=s.get("type")
        if typ=="object":
            if not isinstance(v,dict): raise SchemaError(f"{p} must be object")
            for k in s.get("required",[]):
                if k not in v: raise SchemaError(f"{p}.{k} is required")
            if s.get("additionalProperties") is False:
                extra=set(v)-set(s.get("properties",{}))
                if extra: raise SchemaError(f"{p} unexpected keys {sorted(extra)}")
            for k,sub in s.get("properties",{}).items():
                if k in v: self._check(sub,v[k],f"{p}.{k}")
        elif typ=="array":
            if not isinstance(v,list): raise SchemaError(f"{p} must be array")
            for i,x in enumerate(v): self._check(s.get("items",{}),x,f"{p}[{i}]")
        elif typ=="string" and not isinstance(v,str): raise SchemaError(f"{p} must be string")
        elif typ=="integer" and (not isinstance(v,int) or isinstance(v,bool)): raise SchemaError(f"{p} must be integer")
        elif typ=="number" and (not isinstance(v,(int,float)) or isinstance(v,bool)): raise SchemaError(f"{p} must be number")
        elif typ=="boolean" and not isinstance(v,bool): raise SchemaError(f"{p} must be boolean")
        if "enum" in s and v not in s["enum"]: raise SchemaError(f"{p} must be one of {s['enum']}")
