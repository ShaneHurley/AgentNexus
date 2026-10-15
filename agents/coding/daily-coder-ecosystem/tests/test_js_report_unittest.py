"""Standard-library checks for bound JavaScript report evidence."""
import importlib.util
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'verification_evidence',
    Path(__file__).resolve().parents[1] / 'daily_coder' / 'verification_evidence.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(runner='jest'):
    report = dict(version=1, runner=runner, execution_nonce='nonce-1',
                  source_snapshot_sha256='ab' * 32, passed=3, failed=0,
                  skipped=0, interrupted=0)
    result = dict(expected_runner=runner, execution_nonce='nonce-1',
                  source_snapshot_sha256='ab' * 32, returncode=0,
                  js_report=json.dumps(report))
    return report, result


class JavaScriptReports(unittest.TestCase):
    def check_report(self, report, result, positive=False, argv=None):
        result = dict(result, js_report=json.dumps(report))
        evidence = MODULE.execution_evidence(argv or ['jest'], result)
        self.assertEqual(evidence['positive'], positive)
        self.assertTrue(evidence['recognized'])
        if positive:
            self.assertEqual(evidence['executed_tests'], report['passed'])
            self.assertEqual(evidence['skipped_tests'], report['skipped'])
            self.assertEqual(evidence['runner'], report['runner'])

    def test_commands_and_positive_reports(self):
        cases = [(['node', '--test'], 'node-test'),
                 (['node.exe', '--experimental-foo', '--test'], 'node-test')]
        for executable in ('npm', 'npm.cmd', 'npm.exe'):
            for alias in ('test', 't', 'tst'):
                for prefix in ([], ['run'], ['run-script']):
                    cases.append(([executable] + prefix + [alias], 'npm-test'))
        for runner in ('jest', 'vitest', 'playwright'):
            tail = ['test'] if runner == 'playwright' else []
            for suffix in ('', '.cmd', '.exe'):
                cases.append(([runner + suffix] + tail, runner))
            for npx in ('npx', 'npx.cmd', 'npx.exe'):
                for flags in ([], ['--yes'], ['-y'], ['--no-install'],
                              ['--'], ['--yes', '--no-install', '--']):
                    cases.append(([npx] + flags + [runner] + tail, runner))
        for argv, runner in cases:
            for path_prefix in ('', '/usr/local/bin/'):
                command = [path_prefix + argv[0]] + argv[1:]
                with self.subTest(command=command):
                    self.assertEqual(MODULE.runner_for(command), runner)
                    for skipped in (0, 2):
                        report, result = fixture(runner)
                        report['skipped'] = skipped
                        self.check_report(report, result, True, command)
                    result.pop('js_report')
                    result.update(stdout='3 passed in 0.1s', stderr='Ran 3 tests in 0.1s\nOK')
                    self.assertFalse(MODULE.execution_evidence(command, result)['positive'])

    def test_unrecognized_commands(self):
        for argv in ([], 'jest', ['node', 'script.js'], ['node', '--', '--test'],
                     ['npm', 'run', 'contest'], ['npm', 'install', 'test'],
                     ['playwright'], ['playwright', 'show-report'],
                     ['echo', 'jest'], ['npx', 'other', 'jest']):
            with self.subTest(argv=argv):
                self.assertIsNone(MODULE.runner_for(argv))
                _, result = fixture()
                self.assertEqual(MODULE.execution_evidence(argv, result),
                    dict(runner=None, recognized=False, executed_tests=None,
                         skipped_tests=None, positive=True,
                         reason='Explicit assertion command uses recorded argv and exit status'))

    def test_json_rejections(self):
        report, result = fixture()
        raw = json.dumps(report)
        invalid = ['', '{', raw + '{}', 'null', '[]', '1', 'true', '"text"',
                   None, True, 1, [], {},
                   raw[:-1] + ', "passed": 3}',
                   raw[:-1] + ', "extra": 1, "extra": 2}']
        for constant in ('NaN', 'Infinity', '-Infinity'):
            invalid.append(raw.replace('"passed": 3', '"passed": ' + constant))
        for value in invalid:
            with self.subTest(value=value):
                self.assertFalse(MODULE.execution_evidence(
                    ['jest'], dict(result, js_report=value))['positive'])
        for key in report:
            modified = dict(report)
            del modified[key]
            with self.subTest(missing=key):
                self.check_report(modified, result)
        self.check_report(dict(report, extra=1), result)

    def test_schema_rejections(self):
        report, result = fixture()
        for value in (True, False, 0, 2, -1, 1.0, '1', None, [], {}):
            with self.subTest(version=value):
                self.check_report(dict(report, version=value), result)
        for field in ('passed', 'failed', 'skipped', 'interrupted'):
            for value in (-1, True, False, 1.0, '1', None, [], {}):
                with self.subTest(field=field, value=value):
                    self.check_report(dict(report, **{field: value}), result)

    def test_bindings(self):
        report, result = fixture()
        fields = {
            'runner': (None, True, 1, [], {}, '', 'other', 'vitest'),
            'execution_nonce': (None, True, 1, [], {}, '', '   ', 'nonce-2'),
            'source_snapshot_sha256': (None, True, 1, [], {}, '', 'a' * 63,
                                       'a' * 65, 'z' * 64, 'cd' * 32, 'AB' * 32)}
        for field, values in fields.items():
            metadata = 'expected_runner' if field == 'runner' else field
            for value in values:
                with self.subTest(field=field, value=value):
                    self.check_report(dict(report, **{field: value}), result)
                    self.check_report(report, dict(result, **{metadata: value}))
                    self.check_report(dict(report, **{field: value}),
                                      dict(result, **{metadata: value})) if value not in ('vitest', 'nonce-2', 'cd' * 32, 'AB' * 32) else None
            modified = dict(result)
            del modified[metadata]
            self.check_report(report, modified)
        changed = dict(report, runner='vitest')
        self.check_report(changed, dict(result, expected_runner='vitest'))
        for nonce in (' nonce ', 'nonce-1 '):
            self.check_report(dict(report, execution_nonce=nonce), result)
        self.check_report(dict(report, execution_nonce=' nonce '),
                          dict(result, execution_nonce=' nonce '), True)
        self.check_report(dict(report, source_snapshot_sha256='AB' * 32),
                          dict(result, source_snapshot_sha256='AB' * 32), True)

    def test_unsuccessful_execution(self):
        report, result = fixture()
        for changes in (dict(passed=0), dict(passed=0, skipped=4),
                        dict(failed=1), dict(interrupted=1),
                        dict(passed=0, failed=1), dict(passed=0, interrupted=1)):
            with self.subTest(changes=changes):
                self.check_report(dict(report, **changes), result)
        for value in (-1, 1, True, False, 0.0, '0', None, [], {}):
            with self.subTest(returncode=value):
                self.check_report(report, dict(result, returncode=value))
        missing = dict(result)
        del missing['returncode']
        self.check_report(report, missing)
        for flag in ('timeout', 'timed_out', 'cancelled'):
            for value in (True, 1, 'yes', [1], {'x': 1}):
                self.check_report(report, dict(result, **{flag: value}))
            for value in (False, 0, '', None):
                self.check_report(report, dict(result, **{flag: value}), True)


