"""Version 1 capability contract schemas, shared by compilation and consumers."""
CAPABILITY_ARRAY={"type":"array","items":{"type":"string","minLength":1},"uniqueItems":True}
GRANT_SCHEMA={"type":"object","additionalProperties":False,"properties":{
    **{name:CAPABILITY_ARRAY for name in ("tools","skills","delegation","memory_read","memory_write","workspace_roots","write_roots")},
    "resources":{"type":"object","additionalProperties":{"type":"number","minimum":0}}}}
ROLE_SCHEMA={"type":"object","required":["id","version","responsibilities","prohibitions","installed","active","leaf","user_invocable","callers","grant","input_schema","output_schema","content_hash"],"properties":{
    "id":{"type":"string","minLength":1},"version":{"type":"string","minLength":1},
    **{name:{"type":"boolean"} for name in ("installed","active","leaf","user_invocable","workspace_access")},
    **{name:CAPABILITY_ARRAY for name in ("responsibilities","prohibitions","callers","approval_conditions","escalation_conditions","artifact_destinations","model_requirements")},
    "grant":GRANT_SCHEMA,"content_hash":{"type":"string","pattern":"^[a-f0-9]{64}$"}}}
