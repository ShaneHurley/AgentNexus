"""Repair contracts: disposable homes, stores and Git repositories only."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

KIT = Path(os.environ.get('SIMPLEIDE_TEST_KIT', Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location('repair_sx', KIT / 'core/sx.py')
sx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sx)

class Repairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sx-repair-')
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'project with spaces'
        self.root.mkdir()
        self.env = dict(os.environ, HOME=str(self.base / 'home'), SIMPLEIDE_PROJECT=str(self.root),
                        SIMPLEIDE_HOME=str(self.base / 'shared'), GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull)
        self.env.pop('SIMPLEIDE_STORE', None)
        self.env.pop('SIMPLEIDE_TASK', None)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, root=None, payload=None, install=False, installed=False, env=None):
        root = root or self.root
        e = dict(self.env, SIMPLEIDE_PROJECT=str(root))
        e.update(env or {})
        script = KIT / ('install.py' if install else 'core/sx.py')
        if installed:
            script = root / '.simpleide/sx.py'
        return subprocess.run([sys.executable, str(script), *args], cwd=root, env=e,
                              input=json.dumps(payload) if payload is not None else None,
                              text=True, capture_output=True, timeout=30)

    def ok(self, *args, **kw):
        r = self.cli(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def db(self):
        return sqlite3.connect(self.root / '.simpleide/project.db')

    def git(self, *args, root=None):
        r = subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args],
                           cwd=root or self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def repository(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / '.gitignore').write_text('.simpleide/\n')
        (self.root / 'source.txt').write_text('original\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')

    def test_ids_never_reused_and_strict_ids(self):
        self.ok('mem', 'add', 'note', 'keep')
        self.ok('mem', 'add', 'note', 'deleted')
        self.ok('mem', 'forget', 'P2')
        self.assertIn('P3', self.ok('mem', 'add', 'note', 'replacement'))
        self.assertIn('not found', self.ok('mem', 'show', 'P2'))
        for bad in ('2', 'PP1', 'P-1', 'P1x'):
            self.assertNotEqual(self.cli('mem', 'show', bad).returncode, 0)

    def legacy(self):
        path = self.root / '.simpleide/project.db'
        path.parent.mkdir()
        with sqlite3.connect(path) as c:
            c.executescript(sx.SCHEMA.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'INTEGER PRIMARY KEY'))
            c.execute("INSERT INTO rec(id,uid,ts,kind,title) VALUES(7,'legacy','2026-11-11','note','Legacy needle')")
        return path

    def test_migration_backup_fts_and_identity(self):
        path = self.legacy()
        self.assertIn('Legacy needle', self.ok('mem', 'search', 'needle', '--scope', 'project'))
        with self.db() as c:
            self.assertEqual(c.execute('SELECT id,uid FROM rec').fetchall(), [(7, 'legacy')])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            identity = c.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0]
        backups = list(path.parent.glob('project.db.pre-v*.bak'))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as c:
            self.assertEqual(c.execute('SELECT id,uid FROM rec').fetchall(), [(7, 'legacy')])
        self.ok('mem', 'stats')
        with self.db() as c:
            self.assertEqual(c.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0], identity)

    def test_migration_failure_rolls_back(self):
        path = self.legacy()
        original = sx.FTS
        with patch.object(sx, 'FTS', original + '\nINVALID MIGRATION SQL;'):
            with self.assertRaises(sqlite3.Error):
                sx.connect(path)
        with sqlite3.connect(path) as c:
            self.assertEqual(c.execute('SELECT id,uid FROM rec').fetchall(), [(7, 'legacy')])
            self.assertNotIn('AUTOINCREMENT', c.execute("SELECT sql FROM sqlite_master WHERE name='rec'").fetchone()[0])
        sx.connect(path).close()

    def test_concurrent_first_open_and_duplicate(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.cli('mem', 'add', 'goal', 'same', '--task', 'same'), range(12)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        with self.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rec').fetchone()[0], 1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM run').fetchone()[0], 1)

    def capture(self, session):
        self.ok('hook', 'capture-request', '--host', 'codex', payload={'session_id': session, 'prompt': 'Verbatim\n' + session})
        with self.db() as c:
            return 'P' + str(c.execute('SELECT MAX(id) FROM rec').fetchone()[0])

    def test_explicit_binding_isolates_sessions_and_all_criteria(self):
        a, b = self.capture('a'), self.capture('b')
        self.ok('mem', 'add', 'goal', 'A goal', '--task', 'a', '--request', a)
        self.ok('mem', 'add', 'goal', 'B goal', '--task', 'b', '--request', b)
        self.ok('mem', 'add', 'goal', 'Unbound', '--task', 'unbound')
        for i in range(5):
            self.ok('mem', 'add', 'criteria', 'Criterion ' + str(i), '--body', 'Full body ' + str(i), '--task', 'a')
        out = self.ok('hook', 'resume', '--host', 'codex', payload={'session_id': 'a'})
        self.assertIn('task: a', out)
        self.assertIn('criteria: 5', out)
        self.assertIn('mem export', out)
        self.assertLessEqual(len(out.splitlines()), 5)
        self.assertNotIn('task: b', self.ok('hook', 'resume', '--host', 'codex', payload={'session_id': 'new'}))
        with self.db() as c:
            self.assertEqual(c.execute("SELECT task FROM rec WHERE id=2").fetchone()[0], 'b')
        wrong = self.cli('task', 'bind', 'a', '--request', 'P3')
        self.assertNotEqual(wrong.returncode, 0)

    def test_correlated_intent_and_unknown_lifecycle(self):
        self.ok('mem', 'add', 'goal', 'A', '--task', 'a')
        for call in ('one', 'two'):
            self.ok('hook', 'dispatch-guard', '--host', 'codex', payload={
                'session_id': 's', 'tool_call_id': call, 'hook_event_name': 'PreToolUse',
                'tool_input': {'agent_type': 'sx-worker', 'model': 'requested',
                               'message': 'TASK: a\nGOAL: work\nDONE WHEN: checked'}})
        self.ok('hook', 'dispatch-guard', '--host', 'codex', payload={
            'session_id': 's', 'tool_call_id': 'two', 'agent_id': 'child2',
            'agent_type': 'sx-worker', 'hook_event_name': 'SubagentStart', 'model': 'observed'})
        self.ok('hook', 'dispatch-guard', '--host', 'codex', payload={
            'session_id': 's', 'agent_id': 'unknown', 'agent_type': 'sx-worker', 'hook_event_name': 'SubagentStart'})
        with self.db() as c:
            self.assertEqual(c.execute("SELECT task,requested_model,model,state FROM dispatch WHERE child_id='child2'").fetchone(),
                             ('a', 'requested', 'observed', 'started'))
            self.assertEqual(c.execute("SELECT task,requested_model FROM dispatch WHERE child_id='unknown'").fetchone(), ('', ''))

    def test_empty_section_contents_rejected(self):
        for brief in ('GOAL:\nDONE WHEN:', 'GOAL\nDONE WHEN\nChecked', 'GOAL: Work\nCONTEXT: x\nDONE WHEN:   '):
            out = self.ok('hook', 'dispatch-guard', '--host', 'cursor', payload={'subagent_type': 'sx-worker', 'task': brief})
            self.assertEqual(json.loads(out)['permission'], 'deny')

    def test_pending_admission_limit_is_atomic(self):
        self.ok('mem', 'add', 'goal', 'A', '--task', 'a')
        def launch(i):
            return self.ok('hook', 'dispatch-guard', '--host', 'codex', payload={
                'session_id': 's', 'tool_call_id': str(i), 'hook_event_name': 'PreToolUse',
                'tool_input': {'agent_type': 'sx-worker', 'message': 'TASK: a\nGOAL: work\nDONE WHEN: checked'}})
        with ThreadPoolExecutor(max_workers=6) as pool:
            replies = list(pool.map(launch, range(6)))
        self.assertEqual(sum('permissionDecision' in r for r in replies), 3)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM dispatch WHERE state='pending'").fetchone()[0], 3)

    def checks(self, checks):
        path = self.root / '.simpleide/config.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'confirmed': True, 'checks': checks}))

    def test_outcomes_are_explicit_immutable_and_filtered(self):
        self.ok('mem', 'add', 'goal', 'Failed task', '--task', 'bad')
        result = self.ok('mem', 'add', 'result', 'Blocked; failed', '--task', 'bad').split()[0]
        self.assertIn('accepted=0', self.ok('stats', '--task', 'bad'))
        self.ok('task', 'close', 'bad', '--outcome', 'failed', '--result', result, '--by', 'assistant', '--refs', 'observed failure')
        self.ok('task', 'close', 'bad', '--outcome', 'failed', '--result', result, '--by', 'assistant', '--refs', 'observed failure')
        self.assertNotEqual(self.cli('mem', 'add', 'goal', 'retry', '--task', 'bad').returncode, 0)
        self.ok('mem', 'add', 'goal', 'Retry', '--task', 'good', '--retry-of', 'bad')
        self.assertNotEqual(self.cli('task', 'close', 'good', '--outcome', 'accepted', '--result', result, '--by', 'user', '--refs', 'decision').returncode, 0)
        r2 = self.ok('mem', 'add', 'result', 'Document delivered', '--task', 'good').split()[0]
        self.ok('task', 'close', 'good', '--outcome', 'accepted', '--result', r2, '--by', 'assistant', '--refs', 'document evidence')
        out = self.ok('stats', '--task', 'good', '--tokens', '42', '--cost', '0.1', '--usage-source', 'manual observation')
        self.assertIn('tasks=1', out)
        self.assertIn('assistant=1', out)
        self.assertIn('user=0', out)
        for flag, value in (('--tokens', '-1'), ('--cost', 'nan'), ('--cost', 'inf')):
            self.assertNotEqual(self.cli('stats', '--task', 'good', flag, value).returncode, 0)

    def test_checks_keep_failures_currentness_and_close_gate(self):
        self.repository()
        self.ok('mem', 'add', 'goal', 'Check all', '--task', 't', '--size', 'MEDIUM')
        self.checks({'test': 'exit 1', 'lint': 'echo passed'})
        self.assertEqual(self.cli('check', '--task', 't').returncode, 1)
        result = self.ok('mem', 'add', 'result', 'Written', '--task', 't').split()[0]
        stop = self.ok('hook', 'stop-check', '--host', 'codex', payload={'task_slug': 't'})
        self.assertIn('failed', stop)
        close = ('task', 'close', 't', '--outcome', 'accepted', '--result', result, '--by', 'assistant', '--refs', 'evidence')
        self.assertNotEqual(self.cli(*close).returncode, 0)
        self.checks({'test': 'echo passed', 'lint': 'echo passed'})
        self.ok('check', '--task', 't')
        self.assertIn('PASS', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        (self.root / 'source.txt').write_text('edited\n')
        self.assertIn('stale', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertNotEqual(self.cli(*close).returncode, 0)
        self.ok('check', '--task', 't')
        self.checks({'test': 'echo passed', 'lint': 'echo changed command'})
        self.assertIn('stale', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertNotEqual(self.cli(*close).returncode, 0)
        self.ok('check', '--task', 't')
        self.ok(*close)

    def test_raw_git_paths_and_concurrent_check_logs(self):
        self.repository()
        self.git('config', 'core.quotePath', 'true')
        (self.root / 'allowed').mkdir()
        for name in ('café.py', 'tab\tname', 'new\nline'):
            (self.root / 'allowed' / name).write_text('x')
        self.ok('scope', '--base', 'HEAD', '--allow', 'allowed/**')
        self.ok('mem', 'add', 'goal', 'Checks', '--task', 't')
        self.checks({'test': 'echo concurrent'})
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.cli('check', '--task', 't'), range(6)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        with self.db() as c:
            artifacts = [r[0] for r in c.execute('SELECT artifact FROM check_obs')]
        self.assertEqual(len(set(artifacts)), 6)
        self.assertTrue(all(Path(a).read_text().strip() == 'concurrent' for a in artifacts))

    def installed_repository(self):
        self.repository()
        (self.root / '.gitignore').write_text('')
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        self.git('add', '.')
        self.git('commit', '-qm', 'installed runtime')
        self.ok('mem', 'add', 'goal', 'Split work', '--task', 't')
        self.ok('mem', 'add', 'criteria', 'Original criterion', '--body', 'complete criterion body', '--task', 't')

    def test_worktree_context_executes_worker_and_preserves_evidence(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        self.assertIn('Original criterion', self.ok('mem', 'recent', '--task', 't', root=worker, installed=True))
        (worker / 'worker-only').write_text('yes')
        (worker / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {'test': 'test -f worker-only'}}))
        self.ok('check', '--task', 't', root=worker, installed=True)
        with self.db() as c:
            artifact, execution = c.execute('SELECT artifact,execution_root FROM check_obs').fetchone()
        self.assertEqual(execution, str(worker))
        self.assertTrue(Path(artifact).is_relative_to(self.root))
        self.assertTrue(list((self.root / '.simpleide/artifacts/t').glob('request-*.md')))
        (worker / '.simpleide/config.json').unlink()
        self.git('add', 'worker-only', root=worker)
        self.git('commit', '-qm', 'worker', root=worker)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.ok('worktree', 'merge', 't')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.ok('worktree', 'clean', 't')
        self.ok('worktree', 'clean', 't')
        self.assertTrue(Path(artifact).exists())
        self.assertIn('test: PASS', self.ok('mem', 'recent', '--task', 't'))

    def test_cleanup_preflights_all_and_rejects_bad_store(self):
        self.installed_repository()
        one = Path(self.ok('worktree', 'add', 't', 'one').strip())
        two = Path(self.ok('worktree', 'add', 't', 'two').strip())
        (two / 'dirty').write_text('dirty')
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(one.exists())
        (two / 'dirty').unlink()
        context = two / '.simpleide/context.json'
        data = json.loads(context.read_text())
        data['store_id'] = 'wrong'
        context.write_text(json.dumps(data))
        self.assertNotEqual(self.cli('mem', 'recent', root=two, installed=True).returncode, 0)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(one.exists())
        data['store_id'] = json.loads((one / '.simpleide/context.json').read_text())['store_id']
        context.write_text(json.dumps(data))
        self.ok('worktree', 'clean', 't')

    def test_concurrent_worktree_add_and_missing_runtime(self):
        self.repository()
        self.ok('mem', 'add', 'goal', 'Task', '--task', 't')
        missing = self.cli('worktree', 'add', 't', 'missing')
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('commit local simpleIDE runtime', missing.stderr)
        self.installed_runtime_for_existing_repo()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda p: self.cli('worktree', 'add', 't', p), ('one', 'two')))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        with self.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM worktree WHERE state='added'").fetchone()[0], 2)
        self.ok('worktree', 'clean', 't')

    def installed_runtime_for_existing_repo(self):
        (self.root / '.gitignore').write_text('')
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        self.git('add', '.')
        self.git('commit', '-qm', 'runtime')
        self.ok('mem', 'add', 'goal', 'Task', '--task', 't')

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_installer_preflight_and_exact_hook_ownership(self):
        path = self.root / '.cursor/hooks.json'
        path.parent.mkdir()
        path.write_text('{ invalid json')
        before = self.snapshot()
        self.assertNotEqual(self.cli('--target', str(self.root), '--tools', 'cursor', '--hooks', install=True).returncode, 0)
        self.assertEqual(before, self.snapshot())
        path.write_text('{"version":1,"hooks":{"stop":[{ "command" : "echo documented .simpleide/sx.py hook syntax" }]}}')
        self.ok('--target', str(self.root), '--tools', 'cursor,codex', '--hooks', install=True)
        self.assertIn('{ "command" : "echo documented .simpleide/sx.py hook syntax" }', path.read_text())
        self.ok('--target', str(self.root), '--tools', 'cursor', '--uninstall', install=True)
        self.assertTrue((self.root / '.agents/skills/simpleide/SKILL.md').exists())
        self.assertTrue((self.root / '.agents/skills/sx-writeup/SKILL.md').exists())
        self.assertIn('simpleIDE:start', (self.root / 'AGENTS.md').read_text())
        self.assertTrue((self.root / '.codex/agents/sx-worker.toml').exists())
        self.ok('--target', str(self.root), '--tools', 'cursor', install=True)
        # Updating without --hooks retains previously enabled Codex hooks.
        self.assertIn('sx.py', (self.root / '.codex/hooks.json').read_text())

    def test_installer_validation_dry_run_rollback_and_doctor(self):
        self.ok('--target', str(self.root), '--tools', 'codex', '--hooks', install=True)
        before = self.snapshot()
        self.ok('--target', str(self.root), '--tools', 'cursor', '--dry-run', install=True)
        self.assertEqual(before, self.snapshot())
        for tools in ('', 'bogus'):
            self.assertNotEqual(self.cli('--target', str(self.root), '--tools', tools, install=True).returncode, 0)
            self.assertEqual(before, self.snapshot())
        spec = importlib.util.spec_from_file_location('repair_installer', KIT / 'install.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        replace = os.replace
        count = 0
        def fail_once(src, dst):
            nonlocal count
            count += 1
            if count == 3: raise OSError('injected apply failure')
            return replace(src, dst)
        with patch.object(module.os, 'replace', side_effect=fail_once), patch.dict(os.environ, self.env):
            self.assertNotEqual(module.main(['--target', str(self.root), '--tools', 'cursor']), 0)
        self.assertEqual(before, self.snapshot())
        self.ok('doctor', installed=True)
        agent = self.root / '.codex/agents/sx-worker.toml'
        agent.unlink()
        self.assertNotEqual(self.cli('doctor', installed=True).returncode, 0)
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        self.ok('doctor', installed=True)
        (self.root / '.agents/skills/simpleide/SKILL.md').unlink()
        self.assertNotEqual(self.cli('doctor', installed=True).returncode, 0)

    def test_global_and_local_rendered_commands_from_subdirectory(self):
        self.ok('--global', '--tools', 'codex', install=True)
        home = Path(self.env['HOME'])
        global_skill = (home / '.agents/skills/sx-writeup/SKILL.md').read_text()
        command = global_skill.split('Run `', 1)[1].split('`', 1)[0].replace('<slug>', 'trial')
        r = subprocess.run(command, shell=True, cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        subdir = self.root / 'nested'; subdir.mkdir()
        local_skill = (self.root / '.agents/skills/sx-writeup/SKILL.md').read_text()
        command = local_skill.split('Run `', 1)[1].split('`', 1)[0].replace('<slug>', 'local')
        r = subprocess.run(command, shell=True, cwd=subdir, env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_sharing_promotion_same_basename_and_total_limit(self):
        a, b = self.base / 'a/same', self.base / 'b/same'
        a.mkdir(parents=True); b.mkdir(parents=True)
        self.ok('mem', 'lesson', 'Reusable needle', '--local', root=a)
        self.assertIn('no matches', self.ok('mem', 'search', 'needle', root=b))
        self.ok('mem', 'lesson', 'Reusable needle', root=a)
        self.assertIn('Reusable needle', self.ok('mem', 'search', 'needle', root=b))
        self.assertEqual(self.ok('mem', 'search', 'needle', root=a).count('Reusable needle'), 1)
        self.ok('mem', 'lesson', 'Another needle', root=b)
        out = self.ok('mem', 'search', 'needle', '--limit', '1', root=b)
        self.assertEqual(sum(line.startswith(('P', 'S')) for line in out.splitlines()), 1)

    def test_search_attribution_requires_actual_hit_and_matching_session(self):
        self.ok('mem', 'lesson', 'Target lesson', '--local')
        note = self.ok('mem', 'add', 'note', 'Unrelated').split()[0]
        self.ok('mem', 'search', 'target', '--host', 'codex', '--session', 'a')
        self.ok('mem', 'show', note, '--host', 'codex', '--session', 'a')
        self.ok('mem', 'show', 'P1', '--host', 'codex', '--session', 'b')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT SUM(opened) FROM search_log').fetchone()[0], 0)
        self.ok('mem', 'show', 'P1', '--host', 'codex', '--session', 'a')
        self.ok('mem', 'show', 'P1', '--host', 'codex', '--session', 'a')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT uses FROM rec WHERE id=1').fetchone()[0], 1)
        self.ok('mem', 'search', 'target', '--host', 'codex', '--session', 'a')
        self.ok('mem', 'show', 'P1', '--host', 'codex', '--session', 'a')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT uses FROM rec WHERE id=1').fetchone()[0], 1)
        self.ok('mem', 'show', 'P1', '--host', 'codex', '--session', 'a', '--search-id', '2')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT uses FROM rec WHERE id=1').fetchone()[0], 2)
        self.ok('mem', 'search', 'target')
        self.ok('mem', 'show', 'P1')
        self.ok('mem', 'show', 'P1', '--search-id', '0')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT uses FROM rec WHERE id=1').fetchone()[0], 2)
        self.ok('mem', 'show', 'P1', '--search-id', '3')
        with self.db() as c:
            self.assertEqual(c.execute('SELECT uses FROM rec WHERE id=1').fetchone()[0], 3)

    def test_question_resolution_and_export_provenance(self):
        request = self.capture('s')
        self.ok('mem', 'add', 'goal', 'Task', '--task', 't', '--request', request)
        question = self.ok('mem', 'add', 'question', 'Delimiter?', '--task', 't').split()[0]
        decision = self.ok('mem', 'add', 'decision', 'Comma', '--task', 't', '--refs', question).split()[0]
        self.assertIn('open questions: 1', self.ok('hook', 'resume', '--host', 'codex', payload={'session_id':'s'}))
        self.ok('mem', 'add', 'decision', 'Foreign', '--task', 'other')
        self.assertNotEqual(self.cli('mem', 'resolve', question, '--decision', 'P5').returncode, 0)
        self.ok('mem', 'resolve', question, '--decision', decision)
        self.assertIn('open questions: 0', self.ok('hook', 'resume', '--host', 'codex', payload={'session_id':'s'}))
        result = self.ok('mem', 'add', 'result', 'Done', '--task', 't').split()[0]
        self.ok('task', 'close', 't', '--outcome', 'accepted', '--result', result, '--by', 'assistant', '--refs', 'artifact')
        export = self.ok('mem', 'export', '--task', 't')
        for expected in ('Store:', 'Primary request: P1', 'explicit', 'assistant', 'resolved by ' + decision, 'Verbatim\ns'):
            self.assertIn(expected, export)

    def test_legacy_outcome_and_shared_store_migration(self):
        path = self.legacy()
        with sqlite3.connect(path) as c:
            c.execute("INSERT INTO run(task,outcome,end) VALUES('old','accepted',CURRENT_TIMESTAMP)")
        out = self.ok('stats')
        self.assertIn('accepted=0', out)
        self.assertIn('legacy-unverified=1', out)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT outcome,provenance FROM run").fetchone(), ('accepted','legacy-unverified'))
        shared = self.base / 'shared/shared.db'; shared.parent.mkdir()
        with sqlite3.connect(shared) as c:
            c.executescript(sx.SCHEMA.replace('INTEGER PRIMARY KEY AUTOINCREMENT','INTEGER PRIMARY KEY'))
            c.execute("INSERT INTO rec(id,uid,ts,kind,title) VALUES(9,'oldlesson','2026-11-11','lesson','Old shared')")
        self.assertIn('S9 lesson', self.ok('mem', 'search', 'old', '--scope', 'shared'))
        self.ok('mem', 'forget', 'S9')
        self.ok('mem', 'lesson', 'New lesson')
        self.assertIn('S10 lesson', self.ok('mem', 'search', 'new', '--scope', 'shared'))
        self.assertTrue(list(shared.parent.glob('shared.db.pre-v*.bak')))

    def test_interrupted_check_retains_output_and_unknown_freshness_requires_exception(self):
        self.ok('mem', 'add', 'goal', 'Task', '--task', 't')
        self.checks({'test': 'echo check'})
        real_run = subprocess.run
        def interrupted(*args, **kw):
            if kw.get('shell'):
                kw['stdout'].write('partial output\n')
                raise KeyboardInterrupt()
            return real_run(*args, **kw)
        with patch.dict(os.environ,self.env), patch.object(sx.subprocess,'run',side_effect=interrupted):
            self.assertEqual(sx.check_cmd(self.root, 'test', 't'), 1)
        with self.db() as c:
            artifact, code = c.execute('SELECT artifact,exit_code FROM check_obs').fetchone()
        self.assertEqual(code, -2)
        self.assertIn('partial output', Path(artifact).read_text())
        self.ok('check', '--task', 't')
        result = self.ok('mem', 'add', 'result', 'Evidence', '--task', 't').split()[0]
        close = ('task','close','t','--outcome','accepted','--result',result,'--by','assistant','--refs','observed artifact')
        self.assertNotEqual(self.cli(*close).returncode, 0)
        decision = self.ok('mem','add','decision','Accept non-code evidence with unknown revision freshness','--task','t').split()[0]
        self.ok(*close, '--exception', decision)
        self.assertIn('exception=' + decision, self.ok('mem', 'export', '--task', 't'))

    def test_worktree_legacy_archive_and_interrupted_clean_recovery(self):
        self.installed_repository()
        one = Path(self.ok('worktree','add','t','one').strip())
        two = Path(self.ok('worktree','add','t','two').strip())
        context = one / '.simpleide/context.json'
        context.unlink()
        self.ok('context', 'standalone', root=one, installed=True)
        self.ok('mem','add','finding','Independent legacy evidence','--task','t',root=one,installed=True)
        artifacts = one / '.simpleide/artifacts'; artifacts.mkdir(exist_ok=True)
        (artifacts/'ignored.txt').write_text('durable ignored evidence')
        with patch.dict(os.environ,self.env):
            c=sx.ledger(self.root)
            entry=c.execute("SELECT * FROM worktree WHERE piece='one'").fetchone()
            archive=sx.archive_worker(c,self.root,entry)
        manifest=json.loads(Path(archive).read_text())
        self.git('worktree','remove',str(one))
        with self.db() as c:
            c.execute("UPDATE worktree SET state='removing',diagnostic=? WHERE piece='one'",(archive,))
        self.ok('worktree','clean','t')
        self.assertFalse(two.exists())
        with sqlite3.connect(manifest['database']) as c:
            self.assertEqual(c.execute('SELECT title FROM rec').fetchone()[0], 'Independent legacy evidence')
        self.assertEqual((Path(archive).parent/'artifacts/ignored.txt').read_text(),'durable ignored evidence')
        self.ok('worktree','clean','t')

    def test_full_installed_workflow(self):
        self.repository()
        (self.root/'.gitignore').write_text('')
        self.ok('--target',str(self.root),'--tools','cursor,codex','--hooks',install=True)
        self.git('add','.'); self.git('commit','-qm','runtime')
        for session in ('a','b'):
            self.ok('hook','capture-request','--host','codex',payload={'session_id':session,'prompt':'Request '+session},installed=True)
        for task,request in (('a','P1'),('b','P2')):
            self.ok('mem','add','goal','Goal '+task,'--task',task,'--request',request,'--size','MEDIUM',installed=True)
            self.ok('mem','add','criteria','Deliver '+task,'--body','Retain full criteria','--task',task,installed=True)
        self.ok('hook','dispatch-guard','--host','codex',payload={'session_id':'a','tool_call_id':'call-a','hook_event_name':'PreToolUse',
                 'tool_input':{'agent_type':'sx-worker','message':'TASK: a\nGOAL: work\nDONE WHEN: checked'}},installed=True)
        self.ok('hook','dispatch-guard','--host','codex',payload={'session_id':'a','tool_call_id':'call-a','agent_id':'child-a','agent_type':'sx-worker','hook_event_name':'SubagentStart'},installed=True)
        self.ok('hook','return-log','--host','codex',payload={'session_id':'a','agent_id':'child-a','agent_type':'sx-worker','summary':'STATUS: done'},installed=True)
        worker=Path(self.ok('worktree','add','a','one',installed=True).strip())
        self.assertIn('Request a',self.ok('mem','export','--task','a',root=worker,installed=True))
        (worker/'delivered.txt').write_text('delivered')
        self.git('add','delivered.txt',root=worker); self.git('commit','-qm','delivery',root=worker)
        self.ok('worktree','merge','a',installed=True)
        self.checks({'test':'test -f delivered.txt','lint':'echo lint passed'})
        self.ok('check','--task','a',installed=True)
        result=self.ok('mem','add','result','Delivered and checked','--task','a',installed=True).split()[0]
        self.ok('task','close','a','--outcome','accepted','--result',result,'--by','assistant','--refs','fixture acceptance; no user decision',installed=True)
        self.ok('mem','export','--task','a','--out','.simpleide/artifacts/a/final.md',installed=True)
        self.ok('worktree','clean','a',installed=True)
        self.ok('--target',str(self.root),'--tools','cursor','--uninstall',install=True)
        self.ok('doctor',installed=True)
        self.ok('--target',str(self.root),'--tools','cursor',install=True)
        self.ok('doctor',installed=True)
        self.assertIn('task: b',self.ok('hook','resume','--host','codex',payload={'session_id':'b'},installed=True))

    def test_post_close_capture_does_not_reopen_old_task(self):
        request=self.capture('s')
        self.ok('mem','add','goal','First','--task','first','--request',request)
        result=self.ok('mem','add','result','Done','--task','first').split()[0]
        self.ok('task','close','first','--outcome','accepted','--result',result,'--by','assistant','--refs','document')
        next_request=self.capture('s')
        self.ok('mem','add','goal','Next','--task','next','--request',next_request)
        self.assertIn('task: next',self.ok('hook','resume','--host','codex',payload={'session_id':'s'}))
        with self.db() as c:
            self.assertEqual(c.execute("SELECT request_id FROM run WHERE task='first'").fetchone()[0],1)

    def test_legacy_install_bootstrap_and_edited_collision(self):
        directory=self.root/'.simpleide'; directory.mkdir()
        (directory/'.gitignore').write_text('project.db*\nartifacts/\nworktrees.json\nhook-created-*.json\n')
        self.ok('--target',str(self.root),'--tools','codex',install=True)
        user_file=self.root/'.agents/skills/simpleide/user-notes.txt'
        user_file.write_text('preserve user addition')
        self.ok('--target',str(self.root),'--tools','codex','--uninstall',install=True)
        self.assertEqual(user_file.read_text(),'preserve user addition')
        self.ok('--target',str(self.root),'--tools','codex',install=True)
        script=directory/'sx.py'; script.write_text(script.read_text()+'\n# edited user copy\n')
        before=self.snapshot()
        self.assertNotEqual(self.cli('--target',str(self.root),'--tools','codex',install=True).returncode,0)
        self.assertEqual(before,self.snapshot())

    def test_changed_during_check_and_conflicting_return_ids(self):
        self.repository()
        self.ok('mem','add','goal','Task','--task','t')
        self.checks({'test':'echo edited > source.txt'})
        self.ok('check','--task','t')
        self.assertIn('stale',self.ok('pack','--task','t','--base','HEAD'))
        for ident in ('one','two'):
            self.ok('hook','dispatch-guard','--host','cursor',payload={'task':'TASK: t\nGOAL: work\nDONE WHEN: checked',
                  'subagent_type':'sx-worker','subagent_id':ident,'tool_call_id':ident,'conversation_id':'s'})
        self.ok('hook','return-log','--host','cursor',payload={'subagent_type':'sx-worker','subagent_id':'one','tool_call_id':'two','conversation_id':'s','summary':'STATUS: done'})
        with self.db() as c:
            self.assertEqual(c.execute("SELECT return_status FROM dispatch").fetchall(),[('',),('',)])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM hook_observation WHERE event='unmatched-return'").fetchone()[0],1)

    def test_invalid_shapes_fail_before_mutation_without_tracebacks(self):
        models=self.root/'models.json'
        for data in ({}, {'codex':{}}, {'codex':{'worker':{'model':'bad\nmodel = broken'}}}):
            models.write_text(json.dumps(data))
            before=self.snapshot()
            result=self.cli('--target',str(self.root),'--tools','codex','--models',str(models),install=True)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(before,self.snapshot())
        directory=self.root/'.simpleide'; directory.mkdir()
        (directory/'config.json').write_text('[]')
        result=self.cli('check','--task','t')
        self.assertEqual(result.returncode,2)
        self.assertNotIn('Traceback',result.stderr)
        path=self.root/'.cursor/hooks.json'; path.parent.mkdir()
        path.write_text('{"version":1,"hooks":{"stop":{}}}')
        before=self.snapshot()
        result=self.cli('--target',str(self.root),'--tools','cursor','--hooks',install=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(before,self.snapshot())

    def test_pack_uses_selected_primary_request_and_repairs_partial_handoff(self):
        self.repository()
        first=self.capture('s')
        self.ok('mem','add','goal','Task','--task','t','--request',first)
        self.ok('hook','capture-request','--host','codex',payload={'session_id':'s','prompt':'Selected replacement request\nFull original body'})
        with self.db() as c:
            selected='P'+str(c.execute('SELECT MAX(id) FROM rec').fetchone()[0])
        self.ok('task','bind','t','--request',selected)
        packet=self.ok('pack','--task','t','--base','HEAD')
        self.assertIn('REQUEST  '+selected+' ',packet)
        artifacts=list((self.root/'.simpleide/artifacts/t').glob('request-*.md'))
        self.assertEqual(len(artifacts),1)
        text=artifacts[0].read_text()
        self.assertIn('Selected replacement request',text)
        self.assertNotIn('Verbatim',text)
        artifacts[0].write_text('interrupted partial write')
        self.ok('pack','--task','t','--base','HEAD')
        self.assertEqual(artifacts[0].read_text(),text)

    def submodule_repository(self):
        library = self.base / 'library'
        library.mkdir()
        self.git('init', '-q', root=library)
        (library / 'value.txt').write_text('good\n')
        self.git('add', '.', root=library)
        self.git('commit', '-qm', 'library', root=library)
        self.repository()
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(library), 'dep')
        self.git('commit', '-qam', 'add dependency')
        self.ok('mem', 'add', 'goal', 'Check dependency', '--task', 't')
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'from pathlib import Path; assert Path("dep/value.txt").read_text() == "good\\n"')
        self.checks({'test': command})
        self.ok('check', '--task', 't')

    def close_accepted(self):
        result = self.ok('mem', 'add', 'result', 'Done', '--task', 't').split()[0]
        return self.cli('task', 'close', 't', '--outcome', 'accepted', '--result', result,
                        '--by', 'assistant', '--refs', 'check observation')

    def test_r4_unchanged_submodule_stays_current(self):
        self.submodule_repository()
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))

    def test_r4_submodule_file_change_invalidates_pass(self):
        self.submodule_repository()
        (self.root / 'dep/value.txt').write_text('broken\n')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertNotEqual(self.close_accepted().returncode, 0)

    def test_r4_submodule_commit_and_untracked_change_invalidate_pass(self):
        self.submodule_repository()
        (self.root / 'dep/extra.txt').write_text('untracked\n')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        (self.root / 'dep/extra.txt').unlink()
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        (self.root / 'dep/value.txt').write_text('good\n')
        self.git('commit', '--allow-empty', '-qm', 'moved', root=self.root / 'dep')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))

    def test_r4_uninitialized_submodule_is_unknown_and_blocks_acceptance(self):
        self.submodule_repository()
        self.git('submodule', 'deinit', '-q', '-f', 'dep')
        packet = self.ok('pack', '--task', 't', '--base', 'HEAD')
        self.assertNotIn('PASS current', packet)
        self.assertIn('unknown', packet)
        self.assertNotEqual(self.close_accepted().returncode, 0)
        decision = self.ok('mem', 'add', 'decision', 'Accept without submodule coverage', '--task', 't').split()[0]
        result = self.ok('mem', 'add', 'result', 'Done anyway', '--task', 't').split()[0]
        self.ok('task', 'close', 't', '--outcome', 'accepted', '--result', result, '--by', 'assistant',
                '--refs', 'explicit exception', '--exception', decision)

    def switched_worker(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        self.git('checkout', '-qb', 'worker-repair', root=worker)
        (worker / 'worker-change.txt').write_text('required implementation\n')
        self.git('add', 'worker-change.txt', root=worker)
        self.git('commit', '-qm', 'worker implementation', root=worker)
        return worker

    def test_r1_switched_branch_blocks_merge_and_clean(self):
        worker = self.switched_worker()
        self.assertNotEqual(self.cli('worktree', 'merge', 't').returncode, 0)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(worker.exists())
        self.assertFalse((self.root / 'worker-change.txt').exists())
        reconcile = self.ok('worktree', 'reconcile', 't', '--apply')
        with self.db() as c:
            self.assertNotEqual(c.execute("SELECT state FROM worktree WHERE piece='one'").fetchone()[0], 'merged')

    def test_r1_restoring_branch_allows_merge_and_clean(self):
        worker = self.switched_worker()
        self.git('checkout', '-q', 'codex/sx-t-one', root=worker)
        self.git('merge', '-q', '--ff-only', 'worker-repair', root=worker)
        out = self.ok('worktree', 'merge', 't')
        self.assertIn('merged one', out)
        self.assertTrue((self.root / 'worker-change.txt').exists())
        self.ok('worktree', 'clean', 't')
        self.assertFalse(worker.exists())

    def test_r1_detached_head_is_rejected(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        self.git('checkout', '-q', '--detach', root=worker)
        self.assertNotEqual(self.cli('worktree', 'merge', 't').returncode, 0)
        self.assertNotEqual(self.cli('worktree', 'clean', 't', '--discard').returncode, 0)
        self.assertTrue(worker.exists())

    def test_r1_commit_after_merge_blocks_clean(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        (worker / 'first.txt').write_text('first\n')
        self.git('add', 'first.txt', root=worker)
        self.git('commit', '-qm', 'first', root=worker)
        self.ok('worktree', 'merge', 't')
        (worker / 'second.txt').write_text('second\n')
        self.git('add', 'second.txt', root=worker)
        self.git('commit', '-qm', 'second', root=worker)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(worker.exists())
        self.ok('worktree', 'merge', 't')
        self.assertTrue((self.root / 'second.txt').exists())
        self.ok('worktree', 'clean', 't')

    def test_r2_missing_context_fails_without_new_store(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        (worker / '.simpleide/context.json').unlink()
        for args in (('mem', 'show', 'P1'), ('mem', 'add', 'note', 'lost'), ('task', 'dispatches', 't')):
            result = self.cli(*args, root=worker, installed=True)
            self.assertNotEqual(result.returncode, 0, args)
            self.assertIn('reconcile', result.stderr + result.stdout)
        self.assertFalse((worker / '.simpleide/project.db').exists())
        self.ok('worktree', 'reconcile', 't', '--apply')
        self.assertIn('Split work', self.ok('mem', 'show', 'P1', root=worker, installed=True))

    def test_r2_declared_standalone_worktree_keeps_own_store(self):
        self.installed_repository()
        other = self.base / 'standalone-worktree'
        self.git('worktree', 'add', '-q', '-b', 'standalone', str(other))
        self.assertNotEqual(self.cli('mem', 'add', 'note', 'mine', root=other, installed=True).returncode, 0)
        self.ok('context', 'standalone', root=other, installed=True)
        self.ok('mem', 'add', 'note', 'mine', root=other, installed=True)
        self.assertTrue((other / '.simpleide/project.db').exists())

    def test_r2_plain_project_still_creates_store(self):
        self.repository()
        self.ok('mem', 'add', 'note', 'plain')
        self.assertTrue((self.root / '.simpleide/project.db').exists())

    def custom_models(self):
        custom = self.base / 'custom-models.json'
        custom.write_text(json.dumps({'codex': {'worker': {'model': 'custom-worker'}}}))
        return custom

    def test_r3_partial_uninstall_preserves_surviving_models(self):
        custom = self.custom_models()
        self.ok('--target', str(self.root), '--tools', 'cursor,codex', '--models', str(custom), install=True)
        agent = self.root / '.codex/agents/sx-worker.toml'
        installed = self.root / '.simpleide/models.json'
        agent_before, models_before = agent.read_bytes(), installed.read_bytes()
        self.assertIn(b'custom-worker', agent_before)
        custom.unlink()
        self.ok('--target', str(self.root), '--tools', 'cursor', '--uninstall', install=True)
        self.assertEqual(agent_before, agent.read_bytes())
        self.assertEqual(models_before, installed.read_bytes())
        self.ok('--target', str(self.root), '--tools', 'cursor', install=True)
        self.assertIn('custom-worker', agent.read_text())
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        self.assertIn('custom-worker', agent.read_text())

    def test_r3_global_partial_uninstall_preserves_models(self):
        custom = self.custom_models()
        self.ok('--global', '--tools', 'cursor,codex', '--models', str(custom), install=True)
        home = Path(self.env['HOME'])
        agents = list(home.rglob('sx-worker.toml'))
        self.assertEqual(len(agents), 1, agents)
        before = agents[0].read_bytes()
        self.ok('--global', '--tools', 'cursor', '--uninstall', install=True)
        self.assertEqual(before, agents[0].read_bytes())

    def test_r3_conflicting_model_flags_fail_without_writes(self):
        custom = self.custom_models()
        self.ok('--target', str(self.root), '--tools', 'cursor,codex', install=True)
        before = self.snapshot()
        result = self.cli('--target', str(self.root), '--tools', 'cursor', '--uninstall', '--models', str(custom), install=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        result = self.cli('--target', str(self.root), '--tools', 'cursor', '--models', str(custom), install=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())




