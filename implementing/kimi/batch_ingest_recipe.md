# Kimi Batch Codebase Packing Recipe

Use this recipe to pack an entire repository directory into a single structured markdown file that can be dropped into Kimi's 2,000,000 token context window.

---

## 1. Quick Shell One-Liner

Run this command from your terminal to bundle relevant source files into `kimi_bundle.md`:

```bash
python3 -c "
import os
from pathlib import Path

EXTENSIONS = {'.py', '.md', '.json', '.yaml', '.yml', '.ts', '.js', '.sh'}
IGNORE_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache'}

out_file = Path('kimi_bundle.md')
with out_file.open('w', encoding='utf-8') as out:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for f in files:
            p = Path(root) / f
            if p.suffix in EXTENSIONS and p.name != 'kimi_bundle.md':
                try:
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    out.write(f'# File: {p}\n```\n{content}\n```\n\n')
                except Exception as e:
                    pass

print(f'Done! Created {out_file} ({out_file.stat().st_size // 1024} KB). Ready to drop into Kimi!')
"
```

---

## 2. Ingesting into Kimi

1. Open `https://kimi.ai`.
2. Drag and drop `kimi_bundle.md` into the message input area.
3. Paste your query along with the prompt from [`kimi_system_prompts.md`](./kimi_system_prompts.md):
   ```text
   Please analyze the attached repository bundle and answer:
   1. What is the full architectural lifecycle of a Daily Coder run?
   2. Where does PolicyGateway enforce tool write restrictions?
   3. Format the answer as a structured Fact Table with file and line locators.
   ```
4. Copy Kimi's structured response back into your local IDE.
