# Zhipu AI GLM (GLM-4 & BigModel): AgentNexus Integration Guide

This guide details how to integrate **Zhipu AI's GLM** models (GLM-4, GLM-4-Flash, GLM-Zero) into the **AgentNexus** ecosystem.

---

## 1. GLM's Role in AgentNexus

Zhipu GLM models excel in structured extraction, bilingual (Chinese/English) technical reasoning, and document curation. In AgentNexus, GLM is assigned to:
- **`structured-data-extractor`**: Converting messy logs, CSVs, and API responses into strictly typed fact tables.
- **`data-evaluator`**: Checking math, boundary limits, and statistical consistency.
- **`documentation-curator`**: Polishing and formatting reviewed technical documentation across Markdown and bilingual code comments.

---

## 2. Accessing Free GLM Tiers

### A. Free Web Interface
Access `https://chatglm.cn` for zero-cost interactive access to GLM-4. It supports file uploads, web browsing, and code analysis.

### B. BigModel Open Platform (Free Token Grants)
Zhipu AI offers complimentary starter tokens (up to 25 million free tokens on registration for GLM-4-Flash / open platform):
- Sign up at `https://open.bigmodel.cn`.
- Obtain your API key from the developer console.
- GLM-4-Flash is permanently free or ultra-low cost for developer API calls.

---

## 3. Running Structured Data Extraction with GLM

When you need to extract dense parameters from unstructured specs or datasheets:
1. Open ChatGLM or call the BigModel API.
2. Use the structured prompt template in [`structured_data_extractor_prompt.md`](./structured_data_extractor_prompt.md).
3. GLM will parse the input into a validated, typed fact table with provenance.

---

## 4. API Integration Details

See [`api_setup.md`](./api_setup.md) for curl and Python connection snippets to wire GLM into Daily Coder and Research Forge.
