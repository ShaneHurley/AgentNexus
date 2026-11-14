#!/usr/bin/env python3
"""Additional local audit cases. Uses disposable stores; never invokes an IDE.

Exit zero means the harness completed, not that all expectations passed.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
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
    with tempfile.TemporaryDirectory(prefix='simpleide-followup-') as temporary:
        base = Path(temporary)

        def project(name):
            root = base / name
            root.mkdir()
            return root

        def call(root, *argv, payload=None, install=False):
            env = dict(os.environ, SIMPLEIDE_PROJECT=str(root),
                       SIMPLEIDE_HOME=str(base / 'shared'), HOME=str(base / 'home'))
            result = subprocess.run(
                [sys.executable, str(KIT / ('install.py' if install else 'core/sx.py')), *argv],
                cwd=root, env=env, input=json.dumps(payload) if payload is not None else None,
                capture_output=True, text=True, timeout=30)
            return dict(code=result.returncode, stdout=result.stdout, stderr=result.stderr)

        def good(result):
            assert result['code'] == 0, result
            return result['stdout']

        def check(key, expected, actual, **evidence):
            observations.append(dict(id=key, passed=expected == actual,
                                     expected=expected, actual=actual, **evidence))

        def git(root, *argv):
            result = subprocess.run(['git', '-c', 'user.name=Audit', '-c', 'user.email=audit@example.invalid',
                                     *argv], cwd=root, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr
            return result.stdout

        def repository(name):
            root = project(name)
            git(root, 'init', '-q')
            (root / '.gitignore').write_text('.simpleide/\n')
            (root / 'source.txt').write_text('original\n')
            git(root, 'add', '.')
            git(root, 'commit', '-qm', 'baseline')
            return root

        root = project('identity')
        good(call(root, 'mem', 'add', 'note', 'Keep'))
        old = good(call(root, 'mem', 'add', 'note', 'Original evidence')).split()[0]
        good(call(root, 'mem', 'forget', old))
        replacement = good(call(root, 'mem', 'add', 'note', 'Unrelated replacement')).split()[0]
        check('N01_record_id_reuse', False, old == replacement,
              old_id=old, replacement_id=replacement, old_reference_now=good(call(root, 'mem', 'show', old)))

        root = project('fts-upgrade')
        (root / '.simpleide').mkdir()
        spec = importlib.util.spec_from_file_location('audit_sx', KIT / 'core/sx.py')
        sx = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sx)
        with sqlite3.connect(root / '.simpleide/project.db') as con:
            con.executescript(sx.SCHEMA)
            con.execute("INSERT INTO rec(uid,ts,kind,title) VALUES('old','2026-11-11','note','Legacy needle')")
        output = good(call(root, 'mem', 'search', 'needle', '--scope', 'project'))
        check('N02_fts_initial_population', True, 'Legacy needle' in output,
              output=output, setup='Existing store with rows and no FTS tables, representing fallback-only storage')

        root = project('named-checks')
        good(call(root, 'mem', 'add', 'goal', 'Verify all checks', '--task', 't', '--size', 'MEDIUM'))
        command = shlex.quote(sys.executable) + ' -c '
        (root / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {
            'test': command + shlex.quote('raise SystemExit(1)'),
            'lint': command + shlex.quote('print("lint passed")')}}))
        checks = call(root, 'check', '--task', 't')
        assert checks['code'] == 1, checks
        stop = good(call(root, 'hook', 'stop-check', '--host', 'codex', payload={'task_slug': 't'}))
        check('N03_stop_remembers_failed_named_check', True, 'failed' in stop.lower(),
              checks=checks, stop_output=stop)
        good(call(root, 'mem', 'add', 'result', 'Implementation written', '--task', 't'))
        with sqlite3.connect(root / '.simpleide/project.db') as con:
            con.execute('UPDATE run SET stop_warned=0')
        stop = good(call(root, 'hook', 'stop-check', '--host', 'codex', payload={'task_slug': 't'}))
        check('N04_result_does_not_hide_failed_checks', True, 'failed' in stop.lower(), stop_output=stop)

        root = repository('check-revision')
        good(call(root, 'mem', 'add', 'goal', 'Validate source', '--task', 't'))
        (root / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {
            'test': command + shlex.quote('from pathlib import Path; assert Path("source.txt").read_text() == "original\\n"')}}))
        good(call(root, 'check', '--task', 't'))
        (root / 'source.txt').write_text('broken\n')
        packet = good(call(root, 'pack', '--task', 't', '--base', 'HEAD'))
        check('N05_stale_check_is_distinguished', True,
              'stale' in packet.lower() or 'unverified' in packet.lower(), packet=packet)

        root = repository('pathnames')
        git(root, 'config', 'core.quotePath', 'true')
        (root / 'allowed').mkdir()
        (root / 'allowed/caf\u00e9.py').write_text('pass\n')
        scope = call(root, 'scope', '--base', 'HEAD', '--allow', 'allowed/**')
        check('N06_scope_handles_git_quoted_paths', 0, scope['code'], output=scope)

        root = repository('cleanup')
        first = Path(good(call(root, 'worktree', 'add', 't', 'one')).strip())
        second = Path(good(call(root, 'worktree', 'add', 't', 'two')).strip())
        (second / 'pending.txt').write_text('uncommitted\n')
        partial = call(root, 'worktree', 'clean', 't')
        assert partial['code'] != 0, partial
        check('N07_cleanup_preflights_all_pieces', True, first.exists(), output=partial)
        (second / 'pending.txt').unlink()
        retry = call(root, 'worktree', 'clean', 't')
        check('N08_cleanup_retry_recovers', 0, retry['code'], output=retry)

        root = repository('cleanup-evidence')
        worker = Path(good(call(root, 'worktree', 'add', 't', 'one')).strip())
        good(call(worker, 'mem', 'add', 'finding', 'Only copy of worker evidence', '--task', 't'))
        result = good(call(root, 'worktree', 'clean', 't'))
        parent_has_record = 'Only copy' in good(call(root, 'mem', 'recent', '--task', 't'))
        check('N09_cleanup_preserves_worker_ledger', True,
              (worker / '.simpleide/project.db').exists() or parent_has_record,
              output=result, parent_has_record=parent_has_record)

        root = project('invalid-hook-config')
        (root / '.cursor').mkdir()
        (root / '.cursor/hooks.json').write_text('{ invalid json\n')
        result = call(root, '--target', str(root), '--tools', 'cursor', '--hooks', install=True)
        assert result['code'] != 0, result
        check('N10_installer_preflight_before_writes', False, (root / '.simpleide/sx.py').exists(),
              output=result, installed_agent=(root / '.cursor/agents/sx-worker.md').exists())

        root = project('brief-content')
        response = good(call(root, 'hook', 'dispatch-guard', '--host', 'cursor', payload={
            'subagent_type': 'sx-worker', 'conversation_id': 's', 'task': 'GOAL:\nDONE WHEN:'}))
        check('N11_empty_sections_are_denied', 'deny', json.loads(response)['permission'], response=response)

        root = project('search-attribution')
        good(call(root, 'mem', 'lesson', 'Search target', '--local'))
        note = good(call(root, 'mem', 'add', 'note', 'Unrelated')).split()[0]
        good(call(root, 'mem', 'search', 'target'))
        good(call(root, 'mem', 'show', note))
        with sqlite3.connect(root / '.simpleide/project.db') as con:
            opened = con.execute('SELECT opened FROM search_log ORDER BY id DESC LIMIT 1').fetchone()[0]
        check('N12_unrelated_show_not_counted_as_search_use', 0, opened)

        root = project('hook-ownership')
        (root / '.cursor').mkdir()
        user_entry = {'command': 'echo "documented .simpleide/sx.py hook syntax"'}
        (root / '.cursor/hooks.json').write_text(json.dumps({'version': 1, 'hooks': {'stop': [user_entry]}}))
        good(call(root, '--target', str(root), '--tools', 'cursor', '--hooks', install=True))
        actual_entries = json.loads((root / '.cursor/hooks.json').read_text())['hooks']['stop']
        check('N13_hook_ownership_not_substring', True, user_entry in actual_entries,
              original=user_entry, actual_entries=actual_entries)

    result = dict(python=sys.version.split()[0], total=len(observations),
                  unmet=sum(not item['passed'] for item in observations), observations=observations)
    text = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
