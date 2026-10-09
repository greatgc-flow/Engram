from contextlib import contextmanager
import uuid
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
import subprocess
import pytest
from evidence_fixtures import evidence_fixture
from unittest.mock import patch
import zipfile
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/release_gate'))
import importlib.util
_spec = importlib.util.spec_from_file_location('winget_gate_checks', ROOT / '_sys/checks/release_evidence.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
import winget_smoke as smoke

@contextmanager
def temporary_directory(**kwargs):
    directory = ROOT / '_sys/tests/unit' / ('winget-fixture-' + uuid.uuid4().hex)
    directory.mkdir(mode=511)
    try:
        yield str(directory)
    finally:
        shutil.rmtree(directory)

class TestRequiredEvidence:

    def test_missing_winget_is_hold(self):
        with pytest.raises(gate.Hold, match='WinGet evidence is required'):
            gate.verify('missing', 'missing', 'upgrade.json')

    def test_evidence_contract(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            hashes = {'release.zip': 'a' * 64}
            candidate = root / 'candidate.json'
            sandbox = root / 'sandbox.json'
            winget = root / 'winget.json'
            candidate.write_text(json.dumps({'tag': 'v1.2.3', 'commit': 'b' * 40, 'candidate_sha256s': hashes}))
            sandbox.write_text(json.dumps({'status': 'PASS', 'candidate_sha256s': hashes,
                'provider': 'windows-sandbox', 'runner_environment': 'self-hosted',
                'workflow_run_id': '12', 'image': 'Windows 11', 'cancelled': False, 'skipped': False, 'run_id': '12', 'run_attempt': '1'}))
            good = {'status': 'PASS', 'candidate_sha256s': hashes, 'cancelled': False, 'skipped': False, 'run_id': '12', 'run_attempt': '1'}
            with patch.dict(os.environ, {'GITHUB_RUN_ID': '12', 'GITHUB_RUN_ATTEMPT': '1'}):
                for change in ({}, {'status': 'HOLD'}, {'status': 'SKIPPED'}, {'skipped': True}, {'cancelled': True}, {'skipped': None}, {'candidate_sha256s': {'release.zip': 'c' * 64}}, {'run_attempt': '2'}):
                    winget.write_text(json.dumps(dict(good, **change)))
                    if change:
                        with pytest.raises(gate.Hold):
                            gate.verify(candidate, sandbox, run_id="12", run_attempt="1", winget_evidence_path=winget, upgrade_evidence_path=evidence_fixture(candidate, "upgrade"))
                    else:
                        gate.verify(candidate, sandbox, run_id="12", run_attempt="1", winget_evidence_path=winget, upgrade_evidence_path=evidence_fixture(candidate, "upgrade"))
                winget.unlink()
                with pytest.raises(gate.Hold):
                    gate.verify(candidate, sandbox, run_id="12", run_attempt="1", winget_evidence_path=winget, upgrade_evidence_path=evidence_fixture(candidate, "upgrade"))
                gate.verify(candidate, sandbox, run_id="12", run_attempt="1", upgrade_evidence_path=evidence_fixture(candidate, "upgrade"), winget_evidence_path=evidence_fixture(candidate, "winget"))
                with pytest.raises(gate.Hold):
                    gate.verify(candidate, sandbox, run_id="12", run_attempt="1", upgrade_evidence_path=evidence_fixture(candidate, "upgrade"))

class TestSmoke:

    def exercise(self, failure=None):
        with temporary_directory() as temporary:
            root = Path(temporary)
            assets = root / 'assets'
            manifests = assets / 'manifests'
            manifests.mkdir(parents=True)
            archive = assets / 'Engram-v1.2.3-portable-x64.zip'
            with zipfile.ZipFile(archive, 'w') as payload:
                payload.writestr('Engram.exe', b'candidate-executable')
                payload.writestr('engram.cmd', b'candidate-launcher')
                payload.writestr('_sys/core/version.json', b'{"version":"1.2.3"}')
            installer = manifests / 'greatgc-flow.Engram.installer.yaml'
            original = f'PackageIdentifier: greatgc-flow.Engram\nPackageVersion: 1.2.3\nInstallerUrl: https://github.com/unpublished.zip\nInstallerSha256: {smoke.digest(archive).upper()}\n'
            installer.write_text(original)
            candidate = {'tag': 'v1.2.3', 'commit': 'b' * 40, 'candidate_sha256s': smoke.snapshot(assets)}
            install = root / 'program'
            data = install / '.engram'
            local = root / 'local'
            alias = local / 'Microsoft/WinGet/Links/engram.exe'
            calls = []

            def stub(args):
                calls.append(args)
                operation = args[1]
                if failure == operation:
                    raise smoke.Hold('stub CLI failure')
                if failure == 'absent':
                    raise FileNotFoundError('winget absent')
                if operation == 'install':
                    copied = Path(args[args.index('--manifest') + 1]) / installer.name
                    rewritten = copied.read_text()
                    assert 'http://127.0.0.1:' in rewritten
                    assert rewritten.split('InstallerUrl:')[0] == original.split('InstallerUrl:')[0]
                    assert rewritten.split('InstallerSha256:')[1] == original.split('InstallerSha256:')[1]
                    with zipfile.ZipFile(archive) as payload:
                        payload.extractall(install)
                    alias.parent.mkdir(parents=True)
                    os.link(install / 'Engram.exe', alias)
                    if failure == 'files':
                        (install / 'engram.cmd').write_bytes(b'wrong')
                elif operation == 'uninstall':
                    assert '--manifest' in args and '--id' not in args and '--name' not in args
                    assert Path(args[args.index('--manifest') + 1]).is_dir()
                    assert '--accept-source-agreements' in args
                    assert '--purge' not in args and '--force' not in args
                    assert calls[-2][1] == 'list'
                    alias.unlink()
                    for path in list(install.iterdir()):
                        if path != data:
                            if path.is_dir():
                                shutil.rmtree(path)
                            else:
                                path.unlink()
                    if failure == 'data':
                        shutil.rmtree(data)
                    if failure == 'removal':
                        (install / 'Engram.exe').write_bytes(b'remains')
                elif args[0] == str(alias):
                    return 'Engram 9.9.9 (Portable Dev Runtime)' if failure == 'version' else 'Engram 1.2.3 (Portable Dev Runtime)'
                return ''
            with patch.dict(os.environ, {'LOCALAPPDATA': str(local)}), patch.object(smoke.tempfile, 'TemporaryDirectory', temporary_directory):
                if failure:
                    with pytest.raises((smoke.Hold, OSError)):
                        smoke.smoke(candidate, assets, install, data, run=stub)
                else:
                    smoke.smoke(candidate, assets, install, data, run=stub)
                    assert data.is_dir()
                    assert 'uninstall' in [c[1] for c in calls]
            assert installer.read_text() == original

    def test_success_and_frozen_manifest(self):
        self.exercise()

    def test_all_incomplete_checks_hold(self):
        for failure in ('absent', 'settings', 'install', 'files', 'version', 'uninstall', 'data', 'removal'):
            self.exercise(failure)

    def test_hash_mismatch_holds_before_cli(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            assets = root / 'assets'
            assets.mkdir()
            (assets / 'release.zip').write_bytes(b'changed')
            candidate = {'tag': 'v1.2.3', 'commit': 'b' * 40, 'candidate_sha256s': {'release.zip': 'a' * 64}}
            with pytest.raises(smoke.Hold, match='asset hashes differ'):
                smoke.smoke(candidate, assets, root / 'program', root / 'program/.engram', run=lambda args: pytest.fail('CLI must not run for mismatched assets'))

    def test_missing_candidate_emits_hold(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            out = root / 'evidence.json'
            result = smoke.main(['--candidate', str(root / 'missing'), '--assets', str(root / 'assets'), '--install-root', str(root / 'program'), '--user-data', str(root / 'program/.engram'), '--out', str(out)])
            assert result == 1
            assert json.loads(out.read_text())['status'] == 'HOLD'

    def test_hosted_gate_requires_evidence(self):
        workflow = (ROOT / '.github/workflows/sandbox-gate.yml').read_text()
        assert '  winget-smoke:' in workflow
        assert 'needs: [build-candidate, upgrade-gate, winget-smoke]' in workflow
        assert '--winget-evidence evidence/winget_evidence.json' in workflow
        assert '--no-winget-evidence' not in workflow
        assert '_sys/checks/release_evidence.py verify' in workflow

    def test_cli_failure_and_timeout(self):
        import subprocess
        with patch.object(smoke.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failed')):
            with pytest.raises(smoke.Hold):
                smoke.command(['winget', 'install'])
        with patch.object(smoke.subprocess, 'run', side_effect=subprocess.TimeoutExpired('winget', 300)):
            with pytest.raises(smoke.Hold, match='timed out'):
                smoke.command(['winget', 'install'])


class TestWingetDiagnostics(unittest.TestCase):
    def test_local_manifest_uninstall_and_preservation(self):
        TestSmoke().exercise()

    def test_each_failed_step_records_both_streams(self):
        for operation in ('install', 'list', 'uninstall'):
            with self.subTest(operation=operation):
                records = []
                result = subprocess.CompletedProcess([], 2316632134, 'source agreement required', 'stderr detail')
                with patch.object(smoke.subprocess, 'run', return_value=result):
                    with self.assertRaises(smoke.Hold) as caught:
                        smoke.command(['winget', operation], evidence=records)
                self.assertIn('0x8A150046', str(caught.exception))
                self.assertIn(result.stdout, str(caught.exception))
                self.assertIn(result.stderr, str(caught.exception))
                self.assertEqual(records[0]['returncode'], result.returncode)
                self.assertEqual(records[0]['stdout'], result.stdout)
                self.assertEqual(records[0]['stderr'], result.stderr)

    def test_empty_output_and_bounded_output(self):
        for stdout, stderr in (('', ''), ('x' * 10000, 'y' * 10000)):
            records = []
            with patch.object(smoke.subprocess, 'run', return_value=subprocess.CompletedProcess([], -1978335162, stdout, stderr)):
                with self.assertRaises(smoke.Hold) as caught:
                    smoke.command(['winget', 'uninstall'], evidence=records)
            self.assertIn('0x8A150046', str(caught.exception))
            self.assertLess(len(str(caught.exception)), 4500)
            self.assertLessEqual(len(records[0]['stdout']), 2060)
            self.assertLessEqual(len(records[0]['stderr']), 2060)
            if not stdout:
                self.assertIn("stdout=''; stderr=''", str(caught.exception))

    def test_successful_list_dump_and_timeout_output(self):
        records = []
        with patch.object(smoke.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'installed registration', 'warning')):
            self.assertEqual(smoke.command(['winget', 'list'], evidence=records), 'installed registration')
        self.assertEqual(records[0]['stderr'], 'warning')
        with patch.object(smoke.subprocess, 'run', side_effect=subprocess.TimeoutExpired('winget', 300, output=b'partial stdout', stderr=b'partial stderr')):
            with self.assertRaises(smoke.Hold) as caught:
                smoke.command(['winget', 'install'], evidence=records)
        self.assertIn('partial stdout', str(caught.exception))
        self.assertIn('partial stderr', str(caught.exception))
        self.assertTrue(records[-1]['timeout'])

    def test_main_retains_failure_evidence(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            candidate = root / 'candidate.json'
            candidate.write_text(json.dumps({'candidate_sha256s': {}}))
            out = root / 'evidence.json'
            def failed_smoke(*args, run):
                run(['winget', 'uninstall'])
            with patch.object(smoke, 'smoke', side_effect=failed_smoke), patch.object(smoke.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2316632134, 'agreement required', 'detail')):
                self.assertEqual(smoke.main(['--candidate', str(candidate), '--assets', str(root), '--install-root', str(root / 'program'), '--user-data', str(root / 'data'), '--out', str(out)]), 1)
            evidence = json.loads(out.read_text())
            self.assertEqual(evidence['status'], 'HOLD')
            self.assertEqual(evidence['commands'][0]['stdout'], 'agreement required')
            self.assertIn('detail', evidence['reason'])


@pytest.mark.parametrize("flag", ["cancelled", "skipped"])
@pytest.mark.parametrize("value", ["missing", None, True, 0, 1, "false"])
def test_winget_requires_explicit_false_flags(flag, value):
    with temporary_directory() as temporary:
        root = Path(temporary)
        hashes = {"release.zip": "a" * 64}
        candidate = root / "candidate.json"
        sandbox = root / "sandbox.json"
        winget = root / "winget.json"
        candidate.write_text(json.dumps({"tag": "v1.2.3", "commit": "b" * 40,
                                         "candidate_sha256s": hashes}))
        sandbox.write_text(json.dumps({"status": "PASS", "candidate_sha256s": hashes,
            "provider": "windows-sandbox", "runner_environment": "self-hosted",
            "workflow_run_id": "12", "image": "Windows 11", "cancelled": False, "skipped": False, "run_id": "12", "run_attempt": "1"}))
        evidence = {"status": "PASS", "candidate_sha256s": hashes,
                    "cancelled": False, "skipped": False}
        if value == "missing":
            del evidence[flag]
        else:
            evidence[flag] = value
        winget.write_text(json.dumps(evidence))
        with pytest.raises(gate.Hold, match=flag):
            gate.verify(candidate, sandbox, run_id="12", run_attempt="1", winget_evidence_path=winget,
                        upgrade_evidence_path=evidence_fixture(candidate, "upgrade"))


def test_winget_cli_required_and_removed_options(capsys):
    for removed in ("--no-upgrade-evidence", "--no-winget-evidence"):
        with pytest.raises(SystemExit) as exc:
            gate.main(["verify", "--run-id", "12", "--run-attempt", "1", "--candidate", "missing", "--evidence", "missing",
                       "--upgrade-evidence", "missing", "--winget-evidence", "missing", removed])
        assert exc.value.code == 2


@pytest.mark.parametrize("content", ["{", "[]", '{"status":"PASS","status":"HOLD"}'])
def test_winget_malformed_evidence_holds(content):
    with temporary_directory() as temporary:
        root = Path(temporary)
        hashes = {"release.zip": "a" * 64}
        candidate = root / "candidate.json"
        sandbox = root / "sandbox.json"
        winget = root / "winget.json"
        candidate.write_text(json.dumps({"tag": "v1.2.3", "commit": "b" * 40,
                                         "candidate_sha256s": hashes}))
        sandbox.write_text(json.dumps({"status": "PASS", "candidate_sha256s": hashes,
            "provider": "windows-sandbox", "runner_environment": "self-hosted",
            "workflow_run_id": "12", "image": "Windows 11", "cancelled": False, "skipped": False, "run_id": "12", "run_attempt": "1"}))
        winget.write_text(content)
        assert gate.main(["verify", "--run-id", "12", "--run-attempt", "1", "--candidate", str(candidate), "--evidence", str(sandbox),
                          "--upgrade-evidence", str(evidence_fixture(candidate, "upgrade")), "--winget-evidence", str(winget)]) == 1
