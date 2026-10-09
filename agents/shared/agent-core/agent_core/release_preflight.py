"""Bounded offline publication checks. Findings never contain matched content.

No fixture exemptions are implicit: candidate fixtures require review and block
publication unless an explicit reviewed manifest pins file hashes and exact spans.
"""
from __future__ import annotations
from collections import OrderedDict
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import time

MAX_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_FILES = 20000
MAX_COMMITS = 1000
PATTERNS = (
    re.compile(rb"(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"(?i)(?:api[_-]?key|password|client[_-]?secret|access[_-]?token)\s*[=:]\s*[\"']([^\"'\r\n]{16,})[\"']"),
)

def _runtime(path):
    parts = Path(path).parts
    name = Path(path).name.lower()
    return (any(p in {'.venv', 'venv', '__pycache__', '.daily-coder', '.research-forge'} for p in parts)
            or name == '.env' or name.startswith('.env.') and name not in {'.env.example', '.env.sample', '.env.template'}
            or name.endswith(('.sqlite', '.sqlite3', '.db', '.pyc', '.sqlite-wal', '.sqlite-shm')))

def release_preflight(root, base_ref='origin/main', *, fixture_manifest=None):
    """Return JSON-safe redacted inventory and fail closed on incomplete scans."""
    root = Path(root).resolve()
    result = {'ok': False, 'complete': True, 'findings': [], 'inventory': {}, 'scanned_bytes': 0}
    approvals = {}
    def finding(kind, layer, path=None, line=None, status='blocking'):
        item = {'kind': kind, 'layer': layer, 'status': status}
        if path is not None:
            # Paths themselves can contain credentials; sanitize before output.
            raw = os.fsencode(path)
            for pattern in PATTERNS:
                raw = pattern.sub(b'[REDACTED]', raw)
            item['path'] = os.fsdecode(raw)
        if line is not None:
            item['line'] = line
        result['findings'].append(item)
    def incomplete(layer, path=None):
        result['complete'] = False
        finding('scan-incomplete', layer, path)
    def git(*args):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_NO_REPLACE_OBJECTS': '1'})
        proc = subprocess.Popen(['git', '--no-pager', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
        data = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + 15
                while selector.get_map():
                    if time.monotonic() > deadline:
                        raise ValueError('limit')
                    for key, _ in selector.select(.2):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise ValueError('limit')
            if proc.wait(timeout=1):
                raise ValueError('git failed')
            return bytes(data)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdout.close()
    def paths(data):
        values = [os.fsdecode(v) for v in data.split(b'\0') if v]
        if len(values) > MAX_FILES:
            raise ValueError('limit')
        return values
    def scan(data, layer, path, *, allow_fixtures=True):
        result['scanned_bytes'] += len(data)
        if result['scanned_bytes'] > MAX_TOTAL_BYTES:
            raise ValueError('limit')
        for pattern in PATTERNS:
            for match in pattern.finditer(data):
                approved = allow_fixtures and (hashlib.sha256(data).hexdigest(), match.start(), match.end()) in approvals.get(path, set())
                finding('secret', layer, path, data[:match.start()].count(b'\n') + 1, 'reviewed' if approved else 'blocking')
                if len(result['findings']) >= 1000:
                    raise ValueError('limit')
    def safe_file(path):
        parts = Path(path).parts
        if Path(path).is_absolute() or '..' in parts or not parts:
            raise ValueError('escape')
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                return None
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('non-regular')
                data = stream.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError('limit')
                return data
        finally:
            os.close(directory)
    try:
        if fixture_manifest is not None:
            manifest_path = Path(fixture_manifest)
            if manifest_path.is_absolute():
                manifest_path = manifest_path.relative_to(root)
            if '..' in manifest_path.parts:
                raise ValueError('manifest escapes root')
            manifest_data = safe_file(str(manifest_path))
            manifest = json.loads(manifest_data)
            if manifest.get('version') != 1 or not isinstance(manifest.get('fixtures'), list):
                raise ValueError('invalid manifest')
            for entry in manifest['fixtures']:
                path = entry['path']
                if not isinstance(path, str) or Path(path).is_absolute() or '..' in Path(path).parts:
                    raise ValueError('invalid fixture path')
                digest = entry['sha256']
                if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                    raise ValueError('invalid fixture hash')
                for span in entry['spans']:
                    start, end = span['start'], span['end']
                    if type(start) is not int or type(end) is not int or not 0 <= start < end <= MAX_BYTES:
                        raise ValueError('invalid fixture span')
                    approvals.setdefault(path, set()).add((digest, start, end))
        if os.fsdecode(git('rev-parse', '--show-toplevel')).strip() != str(root):
            raise ValueError('root must be repository root')
        base = git('rev-parse', '--verify', '--end-of-options', base_ref + '^{commit}').decode().strip()
        index_rows = paths(git('ls-files', '--stage', '-z'))
        index_blobs = {}
        for row in index_rows:
            metadata, path = row.split('\t', 1)
            mode, oid, stage = metadata.split()
            if stage != '0':
                raise ValueError('unmerged index')
            index_blobs[path] = oid
        tracked = list(index_blobs)
        staged = paths(git('diff', '--cached', '--name-only', '-z', '--no-ext-diff'))
        unstaged = paths(git('diff', '--name-only', '-z', '--no-ext-diff'))
        untracked = paths(git('ls-files', '--others', '--exclude-standard', '-z'))
        inventory = {'tracked': tracked, 'staged': staged, 'unstaged': unstaged, 'untracked': untracked}
        def redact_path(path):
            raw = os.fsencode(path)
            for pattern in PATTERNS:
                raw = pattern.sub(b'[REDACTED]', raw)
            return os.fsdecode(raw)
        for name, values in inventory.items():
            result['inventory'][name] = [redact_path(p) for p in values]
        candidates = sorted(set(tracked + untracked))
        result['inventory']['categories'] = {category: sum(1 for p in candidates if predicate(p)) for category, predicate in {
            'source': lambda p: p.endswith(('.py', '.js', '.ts', '.sh')),
            'schema': lambda p: 'schema' in p.lower(),
            'docs': lambda p: p.endswith('.md'),
            'projections': lambda p: p.startswith(('.cursor/agents/', '.claude/agents/', '.github/agents/')),
        }.items()}
        blob_cache = OrderedDict()
        cache_size = 0
        def blob(oid):
            nonlocal cache_size
            if oid in blob_cache:
                blob_cache.move_to_end(oid)
                return blob_cache[oid]
            data = git('cat-file', 'blob', oid)
            while blob_cache and cache_size + len(data) > 32 * 1024 * 1024:
                _, removed = blob_cache.popitem(last=False)
                cache_size -= len(removed)
            blob_cache[oid] = data
            cache_size += len(data)
            return data
        for path in tracked:
            if result['scanned_bytes'] > MAX_TOTAL_BYTES or len(result['findings']) >= 1000:
                raise ValueError('limit')
            if _runtime(path):
                finding('tracked-runtime', 'index', path)
            try:
                scan(blob(index_blobs[path]), 'index', path)
            except (ValueError, OSError, subprocess.SubprocessError):
                incomplete('index', path)
        for path in candidates:
            if result['scanned_bytes'] > MAX_TOTAL_BYTES or len(result['findings']) >= 1000:
                raise ValueError('limit')
            try:
                data = safe_file(path)
                if data is not None:
                    scan(data, 'working-tree', path)
            except (ValueError, OSError):
                incomplete('working-tree', path)
        commits = git('rev-list', '--max-count=' + str(MAX_COMMITS + 1), base + '..HEAD').decode().splitlines()
        if len(commits) > MAX_COMMITS:
            raise ValueError('history limit')
        for commit in commits:
            scan(git('cat-file', 'commit', commit), 'history-metadata', 'commit:' + commit, allow_fixtures=False)
            tree = {}
            for row in paths(git('ls-tree', '-r', '-z', commit)):
                metadata, path = row.split('\t', 1)
                mode, kind, oid = metadata.split()
                tree[path] = (kind, oid)
            for path in paths(git('diff-tree', '--root', '-m', '--no-commit-id', '--name-only', '-r', '-z', commit)):
                # Deleted files were scanned in the commit that introduced them.
                if path not in tree:
                    continue
                kind, oid = tree[path]
                if _runtime(path):
                    finding('tracked-runtime', 'history', path)
                if kind != 'blob':
                    incomplete('history', path)
                    continue
                scan(blob(oid), 'history', path)
    except (ValueError, OSError, subprocess.SubprocessError, TypeError, KeyError, AttributeError):
        incomplete('repository')
    result['ok'] = result['complete'] and not any(f['status'] == 'blocking' for f in result['findings'])
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='origin/main')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--fixture-manifest', help='Root-relative reviewed exact byte spans and whole-file SHA-256 manifest')
    args = parser.parse_args(argv)
    result = release_preflight(Path.cwd(), args.base, fixture_manifest=args.fixture_manifest)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print('Publication preflight: ' + ('PASS' if result['ok'] else 'BLOCKED'))
        print('Complete: ' + str(result['complete']))
        for item in result['findings']:
            print(json.dumps(item))
    return 0 if result['ok'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
