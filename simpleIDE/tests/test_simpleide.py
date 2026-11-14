"""Run: python3 -m unittest discover -s tests -v   (from the simpleIDE folder)"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None


def run(script, *args, cwd=None, env=None, input=None):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=e,
                       capture_output=True, text=True, input=input)
    return r.returncode, r.stdout + r.stderr


class Mem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.a, self.b, self.home = t / "proj-a", t / "proj-b", t / "home"
        for d in (self.a, self.b, self.home):
            d.mkdir()
        self.mem = ROOT / "core/mem.py"

    def tearDown(self):
        self.tmp.cleanup()

    def m(self, proj, *args, home=None):
        return run(self.mem, *args, cwd=proj,
                   env={"SIMPLEIDE_PROJECT": str(proj), "SIMPLEIDE_HOME": str(home or self.home)})

    def test_add_search_ranked_and_scoped(self):
        self.m(self.a, "add", "decision", "Use streaming export", "--body", "CSV built in chunks of 1000", "--task", "exp")
        self.m(self.a, "add", "finding", "Unrelated note about fonts")
        code, out = self.m(self.a, "search", "streaming csv export")
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[0].startswith("P1 decision"), out)
        _, out = self.m(self.b, "search", "streaming")
        self.assertIn("no matches", out)  # project records do not leak to other projects

    def test_duplicate_not_stored_twice(self):
        self.m(self.a, "add", "goal", "Same goal", "--task", "t")
        _, out = self.m(self.a, "add", "goal", "Same  GOAL", "--task", "t")
        self.assertIn("already recorded", out)

    def test_lesson_is_shared_across_projects(self):
        _, out = self.m(self.a, "lesson", "pytest caches break read-only sandboxes",
                        "--body", "pass -p no:cacheprovider", "--tags", "pytest,sandbox")
        self.assertIn("+ shared", out)
        _, out = self.m(self.b, "search", "pytest sandbox")
        self.assertIn("S1 lesson", out)
        self.assertIn("from=proj-a", out)
        _, out = self.m(self.b, "show", "S1")
        self.assertIn("no:cacheprovider", out)

    def test_local_lesson_stays_local(self):
        self.m(self.a, "lesson", "only here quirk", "--local")
        _, out = self.m(self.b, "search", "quirk")
        self.assertIn("no matches", out)

    def test_unwritable_shared_db_queues_then_syncs(self):
        blocker = Path(self.tmp.name) / "afile"
        blocker.write_text("x")  # SIMPLEIDE_HOME under a file -> cannot be created
        _, out = self.m(self.a, "lesson", "queued lesson", "--body", "b", home=blocker / "sub")
        self.assertIn("queued", out)
        _, out = self.m(self.a, "stats")
        self.assertIn("1 lesson(s) waiting", out)
        _, out = self.m(self.a, "sync")
        self.assertIn("synced 1", out)
        _, out = self.m(self.b, "search", "queued")
        self.assertIn("S1 lesson", out)

    def test_export_and_forget(self):
        self.m(self.a, "add", "goal", "Ship it", "--task", "t1")
        self.m(self.a, "add", "criteria", "Tests pass", "--task", "t1")
        self.m(self.a, "add", "goal", "Other task", "--task", "t2")
        out_file = self.a / "docs/x.md"
        self.m(self.a, "export", "--task", "t1", "--out", str(out_file))
        text = out_file.read_text()
        self.assertIn("## Goal", text)
        self.assertIn("## Acceptance criteria", text)
        self.assertNotIn("Other task", text)
        self.m(self.a, "forget", "P1")
        _, out = self.m(self.a, "search", "ship")
        self.assertIn("no matches", out)

    def test_odd_query_characters_do_not_crash(self):
        self.m(self.a, "add", "note", "path src/api/export.py matters")
        code, out = self.m(self.a, "search", 'src/api/export.py "AND" (NEAR) *')
        self.assertEqual(code, 0, out)
        self.assertIn("P1 note", out)


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        self.ins = ROOT / "install.py"

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_all_is_idempotent_and_preserves_user_content(self):
        (self.p / "AGENTS.md").write_text("# Mine\nkeep this\n")
        (self.p / ".claude/agents").mkdir(parents=True)
        (self.p / ".claude/agents/mine.md").write_text("mine")
        for _ in range(2):
            code, out = run(self.ins, "--target", str(self.p))
            self.assertEqual(code, 0, out)
        agents_md = (self.p / "AGENTS.md").read_text()
        self.assertIn("keep this", agents_md)
        self.assertEqual(agents_md.count("simpleIDE:start"), 1)
        self.assertIn(".simpleide/sx.py", agents_md)
        self.assertIn("mem search", agents_md)
        self.assertNotIn("{MEM}", agents_md)
        self.assertLess(len(agents_md), 12000)  # Antigravity rule size cap
        self.assertIn("@AGENTS.md", (self.p / "CLAUDE.md").read_text())
        self.assertEqual((self.p / ".claude/agents/mine.md").read_text(), "mine")
        for rel in (".claude/skills/simpleide/SKILL.md", ".agents/skills/sx-writeup/SKILL.md",
                    ".agents/skills/simpleide/references/brief-template.md",
                    ".claude/agents/sx-worker.md", ".cursor/agents/sx-reviewer.md",
                    ".codex/agents/sx-planner.toml", ".agents/agents/sx-scout.md", ".simpleide/sx.py", ".simpleide/mem.py"):
            self.assertTrue((self.p / rel).exists(), rel)
        self.assertFalse((self.p / ".cursor/skills/simpleide").exists())
        self.assertFalse((self.p / ".claude/agents/sx-scout.md").exists())
        self.assertIn("mainAgent: false", (self.p / ".agents/agents/sx-worker.md").read_text())
        self.assertNotIn("tools:", (self.p / ".agents/agents/sx-worker.md").read_text())
        self.assertIn("model: opus", (self.p / ".claude/agents/sx-planner.md").read_text())
        self.assertIn("readonly: true", (self.p / ".cursor/agents/sx-reviewer.md").read_text())
        self.assertNotIn("readonly", (self.p / ".cursor/agents/sx-worker.md").read_text())
        code, out = run(self.p / ".simpleide/mem.py", "stats", cwd=self.p,
                        env={"SIMPLEIDE_HOME": str(self.p / "h")})
        self.assertEqual(code, 0, out)

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_codex_toml_parses(self):
        run(self.ins, "--target", str(self.p), "--tools", "codex")
        for f in (self.p / ".codex/agents").glob("*.toml"):
            d = tomllib.loads(f.read_text())
            self.assertTrue(d["name"].startswith("sx-"))
            self.assertTrue(d["developer_instructions"].strip())
        d = tomllib.loads((self.p / ".codex/agents/sx-reviewer.toml").read_text())
        self.assertNotIn("sandbox_mode", d)
        self.assertFalse((self.p / ".claude").exists())

    def test_uninstall_removes_only_ours(self):
        (self.p / "AGENTS.md").write_text("# Mine\n")
        run(self.ins, "--target", str(self.p))
        (self.p / ".simpleide/project.db").write_text("db")
        run(self.ins, "--target", str(self.p), "--uninstall")
        self.assertEqual((self.p / "AGENTS.md").read_text().strip(), "# Mine")
        self.assertFalse((self.p / "CLAUDE.md").exists())
        self.assertFalse((self.p / ".claude/agents/sx-worker.md").exists())
        self.assertFalse((self.p / ".agents/skills/simpleide/SKILL.md").exists())
        self.assertTrue((self.p / ".simpleide/project.db").exists())

    def test_dry_run_writes_nothing(self):
        code, out = run(self.ins, "--target", str(self.p), "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(list(self.p.iterdir()), [])

    def test_custom_models(self):
        mfile = self.p / "m.json"
        mfile.write_text(json.dumps({"claude": {"worker": {"model": "haiku"}}}))
        proj = self.p / "proj"
        proj.mkdir()
        run(self.ins, "--target", str(proj), "--tools", "claude", "--models", str(mfile))
        self.assertIn("model: haiku", (proj / ".claude/agents/sx-worker.md").read_text())
        self.assertIn("model: inherit", (proj / ".claude/agents/sx-planner.md").read_text())


if __name__ == "__main__":
    unittest.main()
