# Variant `ads-marketing` — Writing Studio

Platform-sized ad variants with explicit compliance review flags.

## When to use
- Promos, search/social ads, landing hooks with stated limits.

## When not
- Long-form product docs → tech-doc. Unverifiable claims without flagging → fix before send.

Paste `AGENT_MESSAGE.md` with packet field `browser_variant: "ads-marketing"`.

For send-critical output: run `document-reviewer` in a **new chat** after this variant.
