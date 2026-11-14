import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SX = ROOT / 'core/sx.py'
INSTALL = ROOT / 'install.py'


def call(script, *args, cwd, data=None):
    env = dict(os.environ, SIMPLEIDE_PROJECT=str(cwd), SIMPLEIDE_HOME=str(cwd / 'shared'), HOME=str(cwd / 'isolated-home'),
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', SIMPLEIDE_STORE='')
    return subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=env,
                          text=True, input=json.dumps(data) if data is not None else None,
                          capture_output=True)


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / '.simpleide').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def sx(self, *args, data=None):
        return call(SX, *args, cwd=self.root, data=data)

    def test_check_proposal_and_failing_artifact(self):
        (self.root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\n')
        proposed = self.sx('check', 'test', '--task', 't')
        self.assertEqual(proposed.returncode, 2)
        cfg = json.loads((self.root / '.simpleide/config.json').read_text())
        self.assertFalse(cfg['confirmed'])
        cfg = {'confirmed': True, 'checks': {'test': f'{sys.executable} -c "raise SystemExit(1)"'}}
        (self.root / '.simpleide/config.json').write_text(json.dumps(cfg))
        run = self.sx('check', 'test', '--task', 't')
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertLessEqual(len(run.stdout.splitlines()), 15)
        self.assertEqual(len(list((self.root / '.simpleide/artifacts/t').glob('test-*.txt'))), 1)
        con = sqlite3.connect(self.root / '.simpleide/project.db')
        self.assertEqual(con.execute("SELECT kind FROM rec WHERE kind='test'").fetchone()[0], 'test')
        unsafe = self.sx('check', 'test', '--task', '../outside')
        self.assertNotEqual(unsafe.returncode, 0)

    def test_scope_and_pack_handle_many_files(self):
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@x', 'commit', '-q', '--allow-empty', '-m', 'base'], cwd=self.root, check=True)
        for i in range(30):
            (self.root / f'f{i}.txt').write_text('x')
        self.sx('mem', 'add', 'request', 'original', '--task', 'task')
        self.sx('mem', 'add', 'criteria', 'works', '--task', 'task')
        scope = self.sx('scope', '--base', 'HEAD', '--allow', 'f*.txt', '--allow', '.simpleide/**')
        self.assertEqual(scope.returncode, 0, scope.stderr)
        pack = self.sx('pack', '--task', 'task', '--base', 'HEAD')
        self.assertEqual(pack.returncode, 0, pack.stderr)
        self.assertLessEqual(len(pack.stdout.splitlines()), 25)
        self.assertIn('REQUEST', pack.stdout)

    def test_scope_without_git_fails(self):
        out = self.sx('scope', '--base', 'HEAD', '--allow', '**')
        self.assertNotEqual(out.returncode, 0)

    def test_hook_capture_and_cursor_brief_guard(self):
        capture = self.sx('hook', 'capture-request', data={'prompt': 'Original wording', 'session_id': 's'})
        self.assertEqual(capture.returncode, 0)
        self.sx('mem', 'add', 'goal', 'Do it', '--task', 't', '--size', 'MEDIUM', '--request', 'P1')
        pack = sqlite3.connect(self.root / '.simpleide/project.db')
        self.assertEqual(pack.execute("SELECT task FROM rec WHERE kind='request'").fetchone()[0], 't')
        bad = self.sx('hook', 'dispatch-guard', data={'subagent_type': 'sx-worker', 'task': 'GOAL: do it'})
        self.assertEqual(json.loads(bad.stdout)['permission'], 'deny')
        good = self.sx('hook', 'dispatch-guard', data={'subagent_type': 'sx-worker', 'task': 'GOAL: do it\nDONE WHEN: complete'})
        self.assertEqual(json.loads(good.stdout)['permission'], 'allow')
        blocked = self.sx('hook', 'shell-guard', data={'command': 'git reset --hard HEAD', 'subagent_type': 'sx-worker'})
        self.assertEqual(json.loads(blocked.stdout)['permission'], 'deny')

    def test_lesson_use_and_prune(self):
        self.sx('mem', 'lesson', 'Old quirk', '--local')
        con = sqlite3.connect(self.root / '.simpleide/project.db')
        con.execute("UPDATE rec SET ts='2020-01-01 00:00' WHERE kind='lesson'")
        con.commit()
        self.assertIn('Old quirk', self.sx('mem', 'prune').stdout)
        self.sx('mem', 'show', 'P1')
        self.assertEqual(con.execute("SELECT uses FROM rec WHERE id=1").fetchone()[0], 0)
        self.sx('mem', 'search', 'quirk', '--host', 'codex', '--session', 'lesson-trial')
        self.sx('mem', 'show', 'P1', '--host', 'codex', '--session', 'lesson-trial')
        self.assertEqual(con.execute("SELECT uses FROM rec WHERE id=1").fetchone()[0], 1)
        self.assertNotIn('Old quirk', self.sx('mem', 'prune').stdout)

    def test_install_hooks_merges_and_uninstalls(self):
        (self.root / '.cursor').mkdir()
        original = {'version': 1, 'hooks': {'stop': [{'command': 'python own.py'}]}}
        original_text = '{"version":1,"hooks":{"stop":[{ "command" : "python own.py" }]}}\n'
        (self.root / '.cursor/hooks.json').write_text(original_text)
        out = call(INSTALL, '--target', str(self.root), '--tools', 'cursor', '--hooks', cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        merged = json.loads((self.root / '.cursor/hooks.json').read_text())
        self.assertIn(original['hooks']['stop'][0], merged['hooks']['stop'])
        self.assertIn('{ "command" : "python own.py" }', (self.root / '.cursor/hooks.json').read_text())
        self.assertTrue(any(' hook stop-check --host cursor' in x['command'] for x in merged['hooks']['stop']))
        call(INSTALL, '--target', str(self.root), '--tools', 'cursor', '--uninstall', cwd=self.root)
        restored = json.loads((self.root / '.cursor/hooks.json').read_text())
        self.assertEqual(restored['hooks']['stop'], original['hooks']['stop'])
        self.assertIn('{ "command" : "python own.py" }', (self.root / '.cursor/hooks.json').read_text())
        self.assertFalse((self.root / '.simpleide/hook-created-cursor.json').exists())

    def test_codex_pretool_brief_can_be_denied(self):
        data = {'hook_event_name': 'PreToolUse', 'tool_name': 'spawn_agent',
                'tool_input': {'agent_type': 'sx-worker', 'message': 'GOAL: do it'}}
        out = self.sx('hook', 'dispatch-guard', '--host', 'codex', data=data)
        self.assertEqual(out.returncode, 0, out.stderr)
        decision = json.loads(out.stdout)['hookSpecificOutput']
        self.assertEqual(decision['hookEventName'], 'PreToolUse')
        self.assertEqual(decision['permissionDecision'], 'deny')

    def test_claude_and_cursor_hook_shapes(self):
        bad = self.sx('hook', 'dispatch-guard', '--host', 'claude', data={
            'hook_event_name': 'PreToolUse', 'tool_name': 'Task',
            'tool_input': {'subagent_type': 'sx-worker', 'prompt': 'GOAL: work'}})
        self.assertEqual(json.loads(bad.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
        self.sx('mem', 'add', 'goal', 'Finish', '--task', 'task', '--size', 'LARGE')
        stopped = self.sx('hook', 'stop-check', '--host', 'codex', data={'hook_event_name': 'Stop', 'task_slug': 'task'})
        self.assertEqual(json.loads(stopped.stdout)['decision'], 'block')
        stopped_again = self.sx('hook', 'stop-check', '--host', 'codex', data={'hook_event_name': 'Stop', 'task_slug': 'task'})
        self.assertEqual(json.loads(stopped_again.stdout), {})
        resumed = self.sx('hook', 'resume', '--host', 'cursor', data={'conversation_id': 'c', 'task_slug': 'task'})
        self.assertIn('simpleIDE task', json.loads(resumed.stdout)['additional_context'])

    def test_worktree_refuses_uncommitted_and_merges_in_order(self):
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        subprocess.run(['git', 'config', 'user.name', 'T'], cwd=self.root, check=True)
        subprocess.run(['git', 'config', 'user.email', 't@x'], cwd=self.root, check=True)
        installed = call(INSTALL, '--target', str(self.root), '--tools', 'codex', cwd=self.root)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@x', 'commit', '-q', '-m', 'base'], cwd=self.root, check=True)
        self.sx('mem', 'add', 'goal', 'Split work', '--task', 'task')
        add = self.sx('worktree', 'add', 'task', 'one')
        self.assertEqual(add.returncode, 0, add.stderr)
        tree = Path(add.stdout.strip())
        (tree / 'file.txt').write_text('changed')
        blocked = self.sx('worktree', 'clean', 'task')
        self.assertNotEqual(blocked.returncode, 0)
        subprocess.run(['git', 'add', 'file.txt'], cwd=tree, check=True)
        subprocess.run(['git', '-c', 'user.name=T', '-c', 'user.email=t@x', 'commit', '-q', '-m', 'one'], cwd=tree, check=True)
        merge = self.sx('worktree', 'merge', 'task')
        self.assertEqual(merge.returncode, 0, merge.stderr)
        self.assertEqual((self.root / 'file.txt').read_text(), 'changed')
        clean = self.sx('worktree', 'clean', 'task')
        self.assertEqual(clean.returncode, 0, clean.stderr)

    def test_doctor_reports_missing_then_installed(self):
        missing = self.sx('doctor')
        self.assertNotEqual(missing.returncode, 0)
        installed = call(INSTALL, '--target', str(self.root), cwd=self.root)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        good = self.sx('doctor')
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        self.assertIn('Files configured/present only.', good.stdout)


if __name__ == '__main__':
    unittest.main()
