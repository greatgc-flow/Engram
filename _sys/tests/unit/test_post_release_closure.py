"""Offline closure contracts, written before the implementation (cc runs tests)."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[3] / 'tools/release_gate/post_release_closure.py'
SPEC = importlib.util.spec_from_file_location('post_release_closure', SCRIPT)
closure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closure)
NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
HASH = 'a' * 64


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {'tag': 'v1.2.3', 'candidate_sha256s': {
            'app.zip': HASH, 'manifests/App.yaml': HASH}}
        self.release = {'tag_name': 'v1.2.3', 'draft': False,
                        'published_at': '2026-10-09T00:00:00Z', 'assets': [
                            {'name': name, 'digest': 'sha256:' + HASH, 'state': 'uploaded'}
                            for name in ('app.zip', 'App.yaml')]}

    def check(self, winget='available', release=None):
        return closure.check_closure(self.candidate,
            fetch_release=lambda tag: deepcopy(self.release if release is None else release),
            fetch_winget=lambda version: winget, now=NOW)

    def test_closed(self):
        result = self.check()
        self.assertEqual(result['status'], 'CLOSED')
        self.assertEqual(result['candidate_sha256s'], self.candidate['candidate_sha256s'])
        self.assertEqual(result['published_digests']['app.zip'], HASH)
        self.assertTrue(result['checked_at'])

    def test_replaced_asset(self):
        self.release['assets'][0]['digest'] = 'sha256:' + 'b' * 64
        self.assertEqual(self.check()['status'], 'DRIFT')

    def test_attestation_cutoff_404(self):
        for tag, status in [('v3.8.0', 'CLOSED'), ('v3.8.1', 'DRIFT'), ('v3.10.0', 'DRIFT')]:
            with self.subTest(tag=tag):
                self.candidate['tag'] = self.release['tag_name'] = tag
                with patch.object(closure, 'gh_api', side_effect=[
                        dict(self.release, id=1), deepcopy(self.release['assets'])]), \
                        patch.object(closure, 'verify_attestation',
                                     side_effect=RuntimeError('attestation verification failed: HTTP 404')) as verify:
                    result = closure.check_closure(self.candidate, now=NOW,
                        fetch_release=closure.release_fetcher('owner/repo'),
                        fetch_winget=lambda _: 'available')
                self.assertEqual(result['status'], status)
                if tag == 'v3.8.0':
                    verify.assert_not_called()
                    self.assertEqual(result['attestation'], 'not-applicable (predates attestation)')
                    self.assertIn('attestation: not-applicable (predates attestation)', result['summary'])
                    self.assertEqual(result['published_digests']['app.zip'], HASH)
                else:
                    verify.assert_called_once_with('owner/repo', tag, 'app.zip')
                    self.assertIn('HTTP 404', result['summary'])

    def test_tampered_hash_is_drift_across_attestation_cutoff(self):
        for tag in ('v3.8.0', 'v3.8.1'):
            with self.subTest(tag=tag):
                self.candidate['tag'] = self.release['tag_name'] = tag
                self.release['assets'][0]['digest'] = 'sha256:' + 'b' * 64
                with patch.object(closure, 'gh_api', side_effect=[
                        dict(self.release, id=1), deepcopy(self.release['assets'])]), \
                        patch.object(closure, 'verify_attestation'):
                    result = closure.check_closure(self.candidate, now=NOW,
                        fetch_release=closure.release_fetcher('owner/repo'),
                        fetch_winget=lambda _: 'available')
                self.assertEqual(result['status'], 'DRIFT')
                self.assertIn('published assets differ', result['summary'])

    def test_missing_asset(self):
        self.release['assets'].pop()
        self.assertEqual(self.check()['status'], 'DRIFT')

    def test_extra_asset(self):
        self.release['assets'].append({'name': 'extra', 'digest': 'sha256:' + HASH})
        self.assertEqual(self.check()['status'], 'DRIFT')

    def test_pending(self):
        result = self.check('pending')
        self.assertEqual(result['status'], 'OPEN_PENDING')
        self.assertIn('recheck', result)

    def test_pending_expires(self):
        self.release['published_at'] = '2026-09-01T00:00:00Z'
        self.assertEqual(self.check('pending')['status'], 'DRIFT')

    def test_api_errors(self):
        def error(_):
            raise RuntimeError('API unavailable')
        for kwargs in ({'fetch_release': error, 'fetch_winget': lambda _: 'available'},
                       {'fetch_release': lambda _: self.release, 'fetch_winget': error}):
            result = closure.check_closure(self.candidate, now=NOW, **kwargs)
            self.assertEqual(result['status'], 'DRIFT')
            self.assertIn('API unavailable', result['summary'])

    def test_invalid_release_never_closed(self):
        for key, value in [('draft', True), ('tag_name', 'v9'), ('published_at', None)]:
            release = deepcopy(self.release)
            release[key] = value
            self.assertEqual(self.check(release=release)['status'], 'DRIFT')

    def test_missing_digest_and_duplicate_names(self):
        self.release['assets'][0]['digest'] = None
        self.assertEqual(self.check()['status'], 'DRIFT')
        self.release['assets'][0]['digest'] = 'sha256:' + HASH
        self.release['assets'].append(deepcopy(self.release['assets'][0]))
        self.assertEqual(self.check()['status'], 'DRIFT')

    def test_candidate_basename_collision(self):
        self.candidate['candidate_sha256s']['elsewhere/App.yaml'] = HASH
        self.assertEqual(self.check()['status'], 'DRIFT')

    def test_exit_status(self):
        self.assertEqual(closure.exit_code(self.check()), 0)
        self.assertEqual(closure.exit_code(self.check('pending')), 0)
        self.release['assets'].clear()
        self.assertNotEqual(closure.exit_code(self.check()), 0)

    def test_cli_writes_failure_evidence_and_issue_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'candidate.json'
            out = Path(directory) / 'post_release_closure.json'
            candidate.write_text(json.dumps(self.candidate), encoding='utf-8')
            with patch.object(closure, 'release_fetcher', return_value=lambda _: self.release), \
                    patch.object(closure, 'fetch_winget', side_effect=RuntimeError('API unavailable')), \
                    patch('builtins.print') as printed:
                code = closure.main(['--candidate', str(candidate), '--repo', 'owner/repo', '--out', str(out)])
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads(out.read_text())['status'], 'DRIFT')
            self.assertIn('API unavailable', printed.call_args.args[0])

    def test_only_explicit_winget_404_is_pending(self):
        from subprocess import CompletedProcess
        for status in ('404', 404):
            result = CompletedProcess([], 1, json.dumps({'status': status}), 'Not Found')
            with patch.object(closure.subprocess, 'run', return_value=result):
                self.assertEqual(closure.fetch_winget('1.2.3'), 'pending')
        for stdout in ('', '{"status":"403"}', '{"message":"Not Found"}'):
            with patch.object(closure.subprocess, 'run', return_value=CompletedProcess([], 1, stdout, 'error')):
                with self.assertRaises(RuntimeError):
                    closure.fetch_winget('1.2.3')
