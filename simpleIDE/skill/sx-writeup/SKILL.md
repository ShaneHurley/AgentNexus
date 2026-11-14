---
name: sx-writeup
description: Turn an sx mem export into a concise factual task write-up, or build a style-only voice profile from user-provided writing samples.
---
# Write-up

Run `{SX} mem export --task <slug> --out docs/simpleide/<slug>.md`. Read that export and write a concise document: what was done, why, checks and evidence, and what remains open. Separate implemented, proposed, and unresolved claims. Every factual claim must trace to a record in the export. Read `~/.simpleide/voice.md` if it exists; it changes style only.

# Voice profile

Only when the user provides writing samples, describe the sample's sentence length, vocabulary, level of technical detail, formality, and typical openings/closings in `~/.simpleide/voice.md`. Keep it under 40 lines. Do not infer facts, preferences or opinions beyond writing style. Ask for samples if none exist.
