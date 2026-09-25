"""Shared HTTP helper for hosted providers. Standard library only."""
from __future__ import annotations
import json, time, urllib.error, urllib.request

class ProviderError(RuntimeError): pass

RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504}
TOOL_RESULT_MAX_CHARS = 12000

def post_json(url, payload, headers, timeout=180, retries=3):
    body = json.dumps(payload).encode("utf-8")
    last = None
    for attempt in range(retries):
        request = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            last = ProviderError(f"HTTP {exc.code}: {detail}")
            if exc.code not in RETRYABLE:
                raise last
        except OSError as exc:
            last = ProviderError(str(exc))
        time.sleep(min(2 ** attempt, 8))
    raise last or ProviderError("request failed")

def extract_json(text):
    """Models sometimes wrap JSON in prose or fences. Recover the first complete object."""
    if not text:
        raise ProviderError("empty model response")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    start = stripped.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if escape:
                escape = False; continue
            if ch == "\\":
                escape = True; continue
            if ch == '"':
                in_string = not in_string; continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start:i + 1])
                    except ValueError:
                        break
        start = stripped.find("{", start + 1)
    raise ProviderError(f"model did not return JSON: {text[:300]}")

def json_instruction(schema):
    if not schema:
        return "\n\nReturn ONLY a single JSON object. No prose, no code fences."
    return ("\n\nReturn ONLY a single JSON object matching this schema. No prose, no code fences.\n"
              + json.dumps(schema, separators=(",", ":"))[:4000])

def schema_field_list(schema):
    """Compact required + property names only; never dump full schema JSON."""
    if not schema:
        return ""
    props = list((schema.get("properties") or {}).keys())
    req = list(schema.get("required") or [])
    return json.dumps({"required": req, "properties": props}, separators=(",", ":"))

def json_instruction_compact(schema):
    return ("\n\nReturn ONLY a single JSON object. Keys must include required fields. "
            "Full validation is server-side.\n" + schema_field_list(schema))

def tool_result_text(result):
    return json.dumps(result, separators=(",", ":"), default=str)[:TOOL_RESULT_MAX_CHARS]
