#!/usr/bin/env python3
"""DeepSeek API Integration Client for AgentNexus.

Supports invoking DeepSeek V3 (deepseek-chat) and DeepSeek R1 (deepseek-reasoner)
for adversarial plan reviews and code reviews.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from agent_core.rate_limiter import RateLimiter, RateLimiterConfig

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


_standalone_limiter: RateLimiter | None = None


def _get_limiter() -> RateLimiter:
    global _standalone_limiter
    if _standalone_limiter is None:
        _standalone_limiter = RateLimiter(RateLimiterConfig.from_env())
    return _standalone_limiter


def call_deepseek(model: str, messages: list[dict[str, str]], api_key: str, temperature: float = 0.2) -> str:
    _get_limiter().acquire()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096
    }

    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]["message"]
            reasoning = choice.get("reasoning_content")
            content = choice.get("content", "")
            if reasoning:
                return f"[DeepSeek R1 Thinking]\n{reasoning}\n\n[Verdict & Output]\n{content}"
            return content
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        print(f"DeepSeek API Error ({e.code}): {err}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek AgentNexus Review Client")
    parser.add_argument("--plan", help="Path to implementation plan file to review adversarially")
    parser.add_argument("--code", help="Path to source code file to review")
    parser.add_argument("--model", default="deepseek-reasoner", choices=["deepseek-reasoner", "deepseek-chat"])
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    if args.plan:
        plan_content = Path(args.plan).read_text(encoding="utf-8")
        sys_prompt = "You are plan-reviewer from AgentNexus. Adversarially audit this plan. Find failure points, missing tests, and regression hazards. Return PASS, REVISE, or BLOCKED."
        user_content = f"Plan to review:\n\n{plan_content}"
    elif args.code:
        code_content = Path(args.code).read_text(encoding="utf-8")
        sys_prompt = "You are code-reviewer from AgentNexus. Adversarially review this code for bugs, edge cases, and missing tests."
        user_content = f"Code to review:\n\n{code_content}"
    else:
        print("Specify either --plan <path> or --code <path>")
        return 1

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content}
    ]

    print(f"[DeepSeek] Calling {args.model}...")
    result = call_deepseek(args.model, messages, api_key)
    print("\n" + "=" * 60)
    print(result)
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
