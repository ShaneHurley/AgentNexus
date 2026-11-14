#!/usr/bin/env python3
"""Reproduce the 2026-11-10 evaluation in disposable projects; no models used.

Run with Python 3.12. JSON contains actual CLI/hook-process observations, not
observations of hooks firing inside an IDE. --out saves the same report to disk.
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
RESULTS = []


def record(name, expected, actual):
    RESULTS.append(dict(name=name, passed=expected == actual, expected=expected, actual=actual))


def call(root, script, *args, payload=None):
    env = dict(os.environ, SIMPLEIDE_PROJECT=str(root), SIMPLEIDE_HOME=str(root.parent / 'shared'))
    return subprocess.run([sys.executable, str(script), *args], cwd=root, env=env,
                          input=json.dumps(payload) if payload is not None else None,
                          text=True, capture_output=True, timeout=20)


def hook(root, event, payload, host='cursor'):
    result = call(root, KIT / 'core/sx.py', 'hook', event, '--host', host, payload=payload)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='simpleide-probe-') as temporary:
        base = Path(temporary)
        cursor = base / 'cursor'
        cursor.mkdir()
        result = call(cursor, KIT / 'install.py', '--target', str(cursor), '--tools', 'cursor', '--hooks')
        record('Cursor-only installation exits successfully', 0, result.returncode)
        record('Cursor-only installation includes both skills', [True, True], [
            (cursor / '.agents/skills' / skill / 'SKILL.md').exists()
            for skill in ('simpleide', 'sx-writeup')])
        config = json.loads((cursor / '.cursor/hooks.json').read_text())
        record('Fresh Cursor hook configuration has required version', 1, config.get('version'))

        template = (KIT / 'skill/simpleide/references/brief-template.md').read_text().split('```')[1]
        actual = hook(cursor, 'dispatch-guard', {'subagent_type': 'sx-worker', 'task': template})
        record('Documented brief template passes dispatch guard', 'allow', actual.get('permission'))

        ledger = base / 'ledger'
        ledger.mkdir()
        sx = KIT / 'core/sx.py'
        call(ledger, sx, 'mem', 'add', 'goal', 'Ledger test', '--task', 'trial', '--size', 'MEDIUM')
        brief = 'TASK: trial\nGOAL: Verify\nDONE WHEN: Tested'
        for ident in ('a', 'b', 'c'):
            hook(ledger, 'dispatch-guard', {'subagent_type': 'sx-worker', 'subagent_id': ident, 'task': brief})
        for ident in ('a', 'b', 'c'):
            hook(ledger, 'return-log', {'subagent_type': 'sx-worker', 'subagent_id': ident,
                                      'summary': 'STATUS: done\nCHANGED: none'})
        with sqlite3.connect(ledger / '.simpleide/project.db') as connection:
            statuses = [r[0] for r in connection.execute('SELECT return_status FROM dispatch ORDER BY id')]
        record('Three returned workers all become inactive', ['done', 'done', 'done'], statuses)
        first = hook(ledger, 'dispatch-guard', {'subagent_type': 'sx-worker', 'task': brief})
        second = hook(ledger, 'dispatch-guard', {'subagent_type': 'sx-worker', 'task': brief})
        record('Two fresh workers allowed after completed parallel work', ['allow', 'allow'],
               [first.get('permission'), second.get('permission')])

        checks = base / 'checks'
        (checks / '.simpleide').mkdir(parents=True)
        call(checks, sx, 'mem', 'add', 'goal', 'Check order', '--task', 'trial', '--size', 'MEDIUM')
        for exit_code in (1, 0, 1):
            command = f'"{sys.executable}" -c "raise SystemExit({exit_code})"'
            (checks / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {'test': command}}))
            call(checks, sx, 'check', 'test', '--task', 'trial')
        with sqlite3.connect(checks / '.simpleide/project.db') as connection:
            titles = [r[0] for r in connection.execute("SELECT title FROM rec WHERE kind='test' ORDER BY id")]
        record('Fail/pass/fail check history preserves all observations', ['test: FAIL', 'test: PASS', 'test: FAIL'], titles)
        stopped = hook(checks, 'stop-check', {'hook_event_name': 'Stop'}, 'codex')
        record('Stop warning identifies latest failed check', True, 'last check failed' in stopped.get('reason', ''))

        guards = base / 'guards'
        guards.mkdir()
        # Payloads only: none of these commands is executed.
        for command in ('git reset --hard HEAD', 'git push -f origin main', 'git clean -fdx',
                        'rm --recursive /tmp/simpleide-outside-probe'):
            decision = hook(guards, 'shell-guard', {'command': command})
            record('Shell guard denies: ' + command, 'deny', decision.get('permission'))

        pre = {'hook_event_name': 'PreToolUse', 'tool_name': 'spawn_agent',
               'tool_input': {'agent_type': 'sx-worker', 'message': brief}}
        start = {'hook_event_name': 'SubagentStart', 'agent_type': 'sx-worker', 'agent_id': 'a'}
        limited = base / 'codex-limits'
        limited.mkdir()
        call(limited, sx, 'mem', 'add', 'goal', 'Codex limits', '--task', 'trial', '--size', 'MEDIUM')
        for ident in ('a', 'b', 'c'):
            hook(limited, 'dispatch-guard', pre, 'codex')
            hook(limited, 'dispatch-guard', dict(start, agent_id=ident), 'codex')
        denied = hook(limited, 'dispatch-guard', pre, 'codex')
        record('Codex fourth worker is denied by PreToolUse', 'deny',
               denied.get('hookSpecificOutput', {}).get('permissionDecision'))
        for ident in ('a', 'b', 'c'):
            hook(limited, 'return-log', dict(start, hook_event_name='SubagentStop', agent_id=ident,
                                           last_assistant_message='STATUS: done'), 'codex')
        with sqlite3.connect(limited / '.simpleide/project.db') as connection:
            statuses = [r[0] for r in connection.execute('SELECT return_status FROM dispatch ORDER BY id')]
        record('Codex returned workers all become inactive', ['done', 'done', 'done'], statuses)

    report = {'python': sys.version.split()[0], 'kind': 'local subprocess probes; not live IDE trials',
              'passed': sum(r['passed'] for r in RESULTS), 'total': len(RESULTS), 'observations': RESULTS}
    output = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