class PythonCompatibility(unittest.TestCase):
    def test_legacy_summaries(self):
        absent = 'Recognized test runner has no unambiguous positive execution summary'
        cases = [
            ('unittest', 'Ran 3 tests in 0.1s\nOK', 3, 0),
            ('unittest', 'Ran 3 tests in 0.1s\nOK (skipped=1)', 2, 1),
            ('unittest', 'Ran 2 tests in 0.1s\nOK (skipped=2)', 0, 2),
            ('unittest', 'Ran 0 tests in 0.1s\nOK', 0, 0),
            ('unittest', 'OK', None, None),
            ('unittest', 'Ran 1 test in 0.1s\nOK\nOK', None, None),
            ('pytest', '=== 3 passed, 1 skipped in 0.1s ===', 3, 1),
            ('pytest', '\x1b[32m3 passed in 0.1s\x1b[0m', 3, 0),
            ('pytest', '2 skipped in 0.1s', 0, 2),
            ('pytest', 'no tests ran in 0.1s', 0, 0),
            ('pytest', 'no tests collected', 0, 0),
            ('pytest', '1 passed, 1 failed in 0.1s', None, None),
            ('pytest', '1 passed, 1 error in 0.1s', None, None),
            ('pytest', '1 passed, 2 passed in 0.1s', None, None),
            ('pytest', '1 passed in 0.1s\n2 passed in 0.1s', None, None),
            ('pytest', '', None, None)]
        for runner, text, executed, skipped in cases:
            commands = ([['python', '-m', 'unittest'], ['/usr/bin/python3', '-m', 'unittest']]
                        if runner == 'unittest' else
                        [['pytest'], ['py.test'], ['python', '-m', 'pytest'], ['/usr/bin/pytest']])
            for argv in commands:
                for stream in ('stdout', 'stderr'):
                    with self.subTest(argv=argv, text=text, stream=stream):
                        reason = (absent if executed is None else
                                  'Positive executed-test summary' if executed > 0 else
                                  'No non-skipped tests executed')
                        result = {stream: text, 'returncode': 9, 'timeout': True,
                                  'timed_out': True, 'cancelled': True,
                                  'js_report': '{}', 'expected_runner': 'jest'}
                        self.assertEqual(MODULE.execution_evidence(argv, result),
                            dict(runner=runner, recognized=True, executed_tests=executed,
                                 skipped_tests=skipped, positive=executed is not None and executed > 0,
                                 reason=reason))


if __name__ == '__main__':
    unittest.main()
