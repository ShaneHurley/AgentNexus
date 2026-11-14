#!/usr/bin/env python3
"""Independent post-repair review; isolated projects, no live host calls."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    observations = []
    with tempfile.TemporaryDirectory(prefix='sx-postrepair-review-') as temporary:
        base = Path(temporary)
        home = base / 'home'
        home.mkdir()
        env = dict(os.environ, HOME=str(home), SIMPLEIDE_HOME=str(base / 'shared'))
        for key in ('SIMPLEIDE_STORE', 'SIMPLEIDE_PROJECT', 'SIMPLEIDE_TASK', 'SIMPLEIDE_SESSION', 'SIMPLEIDE_HOST'):
            env.pop(key, None)

        def run(root, argv, ok=True):
            result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=40)
            data = dict(code=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if ok:
                assert result.returncode == 0, data
            return data

        def sx(root, *argv, ok=True):
            return run(root, [sys.executable, str(KIT / 'core/sx.py'), *argv], ok)

        def install(root, *argv):
            return run(root, [sys.executable, str(KIT / 'install.py'), '--target', str(root), *argv])

        def git(root, *argv):
            return run(root, ['git', '-c', 'user.name=Review', '-c', 'user.email=review@example.invalid', *argv])

        def repo(name, installed=True):
            root = base / name
            root.mkdir()
            git(root, 'init', '-q')
            if installed:
                install(root, '--tools', 'codex')
            (root / 'baseline.txt').write_text('baseline\n')
            git(root, 'add', '.')
            git(root, 'commit', '-qm', 'baseline')
            return root

        root = repo('branch-change')
        sx(root, 'mem', 'add', 'goal', 'Integrate worker', '--task', 't')
        worker = Path(sx(root, 'worktree', 'add', 't', 'one')['stdout'].strip())
        git(worker, 'checkout', '-qb', 'worker-repair')
        (worker / 'worker-change.txt').write_text('required implementation\n')
        git(worker, 'add', 'worker-change.txt')
        git(worker, 'commit', '-qm', 'worker implementation')
        merge = sx(root, 'worktree', 'merge', 't', ok=False)
        clean = sx(root, 'worktree', 'clean', 't', ok=False)
        observations.append(dict(id='R1_branch_mismatch',
            expected='Refuse merge/clean when actual worktree branch differs from recorded branch',
            merge=merge, cleanup=clean, implementation_integrated=(root / 'worker-change.txt').exists(),
            worker_removed=not worker.exists()))

        root = repo('missing-pointer')
        goal = sx(root, 'mem', 'add', 'goal', 'Parent evidence', '--task', 't')['stdout'].split()[0]
        worker = Path(sx(root, 'worktree', 'add', 't', 'one')['stdout'].strip())
        (worker / '.simpleide/context.json').unlink()
        read = sx(worker, 'mem', 'show', goal, ok=False)
        observations.append(dict(id='R2_missing_context',
            expected='Fail for a managed worktree with missing store pointer; do not create a new store',
            read=read, replacement_database_created=(worker / '.simpleide/project.db').exists()))

        root = base / 'model-settings'
        root.mkdir()
        custom = base / 'models.json'
        custom.write_text(json.dumps({'codex': {'worker': {'model': 'custom-worker'}}}))
        install(root, '--tools', 'cursor,codex', '--models', str(custom))
        before = (root / '.codex/agents/sx-worker.toml').read_text()
        install(root, '--tools', 'cursor', '--uninstall')
        after = (root / '.codex/agents/sx-worker.toml').read_text()
        observations.append(dict(id='R3_partial_uninstall_models',
            expected='Uninstalling Cursor preserves the remaining Codex model selection',
            before_model=next(s for s in before.splitlines() if s.startswith('model =')),
            after_model=next(s for s in after.splitlines() if s.startswith('model =')),
            codex_agent_unchanged=before == after))

        library = repo('library', installed=False)
        (library / 'value.txt').write_text('good\n')
        git(library, 'add', 'value.txt')
        git(library, 'commit', '-qm', 'library input')
        root = repo('submodule-check')
        git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(library), 'dep')
        git(root, 'commit', '-qam', 'add dependency')
        sx(root, 'mem', 'add', 'goal', 'Check dependency', '--task', 't')
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'from pathlib import Path; assert Path("dep/value.txt").read_text() == "good\\n"')
        (root / '.simpleide/config.json').write_text(json.dumps({'confirmed': True, 'checks': {'test': command}}))
        sx(root, 'check', '--task', 't')
        (root / 'dep/value.txt').write_text('broken\n')
        packet = sx(root, 'pack', '--task', 't', '--base', 'HEAD')
        result_id = sx(root, 'mem', 'add', 'result', 'Done', '--task', 't')['stdout'].split()[0]
        close = sx(root, 'task', 'close', 't', '--outcome', 'accepted', '--result', result_id,
                   '--by', 'assistant', '--refs', 'check observation', ok=False)
        actual_check = run(root, ['sh', '-c', command], ok=False)
        observations.append(dict(id='R4_submodule_freshness',
            expected='Changed tested submodule content invalidates PASS; accepted closure requires fresh checks',
            packet=packet, close=close, actual_check_now=actual_check,
            git_status=git(root, 'status', '--short')['stdout']))

    args.out.write_text(json.dumps({'python': sys.version.split()[0], 'observations': observations}, indent=2) + '\n')
    print(json.dumps(observations, indent=2))


if __name__ == '__main__':
    main()
