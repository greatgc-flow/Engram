"""CLI regressions runnable with unittest (no pytest runner required)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from conftest import scratch_dir
from _sys.core.root import find_root

REPO = find_root(__file__).parent


@unittest.skipUnless(os.name == 'nt', 'Windows batch entry point')
class CliCorrectness(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(scratch_dir())
        shutil.copy(REPO / 'engram.cmd', self.root)
        core = self.root / '_sys/core'
        core.mkdir(parents=True)
        shutil.copytree(REPO / '_sys/core/help', core / 'help')
        py = self.root / '_sys/env/python/python.exe'
        py.parent.mkdir(parents=True)
        shutil.copy(r'C:\Windows\System32\find.exe', py)
        state = self.root / '_sys/data/state'
        state.mkdir(parents=True)
        (state / 'layout.json').write_text('{"layout_version":2}')
        self.harness = self.root / 'harness.py'
        self.harness.write_text('''import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, os.environ['C1_REPO'] + '/_sys')
from core import dispatcher, repair, launcher, backups
root = Path(__file__).parent
mode = os.environ.get('C1_MODE', 'echo')
if mode == 'echo':
    print(json.dumps(sys.argv[1:])); sys.exit(7)
dispatcher.sys_dir = Path(os.environ['C1_REPO']) / '_sys'
ctx = {'base_dir': root, 'sys_dir': root / '_sys', 'args': sys.argv[2:], 'command': sys.argv[1], 'paths': {}, 'state': {}}
if mode == 'launcher':
    with patch.object(dispatcher, '_build_ctx', return_value=ctx), patch.object(launcher, 'build_env', return_value=dict(os.environ)), patch.object(launcher.provisioner, 'portable_python_exe', return_value=Path(sys.executable)):
        sys.exit(dispatcher.main(['dispatcher.py', *sys.argv[1:]]))
elif mode == 'snapshot':
    ref = backups.BackupRef('python', root / 'python-backup', {})
    with patch.object(dispatcher, '_build_ctx', return_value=ctx), patch.object(backups, '_resolve', return_value=(ref, None)):
        sys.exit(dispatcher.main(['dispatcher.py', *sys.argv[1:]]))
else:
    detection = {'journal': None, 'drift': {}, 'findings': [], 'manifest': 'ok'}
    plan = {'steps': [], 'spec': [], 'summary': [], 'kind': 'repair'}
    case = os.environ.get('C1_CASE', '')
    if case in ('apply', 'decline', 'user-decline', 'failed-apply'):
        plan['steps'] = [repair.env_ops.Step('test', lambda c: None, group='A')]
    if case == 'user-decline':
        sys.stdin = type('Terminal', (), {'isatty': lambda self: True})()
        ctx['seams'] = {'input_fn': lambda prompt: 'n'}
    if case in ('active', 'resume', 'rollback'):
        detection['journal'] = {'op_id': 'test-op', 'data': {'spec': []}}
    result = {'status': 'success', 'phase': 'COMMITTED', 'op_id': 'test-op'}
    if case == 'rollback': result['phase'] = 'ROLLED_BACK'
    if case == 'failed-apply': result.update(status='failed', phase='ROLLED_BACK', detail='verification failed')
    with patch.object(repair, 'detect', return_value=detection), patch.object(repair, 'build_plan', return_value=plan), patch.object(dispatcher, '_build_ctx', return_value=ctx), patch.object(repair.env_ops, 'execute', return_value=result), patch.object(repair.env_ops, 'resume', return_value=result), patch.object(repair.env_ops, 'rollback', return_value=result):
        sys.exit(dispatcher.main(['dispatcher.py', *sys.argv[1:]]))
''')
        (core / 'dispatch.bat').write_text(f'@echo off\n"{sys.executable}" "{self.harness}" %*\nexit /b %errorlevel%\n')
        self.env = dict(os.environ, C1_REPO=str(REPO))

    def run_cli(self, args, mode='echo', cwd=None, case=''):
        env = dict(self.env, C1_MODE=mode, C1_CASE=case)
        return subprocess.run(f'cmd.exe /d /s /c ""{self.root / "engram.cmd"}" {args}"', cwd=cwd or self.root, env=env, capture_output=True, text=True)

    def test_forwarding_without_ceiling(self):
        tokens = ['one two', 'a&b', 'a|b', 'a<b', 'a>b', 'a^b', 'a!b', 'a%b', 'nine', 'ten', 'say "hello"']
        proc = self.run_cli('doctor ' + ' '.join('"' + s.replace('"', '\\"') + '"' for s in tokens))
        self.assertEqual(proc.returncode, 7, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout), ['doctor', *tokens])

    def test_no_implicit_path(self):
        (self.root / 'folder').mkdir()
        self.assertEqual(self.run_cli('folder').returncode, 2)

    def test_no_auto_migration(self):
        (self.root / '_sys/data/state/layout.json').unlink()
        for args in ('doctor', 'menu status', 'tidy --dry-run', 'repair --dry-run',
                     'relocate --dry-run', 'snapshots list'):
            proc = self.run_cli(args)
            self.assertEqual(proc.returncode, 7, proc.stdout)
            self.assertEqual(json.loads(proc.stdout), args.split())
            self.assertFalse((self.root / '_sys/data/state/layout.json').exists())

    def test_menu_extras(self):
        for action in ('status', 'enable', 'disable', 'clean'):
            self.assertEqual(self.run_cli(f'menu {action} extra', 'engine').returncode, 2)

    def test_info_extras(self):
        for args in ('version extra', '--version extra', 'help open extra', '--help extra', 'version --help extra'):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(args).returncode, 2)

    def test_recovery_json_and_usage(self):
        for verb in ('repair', 'relocate'):
            for mode in ('--resume', '--rollback'):
                proc = self.run_cli(f'{verb} {mode} --json', 'engine')
                self.assertEqual(proc.returncode, 11, proc.stdout + proc.stderr)
                self.assertEqual(json.loads(proc.stdout)['exit_code'], 11)
            for flags in ('--only bogus', '--only ""', '--resume --rollback'):
                proc = self.run_cli(f'{verb} {flags}', 'engine')
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_launcher_child_status(self):
        for suffix, source in (('.py', 'raise SystemExit(23)'), ('.cmd', '@echo off\nexit /b 23\n')):
            child = self.root / ('child' + suffix)
            child.write_text(source)
            proc = self.run_cli('open "' + str(child) + '"', 'launcher')
            self.assertEqual(proc.returncode, 23, proc.stdout + proc.stderr)

    def test_launcher_child_receives_all_arguments(self):
        tokens = ['one two', 'a&b', 'a|b', 'a<b', 'a>b', 'a^b', 'a!b', 'a%b', 'nine', 'ten', 'say "hello"']
        output = self.root / 'child-args.json'
        receiver = self.root / 'receive.py'
        receiver.write_text('import json, sys\nfrom pathlib import Path\nPath(' + repr(str(output)) + ').write_text(json.dumps(sys.argv[1:]))\n')
        batch = self.root / 'child with space.cmd'
        batch.write_text('@echo off\n"' + sys.executable + '" "' + str(receiver) + '" %*\n')
        for child in (receiver, batch):
            if output.exists(): output.unlink()
            args = ' '.join('"' + token.replace('"', '\\"') + '"' for token in tokens)
            proc = self.run_cli('open "' + str(child) + '" ' + args, 'launcher')
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(output.read_text()), tokens)

    def test_explicit_relative_open_and_default(self):
        caller = self.root / 'caller'
        caller.mkdir()
        (caller / 'child.py').write_text('raise SystemExit(24)')
        proc = self.run_cli('open child.py', 'launcher', cwd=caller)
        self.assertEqual(proc.returncode, 24, proc.stdout + proc.stderr)
        proc = self.run_cli('')
        self.assertEqual(json.loads(proc.stdout), ['start'])

    def test_json_all_engine_modes(self):
        modes = [('', '', 0), ('--dry-run', '', 0), ('--apply --yes', 'apply', 0),
                 ('--apply', 'decline', 11), ('--apply', 'user-decline', 10),
                 ('--apply --yes', 'failed-apply', 12),
                 ('', 'active', 14), ('--resume', 'resume', 0),
                 ('--rollback', 'rollback', 0), ('--only bogus', '', 2),
                 ('--resume --rollback', '', 2)]
        for verb in ('repair', 'relocate'):
            for flags, case, code in modes:
                with self.subTest(verb=verb, flags=flags, case=case):
                    proc = self.run_cli(f'{verb} {flags} --json', 'engine', case=case)
                    self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
                    self.assertEqual(json.loads(proc.stdout)['exit_code'], code)

    def test_snapshot_guidance(self):
        proc = self.run_cli('snapshots restore python-backup', 'snapshot')
        self.assertEqual(proc.returncode, 11, proc.stdout + proc.stderr)
        self.assertIn('not supported', proc.stdout)
        self.assertNotIn("restored through 'engram repair'", proc.stdout)


if __name__ == '__main__':
    unittest.main()
