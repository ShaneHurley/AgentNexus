import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from agent_core.release_preflight import release_preflight

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.root / 'base.txt').write_text('base')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)
    def scan(self):
        return release_preflight(self.root, self.base)
    def test_clean_and_inventory(self):
        result = self.scan()
        self.assertTrue(result['ok'])
        self.assertEqual(result['inventory']['tracked'], ['base.txt'])
    def test_all_candidate_layers_and_redaction(self):
        secret = 'sk-' + 'a' * 40
        (self.root / 'base.txt').write_text(secret)
        self.git('add', 'base.txt')
        (self.root / 'base.txt').write_text('clean')
        (self.root / 'untracked.py').write_text(secret)
        (self.root / '.gitignore').write_text('ignored\n')
        (self.root / 'ignored').write_text(secret)
        result = self.scan()
        self.assertFalse(result['ok'])
        self.assertNotIn(secret, json.dumps(result))
        self.assertIn('base.txt', result['inventory']['staged'])
        self.assertIn('base.txt', result['inventory']['unstaged'])
        self.assertNotIn('ignored', result['inventory']['untracked'])
        self.assertTrue(any(f['layer'] == 'index' for f in result['findings']))
    def test_deleted_history_secret_blocks(self):
        (self.root / 'old.py').write_text('sk-' + 'b' * 40)
        self.git('add', '.')
        self.git('commit', '-qm', 'secret')
        self.git('rm', '-q', 'old.py')
        self.git('commit', '-qm', 'remove')
        self.assertTrue(any(f['layer'] == 'history' for f in self.scan()['findings']))
    def test_runtime_and_symlink_are_blocking(self):
        (self.root / '.env').write_text('LOCAL=1')
        self.git('add', '-f', '.env')
        (self.root / 'escape').symlink_to('/etc/passwd')
        result = self.scan()
        self.assertFalse(result['ok'])
        self.assertFalse(result['complete'])
        self.assertTrue(any(f['kind'] == 'tracked-runtime' for f in result['findings']))
    def test_missing_base_fails_closed(self):
        result = release_preflight(self.root, 'missing-ref')
        self.assertFalse(result['complete'])
        self.assertFalse(result['ok'])
    def test_tests_are_not_exempt(self):
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_fake.py').write_text('sk-' + 'c' * 40)
        result = self.scan()
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['kind'] == 'secret' for f in result['findings']))

    def test_fixture_manifest_exact_spans_and_hash(self):
        import hashlib
        payload = ('sk-' + 'd' * 40).encode()
        (self.root / 'fixture.py').write_bytes(payload)
        manifest = {'version': 1, 'fixtures': [{'path': 'fixture.py', 'sha256': hashlib.sha256(payload).hexdigest(), 'spans': [{'start': 0, 'end': len(payload)}]}]}
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        result = release_preflight(self.root, self.base, fixture_manifest='manifest.json')
        self.assertTrue(result['ok'])
        self.assertEqual(result['findings'][0]['status'], 'reviewed')
        (self.root / 'fixture.py').write_bytes(payload + b'changed')
        self.assertFalse(release_preflight(self.root, self.base, fixture_manifest='manifest.json')['ok'])
    def test_manifest_escape_and_file_limit_fail_closed(self):
        from unittest.mock import patch
        self.assertFalse(release_preflight(self.root, self.base, fixture_manifest='../outside.json')['complete'])
        (self.root / 'big.py').write_text('x' * 1024)
        with patch('agent_core.release_preflight.MAX_BYTES', 100):
            result = self.scan()
        self.assertFalse(result['complete'])
        self.assertFalse(result['ok'])

    def test_deleted_runtime_history_blocks(self):
        (self.root / 'state.sqlite').write_text('runtime')
        self.git('add', '.')
        self.git('commit', '-qm', 'runtime')
        self.git('rm', '-q', 'state.sqlite')
        self.git('commit', '-qm', 'remove')
        result = self.scan()
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['kind'] == 'tracked-runtime' and f['layer'] == 'history' for f in result['findings']))

    def test_commit_message_credentials_block_and_cannot_be_fixtures(self):
        import hashlib
        secret = 'sk-' + 'm' * 40
        self.git('commit', '--allow-empty', '-qm', secret)
        commit = self.git('rev-parse', 'HEAD').strip()
        raw = subprocess.check_output(['git', '-C', str(self.root), 'cat-file', 'commit', commit])
        start = raw.index(secret.encode())
        manifest = {'version': 1, 'fixtures': [{'path': 'commit:' + commit, 'sha256': hashlib.sha256(raw).hexdigest(), 'spans': [{'start': start, 'end': start + len(secret)}]}]}
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        result = release_preflight(self.root, self.base, fixture_manifest='manifest.json')
        self.assertFalse(result['ok'])
        self.assertTrue(result['complete'])
        findings = [f for f in result['findings'] if f['layer'] == 'history-metadata']
        self.assertTrue(findings)
        self.assertTrue(all(f['status'] == 'blocking' for f in findings))
        self.assertNotIn(secret, json.dumps(result))
