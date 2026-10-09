# DeepSeek (V3 & R1): AgentNexus Integration Guide

This guide details how to integrate **DeepSeek V3** and the **DeepSeek R1 Reasoning Model** as high-rigor, cost-effective workers in **AgentNexus**.

---

## 1. DeepSeek's Role in AgentNexus: The Adversarial Engine

DeepSeek provides two top-tier models:
1. **DeepSeek R1**: Advanced reasoning model with transparent chain-of-thought. In AgentNexus, R1 is assigned to high-cognition review roles:
   - `adversarial-skeptic`
   - `plan-reviewer`
   - `code-reviewer`
   - `failure-diagnostician`
2. **DeepSeek V3**: Fast general-purpose coding and instruction-following model. Ideal for `implementer`, `test-author`, and `documenter`.

Both models are accessible **100% free** on the DeepSeek web interface (`https://chat.deepseek.com`), and at ultra-low pricing on the DeepSeek API (\$0.14/\$0.28 per million tokens with free signup credits).

---

## 2. Using DeepSeek Web (Free R1 Reasoning) for Plan Review

According to AgentNexus architectural doctrine, an implementation plan must pass an adversarial review before mutating code is written.

1. Generate your draft plan using `plan-prep` or `use-master`.
2. Open `https://chat.deepseek.com` and toggle the **"DeepThink (R1)"** button ON.
3. Paste the prompt from [`r1_adversarial_reviewer.md`](./r1_adversarial_reviewer.md) along with your draft plan.
4. DeepSeek R1 will generate a deep chain-of-thought audit, testing:
   - Hidden edge cases and boundary failures.
   - Regressions in unchanged files.
   - Security vulnerabilities and secret exposure.
   - Missing negative test cases.
5. If R1 returns `VERDICT: PASS`, proceed to execution. If `VERDICT: REVISE`, adjust your plan before writing code.

---

## 3. Integrating DeepSeek API with Daily Coder

DeepSeek provides an OpenAI-compatible endpoint:
- **Base URL**: `https://api.deepseek.com/v1`
- **Models**: `deepseek-chat` (V3), `deepseek-reasoner` (R1)

Run the included integration script to verify connectivity and test DeepSeek against your local code:
```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
python implementing/deepseek/api_integration.py --review "src/my_module.py"
```

In Daily Coder's `models.json` configuration, map `frontier` or `reasoning` tiers to DeepSeek:
```json
{
  "provider": "openai",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-reasoner",
  "api_key_env": "DEEPSEEK_API_KEY"
}
```
