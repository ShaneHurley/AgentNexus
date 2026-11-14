#!/usr/bin/env python3
"""Local readiness checks in disposable projects; no IDE/model trials.

Prints JSON expectations and observations. A failed expectation is an audit
finding, not a claim about how often the defect occurs in real use.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    observations = []
    with tempfile.TemporaryDirectory(prefix='simpleide-readiness-') as temporary:
        base = Path(temporary)

        def project(name):
            root = base / name
            root.mkdir(parents=True)
            return root

        def call(root, *arguments, script=None, payload=None, extra_env=None):
            env = dict(os.environ, SIMPLEIDE_PROJECT=str(root), SIMPLEIDE_HOME=str(base / 'shared'))
            env.update(extra_env or {})
            result = subprocess.run([sys.executable, str(script or KIT / 'core/sx.py'), *arguments],
                                    cwd=root, env=env, input=json.dumps(payload) if payload is not None else None,
                                    text=True, capture_output=True, timeout=20)
            if result.returncode:
                raise RuntimeError(f'{arguments}: {result.returncode}: {result.stdout} {result.stderr}')
            return result.stdout

        def rows(root, query):
            with sqlite3.connect(root / '.simpleide/project.db') as connection:
                return connection.execute(query).fetchall()

        def check(name, expected, actual, **evidence):
            observations.append(dict(name=name, passed=expected == actual,
                                     expected=expected, actual=actual, **evidence))

        def goal(root, task, title=None):
            return call(root, 'mem', 'add', 'goal', title or task, '--task', task, '--size', 'MEDIUM')

        root = project('partial-uninstall')
        call(root, '--target', str(root), '--tools', 'cursor,codex', script=KIT / 'install.py')
        call(root, '--target', str(root), '--tools', 'cursor', '--uninstall', script=KIT / 'install.py')
        actual = dict(codex_agent=(root / '.codex/agents/sx-worker.toml').exists(),
                      shared_skill=(root / '.agents/skills/simpleide/SKILL.md').exists(),
                      rule=(root / 'AGENTS.md').exists())
        check('Uninstall Cursor preserves the remaining Codex installation',
              dict(codex_agent=True, shared_skill=True, rule=True), actual)

        root = project('outcome')
        goal(root, 'failed')
        call(root, 'mem', 'add', 'result', 'Blocked: acceptance criteria not met; task failed', '--task', 'failed')
        check('A failed result is not automatically counted as accepted', False,
              rows(root, "SELECT outcome FROM run WHERE task='failed'")[0][0] == 'accepted',
              stats=call(root, 'stats'))
        goal(root, 'failed', 'Retry the previously failed task')
        check('Reusing a completed task slug does not silently retain accepted state', False,
              rows(root, "SELECT outcome FROM run WHERE task='failed'")[0][0] == 'accepted')

        root = project('session-isolation')
        for session in ('session-a', 'session-b'):
            call(root, 'hook', 'capture-request', '--host', 'codex',
                 payload={'session_id': session, 'prompt': 'Request for ' + session})
        goal(root, 'task-a')
        check('Adding task A does not attach session B original request', False,
              bool(rows(root, "SELECT 1 FROM rec WHERE kind='request' AND refs='session-b' AND task='task-a'")),
              request_rows=rows(root, "SELECT title,task,refs FROM rec WHERE kind='request' ORDER BY id"))
        # The second run must have a later start to make newest-run selection deterministic.
        goal(root, 'task-b')
        with sqlite3.connect(root / '.simpleide/project.db') as connection:
            connection.execute("UPDATE run SET start='2000-01-01' WHERE task='task-a'")
        call(root, 'hook', 'dispatch-guard', '--host', 'codex', payload={
            'session_id': 'session-a', 'hook_event_name': 'PreToolUse', 'tool_name': 'spawn_agent',
            'tool_input': {'agent_type': 'sx-worker', 'message': 'TASK: task-a\nGOAL: Work\nDONE WHEN: Checked'}})
        call(root, 'hook', 'dispatch-guard', '--host', 'codex', payload={
            'session_id': 'session-a', 'hook_event_name': 'SubagentStart', 'agent_type': 'sx-worker', 'agent_id': 'child-a'})
        check('Lifecycle event retains the task validated by its parent session', 'task-a',
              rows(root, "SELECT task FROM dispatch WHERE child_id='child-a'")[0][0])
        resumed = call(root, 'hook', 'resume', '--host', 'codex', payload={'session_id': 'session-a'})
        check('Session A resume does not restore task B', False, 'simpleIDE task: task-b' in resumed,
              resume_output=resumed)

        root = project('resume-context')
        goal(root, 'recovery')
        for number in range(1, 6):
            call(root, 'mem', 'add', 'criteria', f'Criterion {number}', '--task', 'recovery')
        question = call(root, 'mem', 'add', 'question', 'Which CSV delimiter?', '--task', 'recovery').split()[0]
        call(root, 'mem', 'add', 'decision', 'Use comma; question answered', '--task', 'recovery', '--refs', question)
        resumed = call(root, 'hook', 'resume', '--host', 'codex', payload={})
        check('Resume supplies all criterion text or retrieval IDs within its bound', True,
              ('Criterion 5' in resumed or 'sx mem' in resumed or 'P6' in resumed), resume_output=resumed)
        check('Resume distinguishes an answered question from open questions', True,
              'open questions: 0' in resumed or 'unresolved questions: 0' in resumed, resume_output=resumed)

        root = project('stats-filter')
        goal(root, 'small-selected')
        goal(root, 'other-task')
        scoped_stats = call(root, 'stats', '--task', 'small-selected')
        check('stats --task filters the task summary', False, 'tasks=2' in scoped_stats,
              stats=scoped_stats)

        a, b = project('owner-a/same-name'), project('owner-b/same-name')
        call(a, 'mem', 'lesson', 'Distinct repository lesson', '--body', 'A verified behavior in the first repository')
        search = call(b, 'mem', 'search', 'Distinct repository lesson')
        check('Separate projects with the same folder name can find shared lessons', True,
              'Distinct repository lesson' in search, search_output=search,
              explicit_shared_search=call(b, 'mem', 'search', 'Distinct repository lesson', '--scope', 'shared'))

        a, b = project('promote-a'), project('promote-b')
        call(a, 'mem', 'lesson', 'Promote this local lesson', '--local')
        sharing = call(a, 'mem', 'lesson', 'Promote this local lesson')
        search = call(b, 'mem', 'search', 'Promote')
        check('Explicitly sharing an existing local lesson actually shares it', True,
              'Promote this local lesson' in search, save_output=sharing, search_output=search)

        root = project('worktrees')
        call(root, '--target', str(root), '--tools', 'codex', script=KIT / 'install.py')
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        subprocess.run(['git', 'add', '.'], cwd=root, check=True)
        subprocess.run(['git', '-c', 'user.name=Probe', '-c', 'user.email=probe@example.invalid',
                        'commit', '-qm', 'scratch baseline'], cwd=root, check=True)
        goal(root, 'split')
        tree = Path(call(root, 'worktree', 'add', 'split', 'piece').strip())
        recent = call(tree, 'mem', 'recent', '--task', 'split', script=tree / '.simpleide/sx.py',
                      extra_env={'SIMPLEIDE_PROJECT': ''})
        check('Worker worktree can retrieve the parent task records by default', True,
              'split' in recent, worktree_recent=recent,
              parent_recent=call(root, 'mem', 'recent', '--task', 'split'))
        subprocess.run(['git', 'worktree', 'remove', str(tree)], cwd=root, check=True)

        root = project('global-project')
        home = project('global-home')
        call(root, '--global', '--tools', 'codex', script=KIT / 'install.py', extra_env={'HOME': str(home)})
        global_skill = (home / '.agents/skills/sx-writeup/SKILL.md').read_text()
        command = subprocess.run([sys.executable, '.simpleide/sx.py', 'mem', 'export', '--task', 'trial'],
                                 cwd=root, text=True, capture_output=True, timeout=20)
        check('Global write-up skill points to an available sx.py command', True,
              (root / '.simpleide/sx.py').exists() or str(home / '.simpleide/sx.py') in
              global_skill or 'python3 ~/.simpleide/sx.py' in global_skill,
              installed_skill=global_skill, prescribed_command_exit=command.returncode,
              prescribed_command_stderr=command.stderr)

    report = {'python': sys.version.split()[0], 'kind': 'targeted local readiness probes; no live IDE/model calls',
              'passed': sum(o['passed'] for o in observations), 'total': len(observations), 'observations': observations}
    output = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
