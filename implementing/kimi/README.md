# Moonshot Kimi: AgentNexus Integration Guide

This guide details how to leverage **Moonshot Kimi (kimi.ai)** as a high-capacity, zero-cost intelligence worker in the **AgentNexus** ecosystem.

---

## 1. Kimi's Superpower: Free 2M Token Context

Moonshot Kimi provides one of the industry's largest and most accessible context windows (up to **2,000,000 tokens**) on its free web platform (`https://kimi.ai` or `https://kimi.moonshot.cn`), as well as complimentary starter credits on the Moonshot Open Platform API.

In AgentNexus, Kimi serves as the primary **Heavy Ingestion Scout**:
- Ingesting entire multi-megabyte code repositories in a single prompt.
- Analyzing massive PDF libraries, academic papers, and technical specifications.
- Performing cross-document contradiction checks without chunking or vector search loss.

---

## 2. Using Kimi Web (100% Free) for Deep Research

When executing a `deep-research` or `plan-prep` workflow where the input evidence exceeds standard IDE context windows (e.g. 50+ files or a 300-page specification):

1. **Pack the Source Material**:
   Use the bundling command in [`batch_ingest_recipe.md`](./batch_ingest_recipe.md) to generate a single markdown file containing all relevant code and docs.
2. **Open Kimi Web**:
   Navigate to `https://kimi.ai` or drag and drop your files directly into the chat input.
3. **Paste the AgentNexus System Prompt**:
   Copy the specialized prompt from [`kimi_system_prompts.md`](./kimi_system_prompts.md) (e.g., `deep-research` or `source-inspector`).
4. **Extract Structured Output**:
   Kimi returns a typed fact table with exact citations (`VERIFIED`, `SUPPORTED`, `UNKNOWN`) that can be pasted directly into `research-messenger` or `use-master`.

---

## 3. Integrating Kimi API with Daily Coder & Research Forge

Moonshot AI provides an OpenAI-compatible API (`https://api.moonshot.cn/v1`):

```bash
# Set your Moonshot API key
export MOONSHOT_API_KEY="your-moonshot-api-key"
```

Configure Daily Coder or Research Forge to route heavy extraction lanes through Kimi:
```json
{
  "provider": "openai",
  "base_url": "https://api.moonshot.cn/v1",
  "model": "moonshot-v1-128k",
  "api_key_env": "MOONSHOT_API_KEY"
}
```

---

## 4. Best Practices & Token Economy

- **Zero Cost Strategy**: Use Kimi Web for all large document and whole-repo scans. It costs \$0.00 and eliminates the need for expensive vector databases.
- **Fact Provenance**: Require Kimi to provide exact file paths and line ranges for every extracted claim.
- **Transfer to Local IDE**: Once Kimi distills a 1,000,000-token corpus into a 3,000-token structured evidence packet, copy that packet into your local IDE (Cursor, VS Code, or Antigravity) to execute the code modifications.
