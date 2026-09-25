# Mission Control

Browser **phase conductor**: splits long missions into sequential chats with explicit handoffs to research-desk, code-crafter (with self-review), code-reviewer, document-reviewer, and closeout.

## Why it exists
Mega-prompts blow context. Mission control keeps each chat bounded and names the exact next paste path.

## vs IDE /use-master
This family **routes** only. It does not execute the DAG, bridge, or multi-agent fan-out. Use IDE `/use-master` when the repo supports audited orchestration.

## Honest sequencing
Independent reviews (code-reviewer, document-reviewer) always require a **new chat** from the author/implement chat.
