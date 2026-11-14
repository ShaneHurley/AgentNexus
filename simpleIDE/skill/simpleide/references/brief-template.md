# Brief template

Include `TASK: <slug>` so hooks and the ledger associate the dispatch with the open task.

A brief is everything the receiving agent will know. Write it so someone who has never seen this conversation could do the job. Aim for 10-25 lines.

```
TASK: <slug>

GOAL:
<one or two sentences: the outcome, and what it is for>

CONTEXT:
Execution root: <worker checkout>. Runtime: <installed SX command>.
Task/store ID and parent store path: <identities>. Readable request/criteria: <artifact path and hash>.
<paths, symbols, commands, record ids (P12) to read. Facts already established.
 Point to things; do not paste files or conversation.>

DO:
<the concrete work. Name interfaces and file locations already decided.>

DO NOT TOUCH:
<files, behaviour and scope that must stay as they are>

DONE WHEN:
<checkable conditions: a command that passes, a file that exists, criterion numbers>

RETURN:
<use your standard return block. Add anything specific you need back.>
```

## Example

```
TASK: export-streaming

GOAL:
Requests to /api/export time out after 30s on large accounts. Make the export
stream rows instead of building the whole file in memory.

CONTEXT:
Handler: src/api/export.py: export_csv(). Query helper: src/db/rows.py: fetch_rows().
fetch_rows already accepts chunk_size. Decision P14: keep the CSV column order.

DO:
Change export_csv to return a streaming response that writes rows in chunks of 1000.

DO NOT TOUCH:
The CSV format, src/db/rows.py, the route path, authentication.

DONE WHEN:
pytest tests/api/test_export.py passes, and peak memory no longer grows with row
count (the test at tests/api/test_export.py::test_streams covers this).

RETURN:
Standard block.
```

## Checks before sending

- Could the agent do this without asking you anything? If not, add what is missing.
- Is there exactly one outcome? Two outcomes means two briefs.
- Is "done" something a command or a reader can verify?
- Did you paste something that could have been a path? Replace it with the path.
