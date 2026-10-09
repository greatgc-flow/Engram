import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import pytest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "tools" / "release_gate" / "release_policy.json"
sys.path.insert(0, str(ROOT / '_sys'))
from checks import backup_personal_data as backup
from core import layout_migration

class WaveI(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def scratch_root(self, tmp_path):
        self.root = tmp_path

    def test_bundle_replaces_directory(self):
        item = next(i for i in backup.ITEMS if i.kind == 'dir')
        live = self.root / 'live' / item.live_relpath
        live.mkdir(parents=True)
        (live / 'keep.txt').write_text('keep')
        (live / 'deleted.txt').write_text('gone')
        bundle = self.root / 'bundle'
        backup._sync_item_to_bundle(item, self.root / 'live', bundle)
        (live / 'deleted.txt').unlink()
        dest = bundle / item.bundle_relpath
        (dest / 'auth.json').write_text('old secret')
        backup._sync_item_to_bundle(item, self.root / 'live', bundle)
        self.assertEqual({p.name for p in dest.iterdir()}, {'keep.txt'})

    def test_restore_preview_creates_no_entries(self):
        bundle = self.root / 'bundle'
        bundle.mkdir()
        before = set(self.root.rglob('*'))
        backup.run_restore({'base_dir': self.root / 'new', 'sys_dir': self.root / 'new/_sys',
                            'args': [str(bundle), '--apply', '--dry-run']})
        self.assertEqual(set(self.root.rglob('*')), before)

    def test_update_migration_step_is_explicit_and_preview_safe(self):
        cfg = json.loads((ROOT / '_sys/dispatch.json').read_text())
        self.assertIn('migration.update_layout', cfg['pipelines']['update'])
        for verb in ('doctor', 'menu-status', 'repair', 'restore'):
            self.assertNotIn('migration.update_layout', cfg['pipelines'][verb])
        with patch.object(layout_migration, 'migrate_layout', return_value=0) as run:
            for args in (['--check'], ['--dry-run'], ['--yes', '--dry-run']):
                layout_migration.update_layout({'args': args, 'base_dir': self.root, 'sys_dir': self.root / '_sys'})
            run.assert_not_called()
            layout_migration.update_layout({'args': ['--yes'], 'base_dir': self.root, 'sys_dir': self.root / '_sys'})
            run.assert_called_once_with(self.root, self.root / '_sys', merge_defaults=False)

    def test_dispatch_update_runs_maintenance_without_preview_writes(self):
        from core import dispatcher
        cfg = json.loads((ROOT / '_sys/dispatch.json').read_text())
        sentinel = self.root / 'maintenance'
        def migrate(*args, **kwargs):
            sentinel.write_text('done')
            return 0
        def operation(op_id, config, ctx):
            if op_id == 'migration.update_layout':
                return layout_migration.update_layout(ctx)
            return {'status': 'success'}
        with patch.object(dispatcher, '_load_json', return_value=cfg), patch.object(dispatcher, '_build_ctx', side_effect=lambda cmd, args: {'base_dir': self.root, 'sys_dir': self.root / '_sys', 'args': args}), patch.object(dispatcher, '_run_operation', side_effect=operation), patch.object(layout_migration, 'migrate_layout', side_effect=migrate):
            for verb, args in [('doctor', []), ('menu', ['status']), ('update', ['--check']), ('update', ['--yes', '--dry-run']), ('repair', ['--dry-run']), ('restore', ['bundle', '--dry-run'])]:
                before = set(self.root.rglob('*'))
                dispatcher.run_pipeline(verb, args)
                self.assertEqual(set(self.root.rglob('*')), before)
            dispatcher.run_pipeline('update', ['--yes'])
            self.assertTrue(sentinel.exists())

    def test_update_maintenance_is_offline_and_preserves_declarations(self):
        import urllib.request
        from core import version_resolver
        sys_dir = self.root / '_sys'
        (sys_dir / 'core').mkdir(parents=True)
        (sys_dir / 'defaults').mkdir()
        (sys_dir / 'core/version.json').write_text('{"version":"1.0.0"}')
        declarations = sys_dir / 'runtimes.json'
        declarations.write_text('{"runtimes":{}}')
        (sys_dir / 'defaults/runtimes.json').write_text('{"runtimes":{"python":{"version":"9.9.9"}}}')
        before = declarations.read_bytes()
        with patch.object(urllib.request.OpenerDirector, 'open', side_effect=AssertionError('network')), patch.object(urllib.request, 'urlopen', side_effect=AssertionError('network')), patch.object(version_resolver, 'resolve_latest', side_effect=AssertionError('discovery')):
            result = layout_migration.update_layout({'args': ['--yes'], 'base_dir': self.root, 'sys_dir': sys_dir})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(declarations.read_bytes(), before)

    def test_update_check_cannot_fall_through_when_exit_returns(self):
        from core import updater, version_resolver
        sys_dir = self.root / '_sys'
        (sys_dir / 'core').mkdir(parents=True)
        (sys_dir / 'core/version.json').write_text('{"version":"1.0.0"}')
        (sys_dir / 'runtimes.json').write_text('{"runtimes":{}}')
        (sys_dir / 'tool-catalog.v1.json').write_text('{"tools":[]}')
        discovery = {'artifact_dir': str(self.root), 'updates_discovered': []}
        core_update = {'status': 'ok', 'latest_version': '9.9.9', 'url': 'http://fake.zip', 'checksum_value': 'a' * 64}
        with patch.object(updater, '_SYS_DIR', sys_dir), patch.object(updater, '_PORTABLE_ROOT', self.root), patch.object(updater.check_tool_updates, 'run', return_value=discovery), patch.object(updater, 'check_components', return_value={'missing': []}), patch.object(version_resolver, 'resolve_latest', return_value=core_update), patch.object(sys, 'exit'), patch.object(updater.check_tool_updates, 'apply_proposal', side_effect=AssertionError('apply during check')) as apply, patch.object(updater, '_download_and_stage_core_update', side_effect=AssertionError('download during check')) as download:
            result = updater.run({'args': ['--check']})
        self.assertEqual(result['status'], 'success')
        apply.assert_not_called()
        download.assert_not_called()

    def test_updater_source_policy_rejects_other_sources(self):
        from checks import release_evidence as gate
        hashes = {'release.zip': 'a' * 64}
        candidate = self.root / 'candidate.json'
        candidate.write_text(json.dumps(dict(tag='v2', commit='b' * 40, candidate_sha256s=hashes)))
        base = dict(status='PASS', candidate_sha256s=hashes, cancelled=False, skipped=False, run_id='12', run_attempt='1')
        sandbox = self.root / 'sandbox.json'
        sandbox.write_text(json.dumps(dict(base, provider='windows-sandbox', runner_environment='self-hosted', workflow_run_id='12', image='Windows')))
        winget = self.root / 'winget.json'
        winget.write_text(json.dumps(base))
        upgrade = self.root / 'upgrade.json'
        for source in ('candidate', 'previous', 'unknown', None):
            upgrade.write_text(json.dumps(dict(base, updater_source=source, previous_tag='v1', scenarios={'upgrade': 'PASS', 'rollback': 'PASS'})))
            args = (candidate, sandbox, upgrade)
            kw = dict(winget_evidence_path=winget, run_id='12', run_attempt='1')
            if source in ('candidate', 'previous'):
                gate.verify(*args, **kw)
            else:
                with self.assertRaises(gate.Hold): gate.verify(*args, **kw)

    def test_updater_policy_is_explicit(self):
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy['upgrade_updater_sources'], ['candidate', 'previous'])

    def test_artifact_selection_excludes_other_attempts(self):
        script = ROOT / '.github/scripts/select_current_sandbox.js'
        harness = self.root / 'artifact-test.js'
        harness.write_text("""const fs = require('fs');
const context = {repo: {}, runId: 12};
process.env.GITHUB_RUN_ATTEMPT = '2';
const artifacts = [
 {id:1,name:'sandbox-evidence-windows-sandbox-12-1'},
 {id:2,name:'sandbox-evidence-windows-sandbox-12-2'},
 {id:3,name:'sandbox-evidence-hosted-ephemeral-vm-12-2'},
 {id:4,name:'sandbox-evidence-windows-sandbox-13-2'},
 {id:5,name:'sandbox-evidence-other-12-2'}];
const github = {rest:{actions:{listWorkflowRunArtifacts: {}}}, paginate: async () => artifacts};
const core = {setOutput: (key,value) => {if(value !== '2,3') throw Error(value);}};
const run = new Function('github','context','core','require', 'return (async () => {' + fs.readFileSync(process.argv[2], 'utf8') + '})()');
run(github,context,core,require).catch(err => {console.error(err); process.exit(1);});
""")
        proc = subprocess.run(['node', str(harness), str(script)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_promotion_names_are_current(self):
        workflow = (ROOT / '.github/workflows/sandbox-gate.yml').read_text()
        self.assertNotIn('pattern: sandbox-evidence-', workflow)
        script = (ROOT / '.github/scripts/select_current_sandbox.js').read_text()
        self.assertIn('names.includes(artifact.name)', script)
        self.assertIn('GITHUB_RUN_ATTEMPT', script)

if __name__ == '__main__':
    unittest.main()
