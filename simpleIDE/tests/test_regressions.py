"""Regression coverage for defects reproduced in the runtime evaluation."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from test_sx import INSTALL, ROOT, SX, call


class Regressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def sx(self, *args, root=None, data=None):
        result = call(SX, *args, cwd=root or self.root, data=data)
        return result

    def hook(self, host, event, data, root=None):
        result = self.sx('hook', event, '--host', host, root=root, data=data)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def goal(self, task='trial', root=None):
        result = self.sx('mem', 'add', 'goal', 'Verify runtime', '--task', task, '--size', 'MEDIUM', root=root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def rows(self, query, root=None):
        with sqlite3.connect((root or self.root) / '.simpleide/project.db') as connection:
            return connection.execute(query).fetchall()

    def start(self, host, ident, session='parent', task='trial', root=None):
        brief = f'TASK: {task}\nGOAL: Verify\nDONE WHEN: Tested'
        data = {'agent_type': 'sx-worker', 'agent_id': ident, 'session_id': session,
                'hook_event_name': 'SubagentStart'}
        if host == 'cursor':
            data = {'subagent_type': 'sx-worker', 'subagent_id': ident,
                    'parent_conversation_id': session, 'task': brief}
        elif host == 'claude':
            data = {'session_id': session, 'tool_use_id': ident, 'hook_event_name': 'PreToolUse',
                    'tool_input': {'subagent_type': 'sx-worker', 'prompt': brief}}
        if host == 'codex':
            self.hook(host, 'dispatch-guard', {'session_id':session, 'tool_call_id':ident,
                'hook_event_name':'PreToolUse','tool_input':{'agent_type':'sx-worker','message':brief}},root=root)
            data['tool_call_id'] = ident
        return self.hook(host, 'dispatch-guard', data, root=root)

    def stop(self, host, ident, session='parent', root=None):
        data = {'agent_type': 'sx-worker', 'agent_id': ident, 'session_id': session,
                'hook_event_name': 'SubagentStop', 'last_assistant_message': 'STATUS: done'}
        if host == 'cursor':
            data = {'subagent_type': 'sx-worker', 'child_conversation_id': ident,
                    'parent_conversation_id': session, 'summary': 'STATUS: done'}
        return self.hook(host, 'return-log', data, root=root)

    def test_each_single_tool_installs_both_skills(self):
        for host in ('claude', 'cursor', 'codex', 'antigravity'):
            with self.subTest(host=host):
                project = self.root / host
                project.mkdir()
                result = call(INSTALL, '--target', str(project), '--tools', host, cwd=project)
                self.assertEqual(result.returncode, 0, result.stderr)
                skills = project / ('.claude/skills' if host == 'claude' else '.agents/skills')
                for skill in ('simpleide', 'sx-writeup'):
                    self.assertTrue((skills / skill / 'SKILL.md').is_file())

    def test_fresh_cursor_hooks_have_version_and_reinstall_is_idempotent(self):
        for _ in range(2):
            result = call(INSTALL, '--target', str(self.root), '--tools', 'cursor', '--hooks', cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((self.root / '.cursor/hooks.json').read_text())
            self.assertEqual(config['version'], 1)
            self.assertEqual(len(config['hooks']['subagentStart']), 1)

    def test_missing_cursor_version_is_added_without_reformatting_user_entries(self):
        path = self.root / '.cursor/hooks.json'
        path.parent.mkdir()
        entry = '{ "command" : "python own.py" }'
        path.write_text('{"hooks":{"stop":[' + entry + ']}}\n')
        result = call(INSTALL, '--target', str(self.root), '--tools', 'cursor', '--hooks', cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text())['version'], 1)
        self.assertIn(entry, path.read_text())

    def test_shipped_briefs_and_standalone_headings_pass_all_blocking_guards(self):
        self.goal('export-streaming')
        text = (ROOT / 'skill/simpleide/references/brief-template.md').read_text()
        briefs = text.split('```')[1::2] + ['GOAL\nDo work\nDONE WHEN\nChecked']
        for host in ('cursor', 'claude', 'codex'):
            for brief in briefs:
                with self.subTest(host=host, brief=brief):
                    if host == 'cursor':
                        data = {'subagent_type': 'sx-worker', 'task': brief}
                    else:
                        data = {'hook_event_name': 'PreToolUse', 'tool_input': {
                            'subagent_type': 'sx-worker', 'prompt': brief}}
                    result = self.hook(host, 'dispatch-guard', data)
                    if host == 'cursor':
                        self.assertEqual(result.get('permission'), 'allow')
                    else:
                        self.assertNotEqual(result.get('hookSpecificOutput', {}).get('permissionDecision'), 'deny')

    def test_empty_and_missing_sections_are_rejected(self):
        for host in ('cursor', 'claude', 'codex'):
            for brief in ('', 'GOAL: Work', 'Text with GOAL: and DONE WHEN: embedded'):
                with self.subTest(host=host, brief=brief):
                    data = {'subagent_type': 'sx-worker', 'task': brief} if host == 'cursor' else {
                        'hook_event_name': 'PreToolUse', 'tool_input': {'agent_type': 'sx-worker', 'message': brief}}
                    result = self.hook(host, 'dispatch-guard', data)
                    decision = result.get('permission') if host == 'cursor' else result['hookSpecificOutput']['permissionDecision']
                    self.assertEqual(decision, 'deny')
        self.assertEqual(self.rows('SELECT COUNT(*) FROM dispatch')[0][0], 0)

    def test_parallel_returns_correlate_out_of_order_and_duplicates_are_idempotent(self):
        for host in ('cursor', 'codex'):
            with self.subTest(host=host):
                root = self.root / host
                root.mkdir()
                self.goal(root=root)
                for ident in ('a', 'b', 'c'):
                    self.start(host, ident, root=root)
                self.stop(host, 'b', root=root)
                self.stop(host, 'b', root=root)
                self.stop(host, 'unknown', root=root)
                self.assertEqual(self.rows('SELECT return_status FROM dispatch ORDER BY id', root),
                                 [('',), ('done',), ('',)])
                self.stop(host, 'c', root=root)
                self.stop(host, 'a', root=root)
                self.assertEqual(self.rows('SELECT return_status FROM dispatch ORDER BY id', root), [('done',)] * 3)
                self.start(host, 'd', root=root)
                self.start(host, 'e', root=root)
                self.assertEqual(self.rows("SELECT COUNT(*) FROM dispatch WHERE return_status=''", root)[0][0], 2)

    def test_return_identity_does_not_cross_sessions_or_hosts(self):
        self.goal()
        for host, session in (('cursor', 'one'), ('cursor', 'two'), ('codex', 'one')):
            self.start(host, 'same-id', session=session)
        self.stop('cursor', 'same-id', session='one')
        self.assertEqual(self.rows('SELECT return_status FROM dispatch ORDER BY id'), [('done',), ('',), ('',)])

    def test_claude_launch_logs_child_identity_once(self):
        self.goal()
        self.start('claude', 'call-a')
        self.hook('claude', 'dispatch-guard', {'hook_event_name': 'SubagentStart', 'session_id': 'parent',
                                            'agent_type': 'sx-worker', 'agent_id': 'child-a', 'tool_use_id':'call-a'})
        self.stop('claude', 'child-a')
        self.assertEqual(self.rows('SELECT return_status FROM dispatch'), [('done',)])

    def test_legacy_return_without_id_uses_unique_brief_and_rejects_ambiguity(self):
        self.goal()
        for brief in ('TASK: trial\nGOAL: First\nDONE WHEN: Checked', 'TASK: trial\nGOAL: Second\nDONE WHEN: Checked'):
            self.hook('cursor', 'dispatch-guard', {'subagent_type': 'sx-worker', 'task': brief})
        self.hook('cursor', 'return-log', {'subagent_type': 'sx-worker', 'summary': 'STATUS: done'})
        self.hook('cursor', 'return-log', {})
        self.assertEqual(self.rows('SELECT return_status FROM dispatch ORDER BY id'), [('',), ('',)])
        self.hook('cursor', 'return-log', {'subagent_type': 'sx-worker', 'task': brief, 'summary': 'STATUS: done'})
        self.assertEqual(self.rows('SELECT return_status FROM dispatch ORDER BY id'), [('',), ('done',)])

    def test_concurrent_cursor_starts_enforce_limit_atomically(self):
        self.goal()
        def launch(i):
            return self.start('cursor', str(i)).get('permission')
        with ThreadPoolExecutor(max_workers=6) as executor:
            decisions = list(executor.map(launch, range(6)))
        self.assertEqual(decisions.count('allow'), 3)
        self.assertEqual(decisions.count('deny'), 3)
        self.assertEqual(self.rows('SELECT COUNT(*) FROM dispatch')[0][0], 3)

    def test_replayed_start_does_not_double_count(self):
        self.goal()
        self.start('cursor', 'a')
        self.start('cursor', 'a')
        self.stop('cursor', 'a')
        self.start('cursor', 'a')
        self.assertEqual(self.rows('SELECT return_status FROM dispatch'), [('done',)])

    def test_existing_dispatch_database_migrates_without_losing_records(self):
        path = self.root / '.simpleide/project.db'
        path.parent.mkdir()
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE dispatch(id INTEGER PRIMARY KEY, task TEXT NOT NULL, agent TEXT NOT NULL, "
                               "model TEXT NOT NULL DEFAULT '', brief_length INTEGER NOT NULL DEFAULT 0, "
                               "ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, return_status TEXT NOT NULL DEFAULT '')")
            connection.execute("INSERT INTO dispatch(task,agent,return_status) VALUES('old','sx-worker','done')")
        self.goal()
        self.start('cursor', 'new')
        self.stop('cursor', 'new')
        self.assertEqual(self.rows('SELECT task,return_status FROM dispatch ORDER BY id'), [('old', 'done'), ('trial', 'done')])

    def test_repeated_checks_keep_chronology_and_distinct_artifacts(self):
        for sequence in ((1, 0, 1), (0, 1, 0)):
            with self.subTest(sequence=sequence):
                root = self.root / ''.join(map(str, sequence))
                root.mkdir()
                self.goal(root=root)
                for code in sequence:
                    command = f'"{sys.executable}" -c "raise SystemExit({code})"'
                    (root / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {'test': command}}))
                    result = self.sx('check', 'test', '--task', 'trial', root=root)
                    self.assertEqual(result.returncode, code, result.stderr)
                rows = self.rows("SELECT title,refs FROM rec WHERE kind='test' ORDER BY id", root)
                self.assertEqual([r[0] for r in rows], ['test: FAIL' if code else 'test: PASS' for code in sequence])
                self.assertEqual(len(set(r[1] for r in rows)), 3)
                self.assertTrue(all((root / r[1]).exists() for r in rows))
                stopped = self.hook('codex', 'stop-check', {'hook_event_name': 'Stop', 'task_slug':'trial'}, root)
                self.assertEqual('failed' in stopped['reason'], bool(sequence[-1]))
                exported = self.sx('mem', 'export', '--task', 'trial', root=root)
                self.assertEqual(exported.stdout.count('**test:'), 3)

    def test_shell_guard_flag_variants_and_safe_controls(self):
        denied = ['git push -f origin main', 'git push --force-with-lease origin main',
                  'git -C repo push --force origin main', 'git push -f -o -n', 'git push -fo -n',
                  'git clean -fdx -e -n', 'git clean -fdx', 'git clean -f -d',
                  'git clean -xdf', 'git reset --hard HEAD',
                  'rm --recursive /tmp/simpleide-outside-probe', '/bin/rm -rf /tmp/simpleide-outside-probe',
                  'rm -r -f ../outside', 'cd /tmp && rm -rf relative', 'cd -- /tmp && rm -rf relative',
                  'sh -c "git push -f origin main"', 'npm publish', 'cargo publish']
        allowed = ['git push origin main', 'git status --short', 'git clean -nfdx',
                   'git push --dry-run -f origin main', 'rm -rf build', 'rm -r -- ./-folder',
                   'echo "git push -f origin main"', 'npm run publish-check', 'cargo publish --dry-run']
        for command, expected in [(c, 'deny') for c in denied] + [(c, 'allow') for c in allowed]:
            with self.subTest(command=command):
                actual = self.hook('cursor', 'shell-guard', {'command': command})
                self.assertEqual(actual.get('permission'), expected)

    def test_shell_guard_uses_event_cwd_and_recognizes_readonly_role(self):
        result = self.hook('cursor', 'shell-guard', {'command': 'rm -rf relative', 'cwd': '/tmp'})
        self.assertEqual(result['permission'], 'deny')
        result = self.hook('cursor', 'shell-guard', {'command': 'touch file', 'subagent_type': 'sx-reviewer'})
        self.assertEqual(result['permission'], 'deny')

    def test_shell_guard_handles_host_payloads_and_fails_closed_on_invalid_input(self):
        for host in ('cursor', 'claude', 'codex'):
            result = self.hook(host, 'shell-guard', {'tool_input': {'cmd': 'git push -f origin main'}})
            decision = result.get('permission') if host == 'cursor' else result['hookSpecificOutput']['permissionDecision']
            self.assertEqual(decision, 'deny')
            for data in ({}, {'command': ['git', 'status']}, {'command': 'rm "unclosed'},
                         {'command': 'rm -rf relative', 'cwd': ['/tmp']}):
                invalid = self.sx('hook', 'shell-guard', '--host', host, data=data)
                self.assertEqual(invalid.returncode, 2, invalid.stdout + invalid.stderr)


if __name__ == '__main__':
    unittest.main()
