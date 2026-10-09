# Zhipu BigModel API Setup Guide

This guide explains how to connect Zhipu AI's GLM API into AgentNexus runtimes.

---

## 1. Authentication & API Key

1. Register at `https://open.bigmodel.cn`.
2. Generate an API Key in the API Keys console.
3. Export the key:
   ```bash
   export ZHIPU_API_KEY="your-zhipu-api-key"
   ```

---

## 2. API Endpoint & Models

Zhipu provides an OpenAI-compatible interface:
- **Base URL**: `https://open.bigmodel.cn/api/paas/v4`
- **Models**:
  - `glm-4-flash`: Free tier model with rapid response times and high rate limits.
  - `glm-4-plus`: Frontier reasoning and multi-modal flagship.
  - `glm-zero-preview`: Competitive reasoning model with extended thinking.

---

## 3. Python Verification Snippet

Test connectivity using standard `urllib`:

```python
import json
import os
import urllib.request

api_key = os.environ.get("ZHIPU_API_KEY")
url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

payload = {
    "model": "glm-4-flash",
    "messages": [
        {"role": "user", "content": "Hello! Confirm that AgentNexus GLM integration is operational."}
    ]
}

req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
with urllib.request.urlopen(req) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    print(result["choices"][0]["message"]["content"])
```
