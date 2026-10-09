"""Wave A1 regressions through the fault-injection real dispatcher entry.
Run directly with Python; no pytest runner or system temp directory required.
All CX-001..007 were RED against the original implementation: lost credentials,
accepted --all, missing extras snapshot, copied nested secrets, junction write,
missing committed WAL table, and deleted old archive on failed replacement.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager, closing

@contextmanager
def fixture_tempdir():
    path = Path(tempfile.tempdir) / uuid.uuid4().hex
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)
from unittest.mock import patch

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS))
sys.path.insert(0, str(Path(__file__).parent))
from core import dispatcher
from checks import backup_personal_data as backup
from test_cli_fault_injection import _invoke


class WaveA1(unittest.TestCase):
    def setUp(self):
        scratch = SYS.parent / '.wave-a1'
        scratch.mkdir(exist_ok=True)
        self.root = scratch / uuid.uuid4().hex
        self.root.mkdir()
        self.sys = self.root / '_sys'
        (self.sys / 'config').mkdir(parents=True)
        (self.sys / 'config/environment.json').write_text(json.dumps({'paths': {'state': str(self.sys / 'data/state')}}))
        shutil.copy2(SYS / 'dispatch.json', self.sys / 'dispatch.json')
        self.patches = [patch.object(dispatcher, 'base_dir', self.root), patch.object(dispatcher, 'sys_dir', self.sys), patch.object(backup, 'check_running_processes', lambda _: []), patch.object(tempfile, 'tempdir', str(self.root)), patch.object(tempfile, 'TemporaryDirectory', fixture_tempdir)]
        for p in self.patches:
            p.start()
        self.addCleanup(shutil.rmtree, self.root)
        for p in self.patches:
            self.addCleanup(p.stop)

    def write(self, rel, data=b'old'):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_CX001_reset_preserves_uncovered_and_credentials(self):
        covered = self.write('.engram/claude/settings.json')
        secret = self.write('.engram/codex/auth.json')
        uncovered = self.write('.engram/custom.bin')
        nested = self.write('.peerhub/secrets.key')
        self.write('.peerhub/state.txt')
        self.assertEqual(_invoke('reset', '--apply', '--yes'), 0)
        self.assertFalse(covered.exists())
        for p in (secret, uncovered, nested):
            self.assertEqual(p.read_bytes(), b'old')

    def test_CX002_reset_all_is_usage_error(self):
        project = self.write('workspace/project.txt')
        with patch('builtins.input', return_value=self.root.name):
            self.assertEqual(_invoke('reset', '--apply', '--yes', '--all'), 2)
        self.assertTrue(project.exists())

    def test_CX003_snapshot_covers_only_restore_destinations_including_extras(self):
        self.write('.peerhub/state.txt')
        self.write('.peerhub/untouched.txt')
        self.write('.engram/codex/CODEX.md', b'untouched')
        bundle = self.root / 'bundle'
        self.write('bundle/custom_extras/.peerhub/state.txt', b'new')
        self.write('bundle/MANIFEST.json', json.dumps({'custom_extras': [{'relpath': '.peerhub', 'kind': 'dir'}]}).encode())
        self.assertEqual(_invoke('restore', bundle, '--apply'), 0)
        snaps = list((self.sys / 'data/backups').glob('pre_restore_*.zip'))
        self.assertEqual(len(snaps), 1)
        import zipfile
        with zipfile.ZipFile(snaps[0]) as z:
            self.assertEqual(z.read('custom_extras/.peerhub/state.txt'), b'old')
            self.assertNotIn('codex/CODEX.md', z.namelist())
            self.assertNotIn('custom_extras/.peerhub/untouched.txt', z.namelist())

    def test_CX004_all_copy_paths_filter_nested_secrets(self):
        self.write('.engram/codex/skills/nested/auth.json')
        self.write('.peerhub/nested/.env')
        out = self.root / 'backup.zip'
        self.assertEqual(_invoke('backup', '--out', out, '--include-uncovered'), 0)
        import zipfile
        with zipfile.ZipFile(out) as z:
            self.assertFalse(any(n.endswith(('auth.json', '.env')) for n in z.namelist()))
        plain = self.root / 'plain'
        self.assertEqual(backup.main(['--base-dir', str(self.root), '--backup', '--out', str(plain)]), 0)
        self.assertFalse((plain / 'codex/skills/nested/auth.json').exists())
        self.write('bundle/custom_extras/.peerhub/nested/hosts.yml')
        self.write('bundle/MANIFEST.json', json.dumps({'custom_extras': [{'relpath': '.peerhub', 'kind': 'dir'}]}).encode())
        self.write('bundle/codex/skills/nested/token.json')
        self.assertEqual(_invoke('restore', self.root / 'bundle', '--apply', '--force'), 0)
        self.assertFalse((self.root / '.engram/codex/skills/nested/token.json').exists())
        self.assertFalse((self.root / '.peerhub/nested/hosts.yml').exists())

    def test_CX005_standard_destination_reparse_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / '.engram').mkdir()
        import subprocess
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root / '.engram/codex'), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.addCleanup(lambda: os.rmdir(self.root / '.engram/codex') if (self.root / '.engram/codex').exists() else None)
        self.write('bundle/codex/CODEX.md', b'new')
        self.assertNotEqual(_invoke('restore', self.root / 'bundle', '--apply', '--force'), 0)
        self.assertFalse((outside / 'CODEX.md').exists())
        self.assertNotEqual(_invoke('backup', '--out', self.root / 'backup.zip'), 0)
        os.rmdir(self.root / '.engram/codex')
        (self.root / 'bundle/codex/skills').mkdir()
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root / 'bundle/codex/skills/link'), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.addCleanup(lambda: os.rmdir(self.root / 'bundle/codex/skills/link'))
        self.assertNotEqual(_invoke('restore', self.root / 'bundle', '--apply', '--force'), 0)

    def test_CX006_sqlite_backup_includes_committed_wal(self):
        db = self.root / '.engram/codex/memories_1.sqlite'
        db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA wal_autocheckpoint=0')
            conn.execute('CREATE TABLE memory (value TEXT)')
            conn.execute("INSERT INTO memory VALUES ('committed')")
            conn.commit()
            out = self.root / 'backup.zip'
            self.assertEqual(_invoke('backup', '--out', out), 0)
            import zipfile
            with zipfile.ZipFile(out) as z:
                z.extract('codex/memories_1.sqlite', self.root / 'check')
            with closing(sqlite3.connect(self.root / 'check/codex/memories_1.sqlite')) as saved:
                self.assertEqual(saved.execute('SELECT value FROM memory').fetchall(), [('committed',)])

    def test_CX007_failed_replace_preserves_existing_archive(self):
        out = self.write('backup.zip', b'previous archive')
        self.write('.engram/claude/settings.json')
        def fail(*args, **kwargs):
            raise OSError('injected replace failure')
        with patch.object(Path, 'replace', fail), patch.object(os, 'replace', fail):
            self.assertNotEqual(_invoke('backup', '--out', out), 0)
        self.assertEqual(out.read_bytes(), b'previous archive')


if __name__ == '__main__':
    unittest.main()
