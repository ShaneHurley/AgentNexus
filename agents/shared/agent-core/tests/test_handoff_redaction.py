import json
from agent_core.handoffs import sanitized_raw

def test_quoted_sensitive_json_values_and_containers_are_redacted():
    canary="FIXTURE_VALUE_MUST_NOT_SURVIVE"
    value={"password":canary,"nested":{"api_key":{"parts":[canary]}},"findings":["ordinary finding"]}
    result=sanitized_raw(value)
    assert canary not in result and "ordinary finding" in result
    parsed=json.loads(result)
    assert parsed["password"]=="[REDACTED]" and parsed["nested"]["api_key"]=="[REDACTED]"

def test_fences_and_nested_json_strings_mask_sensitive_keys():
    canary="FIXTURE_VALUE_MUST_NOT_SURVIVE"
    value='Findings:\n` ` `json\n'+json.dumps({"observations":[json.dumps({"authorization":canary})]})+'\n` ` `'
    assert canary not in sanitized_raw(value)

def test_ordinary_lexical_json_and_fences_are_preserved():
    value='findings:\n` ` `json\n { "changed_files" : ["source.py"] } \n` ` `'
    assert sanitized_raw(value)==value

def test_truncated_sensitive_string_is_fail_closed():
    value='{"password":"'+("FIXTURE_ONLY"*4000)
    result=sanitized_raw(value)
    assert "FIXTURE_ONLY" not in result and "[REDACTED]" in result

def test_redaction_expansion_cannot_exceed_raw_byte_bound():
    value=[{"password":""} for _ in range(2000)]
    assert len(sanitized_raw(value).encode())<=32000
