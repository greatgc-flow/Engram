"""Offline R3 contracts; cc owns suite and hosted validation."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


class WaveR3(unittest.TestCase):
    def test_previous_updater_only(self):
        policy = json.loads((ROOT / 'tools/release_gate/release_policy.json').read_text())
        self.assertEqual(policy['upgrade_updater_sources'], ['previous'])

    def test_promotion_attestation(self):
        workflow = (ROOT / '.github/workflows/sandbox-gate.yml').read_text()
        promotion = re.search(r'^  promotion:\n(.*?)(?=^  \w[\w-]*:|\Z)', workflow, re.M | re.S).group(1)
        step = re.search(r'      - name: Attest verified release zip\n(.*?)(?=      - |\Z)', promotion, re.S)
        self.assertIsNotNone(step)
        self.assertRegex(step.group(1), r'uses: actions/attest-build-provenance@[0-9a-f]{40} # v4\.2\.2')
        self.assertIn('subject-path: release/assets/*.zip', step.group(1))
        self.assertNotRegex(step.group(1), r'if:|continue-on-error:')
        self.assertLess(promotion.index('Verify before promotion or publish'), step.start())
        self.assertLess(step.start(), promotion.index('Publish verified tag assets'))
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", promotion)
        permissions = re.search(r'    permissions:\n(.*?)    steps:', promotion, re.S).group(1)
        outside = workflow.replace(promotion, '')
        for scope in ('id-token', 'attestations'):
            self.assertRegex(permissions, rf'(?m)^      {scope}: write$')
            self.assertNotRegex(outside, rf'(?m)^\s+{scope}: write\s*$')

    def test_closure_attestation_command_and_failure(self):
        spec = importlib.util.spec_from_file_location('closure_r3', ROOT / 'tools/release_gate/post_release_closure.py')
        closure = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(closure)
        for code in (0, 1):
            results = [subprocess.CompletedProcess([], 0, '', ''),
                       subprocess.CompletedProcess([], code, '', 'unverified')]
            with patch.object(closure.tempfile, 'TemporaryDirectory') as directory, \
                    patch.object(closure.subprocess, 'run', side_effect=results) as run:
                directory.return_value.__enter__.return_value = 'scratch'
                if code:
                    with self.assertRaisesRegex(RuntimeError, 'attestation'):
                        closure.verify_attestation('owner/repo', 'v3.8.1', 'app.zip')
                else:
                    closure.verify_attestation('owner/repo', 'v3.8.1', 'app.zip')
                args = run.call_args.args[0]
                self.assertEqual(args[:3], ['gh', 'attestation', 'verify'])
                self.assertEqual(args[4:], ['--repo', 'owner/repo'])
                download = run.call_args_list[0].args[0]
                self.assertEqual(download[:4], ['gh', 'release', 'download', 'v3.8.1'])
                self.assertIn('app.zip', download)

    def test_closure_verification_failure_is_drift(self):
        spec = importlib.util.spec_from_file_location('closure_drift', ROOT / 'tools/release_gate/post_release_closure.py')
        closure = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(closure)
        release = {'id': 1}
        assets = [{'name': 'app.zip'}]
        with patch.object(closure, 'gh_api', side_effect=[release, assets]), \
                patch.object(closure, 'verify_attestation', side_effect=RuntimeError('attestation unverified')) as verify:
            result = closure.check_closure({'tag': 'v3.8.1', 'candidate_sha256s': {'app.zip': 'a' * 64}},
                fetch_release=closure.release_fetcher('owner/repo'), fetch_winget=lambda _: 'available')
        verify.assert_called_once_with('owner/repo', 'v3.8.1', 'app.zip')
        self.assertEqual(result['status'], 'DRIFT')
        self.assertIn('attestation unverified', result['summary'])


if __name__ == '__main__':
    unittest.main()
