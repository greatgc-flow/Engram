"""Wave B1 release coherence regressions; stdlib execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import uuid
from contextlib import contextmanager
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[3]
@contextmanager
def temporary_directory():
    root=ROOT / ('b1-fixture-'+uuid.uuid4().hex)
    root.mkdir(mode=511)
    try:yield str(root)
    finally:shutil.rmtree(root)
def load(name):
    path = ROOT / ('_sys/checks/release_evidence.py' if name == 'release_evidence' else f'tools/release_gate/{name}.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

gate = load('release_evidence')
hosted = load('hosted_clean_room')
closure = load('post_release_closure')

class B1Tests(unittest.TestCase):
    def test_sandbox_requires_flags(self):
        with temporary_directory() as tmp:
            root = Path(tmp)
            hashes = {'app.zip': 'a'*64}
            (root/'candidate.json').write_text(json.dumps({'tag':'v1.2.3','commit':'b'*40,'candidate_sha256s':hashes}))
            data = dict(status='PASS', candidate_sha256s=hashes, provider='windows-sandbox', runner_environment='self-hosted', workflow_run_id='12', image='Windows',run_id='12',run_attempt='1')
            (root/'evidence.json').write_text(json.dumps(data))
            with patch.dict('os.environ', GITHUB_RUN_ID='12', GITHUB_RUN_ATTEMPT='1'):
                with self.assertRaises(gate.Hold):
                    gate.verify(root/'candidate.json',root/'evidence.json',no_upgrade_evidence=True,no_winget_evidence=True)

    def test_shared_validator_rejects_stale_identity_and_flags(self):
        good=dict(status='PASS',candidate_sha256s={'a.zip':'a'*64},cancelled=False,skipped=False,run_id='12',run_attempt='1')
        for label in ('Sandbox','upgrade','WinGet'):
            gate.validate_evidence(good,good['candidate_sha256s'],label,run_id='12',run_attempt='1')
            for field in ('run_id','run_attempt','cancelled','skipped'):
                for value in (None,0,True,'stale'):
                    with self.subTest(label=label,field=field,value=value),self.assertRaises(gate.Hold):
                        gate.validate_evidence(dict(good,**{field:value}),good['candidate_sha256s'],label,run_id='12',run_attempt='1')

    def test_hosted_rejects_existing_root(self):
        with temporary_directory() as tmp:
            root=Path(tmp); clean=root/'clean'; clean.mkdir()
            (clean/'engram.cmd').write_text('stub')
            (clean/'_sys/core').mkdir(parents=True)
            (clean/'_sys/core/bootstrap.bat').write_text('stub')
            cand=root/'candidate.json'
            cand.write_text(json.dumps(dict(tag='v1.2.3',commit='a'*40,candidate_sha256s={'app.zip':'a'*64})))
            with self.assertRaises(hosted.Hold):
                hosted.execute_hosted_clean_room(cand,clean,root/'out.json',runner=lambda *a,**k:'PASS')

    def test_hosted_rejects_archive_hash_before_commands(self):
        with temporary_directory() as tmp:
            root=Path(tmp); archive=root/'app.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('engram.cmd','stub');z.writestr('_sys/core/bootstrap.bat','stub')
            cand=root/'candidate.json'
            cand.write_text(json.dumps(dict(tag='v1.2.3',commit='a'*40,candidate_sha256s={'app.zip':'a'*64})))
            with self.assertRaises(hosted.Hold):
                hosted.execute_hosted_clean_room(cand,root/'clean',root/'out.json',candidate_zip=archive,runner=lambda *a,**k:'PASS')

    def test_timeout_continues_ledger(self):
        with temporary_directory() as tmp:
            root=Path(tmp); candidates=root/'candidates';candidates.mkdir()
            for name in ('a','b'):
                (candidates/(name+'.json')).write_text(json.dumps(dict(tag='v1.2.3',candidate_sha256s={'app.zip':'a'*64})))
            calls=[]
            def run(cmd,**kwargs):
                calls.append(cmd)
                if len(calls)==1: raise subprocess.TimeoutExpired(cmd,180)
                return subprocess.CompletedProcess(cmd,0,'CLOSED','')
            self.assertEqual(closure.check_ledger(candidates,root/'results','owner/repo',run=run),1)
            self.assertEqual(len(calls),2)
            evidence=json.loads((root/'results/a/post_release_closure.json').read_text())
            self.assertEqual(evidence['status'],'DRIFT')
            self.assertEqual(evidence['candidate_sha256s'],{'app.zip':'a'*64})

    def test_required_contract_skip_fails(self):
        checks=load('check_required_tests')
        with temporary_directory() as tmp:
            report=Path(tmp)/'report.xml'
            report.write_text('<testsuite><testcase classname="a" name="b"><skipped/></testcase></testsuite>')
            with self.assertRaises(ValueError):checks.check_report(report,['a::b'])
            report.write_text('<testsuite><testcase classname="a" name="b"/></testsuite>')
            checks.check_report(report,['a::b'])
            with self.assertRaises(ValueError):checks.check_report(report,['missing::test'])

    def test_full_promotion_binds_each_evidence_to_current_run(self):
        with temporary_directory() as tmp:
            root=Path(tmp)
            hashes={'app.zip':'a'*64}
            candidate=root/'candidate.json'
            candidate.write_text(json.dumps(dict(tag='v1.2.3',commit='b'*40,candidate_sha256s=hashes)))
            good=dict(status='PASS',candidate_sha256s=hashes,cancelled=False,skipped=False,run_id='12',run_attempt='2')
            reports=[root/(name+'.json') for name in ('sandbox','upgrade','winget')]
            data=[dict(good,provider='windows-sandbox',runner_environment='self-hosted',workflow_run_id='12',image='Windows'),dict(good,previous_tag='v1.2.2',updater_source='previous',scenarios={'upgrade':'PASS','rollback':'PASS'}),good]
            def verify():
                gate.verify(candidate,reports[0],reports[1],winget_evidence_path=reports[2],run_id='12',run_attempt='2')
            for path,value in zip(reports,data):path.write_text(json.dumps(value))
            verify()
            for path,value in zip(reports,data):
                for field in ('run_id','run_attempt'):
                    with self.subTest(evidence=path.stem,field=field):
                        path.write_text(json.dumps(dict(value,**{field:'1'})))
                        with self.assertRaises(gate.Hold):verify()
                        path.write_text(json.dumps(value))
            with patch.dict('os.environ',GITHUB_RUN_ID='',GITHUB_RUN_ATTEMPT=''):
                with self.assertRaises(gate.Hold):
                    gate.verify(candidate,reports[0],reports[1],winget_evidence_path=reports[2])

    def test_hosted_valid_archive_runs_mandatory_suite(self):
        with temporary_directory() as tmp:
            root=Path(tmp);archive=root/'app.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('engram.cmd','stub');z.writestr('_sys/core/bootstrap.bat','stub')
            candidate=root/'candidate.json'
            candidate.write_text(json.dumps(dict(tag='v1.2.3',commit='a'*40,candidate_sha256s={'app.zip':hashlib.sha256(archive.read_bytes()).hexdigest()})))
            calls=[]
            evidence=hosted.execute_hosted_clean_room(candidate,root/'clean',root/'out.json',candidate_zip=archive,runner=lambda cmd,**kwargs:calls.append(cmd))
            self.assertEqual(evidence['status'],'PASS')
            self.assertEqual(calls,load('installed_artifact_suite').commands(root/'clean'))
            sandbox=load('sandbox_installed_suite')
            (root/'_sys/tests').mkdir(parents=True)
            entry=sandbox.prepare(root).read_text()
            for command in load('installed_artifact_suite').commands(Path('.')):
                self.assertIn('call '+subprocess.list2cmdline(command),entry)
            self.assertIn('check_required_tests.py',entry)

    def test_wait_reads_policy_numbers(self):
        script=ROOT/'.github/scripts/wait_for_sandbox.js'
        js="""const fs=require('fs');let now=0;Date.now=()=>now;
        global.setTimeout=(fn,ms)=>{now+=ms;fn();};
        const policy={evidence_wait_minutes:1,evidence_poll_seconds:7};
        const injected=name=>name==='fs'?{readFileSync:()=>JSON.stringify(policy)}:require(name);
        const github={rest:{actions:{listJobsForWorkflowRunAttempt(){}}},paginate:async()=>[{name:'build-candidate'}]};
        const wait=new Function('github','context','core','require','return (async()=>{'+fs.readFileSync(process.argv[1],'utf8')+'})()');
        wait(github,{repo:{},runId:12},{info(){}},injected).catch(e=>console.log(JSON.stringify({now,error:e.message})));
        """
        result=subprocess.run(['node','-e',js,str(script)],capture_output=True,text=True,timeout=10,check=True)
        report=json.loads(result.stdout)
        self.assertEqual(report['now'],60000)
        self.assertIn('(1 minutes)',report['error'])

    def test_policy_and_shared_suite(self):
        policy=json.loads((ROOT/'release_policy.json').read_text())
        self.assertEqual([policy[k] for k in ('evidence_wait_minutes','evidence_poll_seconds','winget_pending_days','closure_retention_days')],[45,15,21,90])
        suite=load('installed_artifact_suite')
        commands=suite.commands(ROOT)
        self.assertEqual(len(commands),3)
        self.assertEqual(commands[1][1:],['doctor','--json'])
        self.assertEqual(commands[2][1:],['update','--check','--refresh'])

if __name__ == '__main__':unittest.main()
