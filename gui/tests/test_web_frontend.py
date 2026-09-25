"""Focused frontend module checks (markdown XSS, GFM tables, layout redistribution)."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "agent_dashboard" / "web"


def _node_available() -> bool:
    return shutil.which("node") is not None


@unittest.skipUnless(_node_available(), "node required for ES module tests")
class WebFrontendTests(unittest.TestCase):
    def test_markdown_escapes_script(self):
        script = """
        import { renderMarkdown } from './markdown.js';
        const html = renderMarkdown('<script>alert(1)</script>\\n**bold**');
        if (html.includes('<script>')) throw new Error('raw script tag');
        if (!html.includes('&lt;script&gt;')) throw new Error('expected escaped script');
        console.log('ok');
        """
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_markdown_gfm_table(self):
        script = r"""
        import { renderMarkdown } from './markdown.js';
        const src = [
          '| Name | Role |',
          '| --- | --- |',
          '| Ada | Lead |',
          '| Bob | <script>x</script> |',
        ].join('\n');
        const html = renderMarkdown(src);
        if (!html.includes('class="md-table"')) throw new Error('missing md-table: ' + html);
        if (!html.includes('<th>')) throw new Error('missing th');
        if (!html.includes('<td>')) throw new Error('missing td');
        if (!html.includes('table-wrap')) throw new Error('missing table-wrap');
        if (html.includes('<script>')) throw new Error('raw script in cell');
        if (!html.includes('&lt;script&gt;')) throw new Error('expected escaped script in cell');
        if (!html.includes('Ada')) throw new Error('missing cell text');
        console.log('ok');
        """
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_markdown_gfm_table_not_paragraph(self):
        script = r"""
        import { renderMarkdown } from './markdown.js';
        const src = 'Before\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nAfter';
        const html = renderMarkdown(src);
        if (!html.includes('md-table')) throw new Error('table missing');
        if (html.includes('<p>| A |')) throw new Error('table leaked into paragraph');
        console.log('ok');
        """
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_layout_redistribute_round_robin(self):
        script = """
        import { redistribute } from './ide/layout.js';
        const old = [
          { id: 0, tabs: [{ id: 'a' }, { id: 'b' }], activeTabId: 'b' },
          { id: 1, tabs: [{ id: 'c' }], activeTabId: 'c' },
        ];
        const { panes, activePaneId } = redistribute(old, 'quarters', 1);
        if (panes.length !== 4) throw new Error('expected 4 panes');
        const flat = panes.flatMap(p => p.tabs.map(t => t.id));
        if (flat.join(',') !== 'a,b,c') throw new Error('round robin mismatch: ' + flat);
        if (activePaneId !== 1) throw new Error('active pane');
        console.log('ok');
        """
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=str(WEB),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
