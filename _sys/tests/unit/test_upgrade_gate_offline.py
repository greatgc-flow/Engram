"""Offline upgrade gate unit tests exercising candidate transport seam and rollback.

Covers EN-GAP-P1-003 STEP 1 of 2:
- Local candidate release ZIP transport seam (version_resolver, _secure_download)
- Offline staging and validation of release archives
- Detached helper replacement handoff with process-wait stubbed
- Preservation of user data inventory (.engram files incl. binary/Unicode)
- Verification that installed version == candidate on success
- Deterministic replacement failure leading to FAILED_ROLLED_BACK with baseline bytes restored
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile
import urllib.error
from pathlib import Path
import pytest

from _sys.core.root import find_root

_SYS_DIR = find_root(__file__)
if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))
if str(_SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR / "core"))

from core import provisioner, updater, version_resolver
from tools.release_gate import upgrade_harness



def _fixture_handoff(core_update, sys_dir, target_dir, parent_pid=999999):
    """Helper-only fixture; public updater integration is tested separately below."""
    temp = sys_dir / "data/temp/core-update" / core_update["latest_version"]
    temp.mkdir(parents=True)
    staged = temp / "staged"
    updater._download_and_stage_core_update(core_update["url"], core_update["checksum_value"], temp / "update.zip", staged)
    helper = temp / "core_update_helper.ps1"
    shutil.copyfile(sys_dir / "core/core_update_helper.ps1", helper)
    journal = temp / "journal.json"
    plan = temp / "plan.json"
    plan.write_text(json.dumps({"target_dir": str(target_dir), "staged_dir": str(staged),
        "backup_dir": str(temp / "backup"), "journal_path": str(journal),
        "parent_pid": parent_pid, "sys_dir_name": sys_dir.name}), encoding="utf-8")
    return {"process": provisioner._launch_detached_powershell_helper(helper, plan, temp), "journal_path": journal}

_take_inventory = upgrade_harness.take_inventory
_assert_inventory_identical = upgrade_harness.assert_inventory_identical
_seed_user_data = upgrade_harness.seed_user_data


def _build_fixture_zip(
    zip_path: Path,
    version: str,
    exe_bytes: bytes,
    app_bytes: bytes,
    extra_files: dict[str, bytes] | None = None,
) -> str:
    """Create a minimal release ZIP and return its SHA-256."""
    version_json = json.dumps({"version": version}, indent=2).encode("utf-8")
    readme_bytes = f"# Engram v{version}\n".encode("utf-8")

    manifest_map = {
        "_sys/core/version.json": hashlib.sha256(version_json).hexdigest().upper(),
        "_sys/core/app.py": hashlib.sha256(app_bytes).hexdigest().upper(),
    }
    if extra_files:
        for p, b in extra_files.items():
            manifest_map[p] = hashlib.sha256(b).hexdigest().upper()

    manifest_bytes = json.dumps({"files": manifest_map}, indent=2).encode("utf-8")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Engram.exe", exe_bytes)
        zf.writestr("README.md", readme_bytes)
        zf.writestr("_sys/core/version.json", version_json)
        zf.writestr("_sys/core/app.py", app_bytes)
        zf.writestr("_sys/core/release-manifest.json", manifest_bytes)
        if extra_files:
            for rel_path, content in extra_files.items():
                zf.writestr(rel_path, content)

    return hashlib.sha256(zip_path.read_bytes()).hexdigest()


def _setup_baseline_install(
    target_dir: Path,
    version: str,
    exe_bytes: bytes,
    app_bytes: bytes,
) -> None:
    """Set up a baseline mock portable root matching layout requirements."""
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "Engram.exe").write_bytes(exe_bytes)
    (target_dir / "README.md").write_text(f"# Engram v{version}\n", encoding="utf-8")

    sys_core = target_dir / "_sys" / "core"
    sys_core.mkdir(parents=True, exist_ok=True)
    (sys_core / "version.json").write_text(json.dumps({"version": version}, indent=2), encoding="utf-8")
    (sys_core / "app.py").write_bytes(app_bytes)

    # Provide real core_update_helper.ps1 so handoff can be copied
    real_helper = _SYS_DIR / "core" / "core_update_helper.ps1"
    shutil.copyfile(real_helper, sys_core / "core_update_helper.ps1")


def test_helper_offline_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end offline upgrade gate: staging, validation, handoff, inventory preservation."""
    target_dir = tmp_path / "installed_app"
    prev_version = "1.0.0"
    candidate_version = "1.0.1"

    prev_exe_bytes = b"ENGRAM_EXE_BINARY_V1_0_0"
    candidate_exe_bytes = b"ENGRAM_EXE_BINARY_V1_0_1"
    prev_app_bytes = b"# Baseline app core v1.0.0"
    candidate_app_bytes = b"# Updated app core v1.0.1"

    # 1. Setup baseline installation & seed user data
    _setup_baseline_install(target_dir, prev_version, prev_exe_bytes, prev_app_bytes)
    user_data_dir = target_dir / ".engram"
    _seed_user_data(user_data_dir)
    before_user_inventory = _take_inventory(user_data_dir)
    assert len(before_user_inventory) >= 4

    # 2. Build candidate fixture ZIP
    candidate_zip = tmp_path / f"Engram-v{candidate_version}-portable-x64.zip"
    candidate_sha = _build_fixture_zip(
        candidate_zip, candidate_version, candidate_exe_bytes, candidate_app_bytes
    )

    # 3. Configure test transport seam
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate_zip))
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", candidate_sha)
    monkeypatch.setenv("ENGRAM_UPDATE_SKIP_PROCESS_WAIT", "1")

    # 4. Resolve via version_resolver using test seam
    discovery = version_resolver.resolve_latest(
        tool_name="Engram core",
        provider="engram_release",
        current_version=prev_version,
        discovery_id="greatgc-flow/Engram",
    )
    assert discovery["status"] == "ok"
    assert discovery["latest_version"] == candidate_version
    assert discovery["checksum_value"] == candidate_sha
    assert discovery["url"] == candidate_zip.as_uri()

    # 5. Run real staging, validation, and helper handoff
    staged_res = _fixture_handoff(
        core_update={
            "latest_version": discovery["latest_version"],
            "url": discovery["url"],
            "checksum_value": discovery["checksum_value"],
        },
        sys_dir=target_dir / "_sys",
        target_dir=target_dir,
        parent_pid=999999,
    )

    proc = staged_res["process"]
    ret = proc.wait(timeout=20)
    assert ret == 0, f"Helper process failed with code {ret}"

    # 6. Verify journal record
    journal_path = staged_res["journal_path"]
    assert journal_path.exists()
    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal["status"] == "COMPLETED"

    # 7. Assert user data inventory is strictly byte-identical
    after_user_inventory = _take_inventory(user_data_dir)
    _assert_inventory_identical(before_user_inventory, after_user_inventory)

    # 8. Assert installed version == candidate
    installed_version_info = json.loads(
        (target_dir / "_sys" / "core" / "version.json").read_text(encoding="utf-8")
    )
    assert installed_version_info.get("version") == candidate_version

    # 9. Assert program binaries updated and baseline backup kept
    assert (target_dir / "Engram.exe").read_bytes() == candidate_exe_bytes
    assert (target_dir / "Engram.exe.old").read_bytes() == prev_exe_bytes
    assert (target_dir / "_sys" / "core" / "app.py").read_bytes() == candidate_app_bytes


def test_helper_offline_failure_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Injected replacement conflict yields FAILED_ROLLED_BACK with baseline program bytes restored."""
    target_dir = tmp_path / "installed_app"
    prev_version = "1.0.0"
    candidate_version = "1.0.1"

    prev_exe_bytes = b"ENGRAM_EXE_BASELINE_BYTES"
    candidate_exe_bytes = b"ENGRAM_EXE_NEW_BYTES"
    prev_app_bytes = b"# Baseline app core code"
    candidate_app_bytes = b"# Candidate app core code"

    # 1. Setup baseline installation & seed user data
    _setup_baseline_install(target_dir, prev_version, prev_exe_bytes, prev_app_bytes)
    user_data_dir = target_dir / ".engram"
    _seed_user_data(user_data_dir)
    before_user_inventory = _take_inventory(user_data_dir)

    # Baseline program bytes snapshot
    baseline_version_content = (target_dir / "_sys" / "core" / "version.json").read_text(encoding="utf-8")

    # 2. Build candidate fixture ZIP with an extra file under _sys/core
    extra_rel_file = "_sys/core/conflict_marker.txt"
    candidate_zip = tmp_path / f"Engram-v{candidate_version}-portable-x64.zip"
    candidate_sha = _build_fixture_zip(
        candidate_zip,
        candidate_version,
        candidate_exe_bytes,
        candidate_app_bytes,
        extra_files={extra_rel_file: b"candidate marker content"},
    )

    # 3. Deterministically inject replacement failure:
    # Create target _sys/core/conflict_marker.txt as a DIRECTORY containing an item.
    # Staging & validation will succeed, but Copy-Item will fail trying to copy a file over a directory.
    conflict_dir = target_dir / "_sys" / "core" / "conflict_marker.txt"
    conflict_dir.mkdir(parents=True, exist_ok=True)
    (conflict_dir / "blocking_entry").write_text("block", encoding="utf-8")

    # 4. Set test seam environment variables
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate_zip))
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", candidate_sha)
    monkeypatch.setenv("ENGRAM_UPDATE_SKIP_PROCESS_WAIT", "1")

    staged_res = _fixture_handoff(
        core_update={
            "latest_version": candidate_version,
            "url": candidate_zip.as_uri(),
            "checksum_value": candidate_sha,
        },
        sys_dir=target_dir / "_sys",
        target_dir=target_dir,
        parent_pid=999999,
    )

    proc = staged_res["process"]
    ret = proc.wait(timeout=20)
    assert ret == 1, f"Expected helper to exit with code 1 upon rollback, got {ret}"

    # 5. Assert journal status is FAILED_ROLLED_BACK
    journal_path = staged_res["journal_path"]
    assert journal_path.exists()
    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal["status"] == "FAILED_ROLLED_BACK"

    # 6. Assert user data inventory remains strictly byte-identical
    after_user_inventory = _take_inventory(user_data_dir)
    _assert_inventory_identical(before_user_inventory, after_user_inventory)

    # 7. Assert baseline program bytes restored
    assert (target_dir / "Engram.exe").read_bytes() == prev_exe_bytes
    assert not (target_dir / "Engram.exe.old").exists()
    assert (target_dir / "_sys" / "core" / "version.json").read_text(encoding="utf-8") == baseline_version_content
    assert (target_dir / "_sys" / "core" / "app.py").read_bytes() == prev_app_bytes


def test_transport_seam_validation_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Transport seam enforces SHA256 checksum and production safety guards."""
    candidate_zip = tmp_path / "candidate.zip"
    valid_sha = _build_fixture_zip(candidate_zip, "1.0.1", b"EXE", b"APP")

    # 1. Tampered checksum is caught and rejected by staging
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate_zip))
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", "0" * 64)

    staged_dir = tmp_path / "staged"
    dest_zip = tmp_path / "downloaded.zip"
    with pytest.raises(ValueError, match="Checksum mismatch"):
        updater._download_and_stage_core_update(
            candidate_zip.as_uri(), "0" * 64, dest_zip, staged_dir
        )

    # 2. Production safety guard: file:// URIs are rejected if candidate seam is unset
    monkeypatch.delenv("ENGRAM_UPDATE_CANDIDATE_ZIP", raising=False)
    dest_zip2 = tmp_path / "downloaded2.zip"
    with pytest.raises(urllib.error.URLError, match="Local file URLs only permitted"):
        provisioner._secure_download(candidate_zip.as_uri(), dest_zip2)


@pytest.mark.parametrize("sha", [None, "", "   ", "not-a-sha256"])
def test_candidate_requires_external_sha256(tmp_path, monkeypatch, sha):
    candidate = tmp_path / "candidate.zip"
    _build_fixture_zip(candidate, "1.0.1", b"EXE", b"APP")
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate))
    monkeypatch.delenv("ENGRAM_UPDATE_CANDIDATE_SHA256", raising=False)
    if sha is not None:
        monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", sha)
    result = version_resolver._resolve_engram_release("fixture/repo")
    assert result["status"] == "error"
    assert result["error_type"] == "invalid_candidate_sha256"


@pytest.mark.parametrize("version", ["../escape", r"..\escape", "C:/escape", "1.0.1:stream", "1.0.1;exit", "1.0.1\n"])
def test_candidate_version_rejects_injection(tmp_path, monkeypatch, version):
    candidate = tmp_path / "candidate.zip"
    sha = _build_fixture_zip(candidate, "1.0.1", b"EXE", b"APP")
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate))
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", sha)
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_VERSION", version)
    result = version_resolver._resolve_engram_release("fixture/repo")
    assert result["status"] == "error"
    assert result["error_type"] == "invalid_candidate_version"


def test_bare_skip_environment_keeps_parent_wait(tmp_path, monkeypatch):
    # Exercise the helper's actual wait block with a mocked parent process.
    import subprocess
    helper = (_SYS_DIR / "core" / "core_update_helper.ps1").read_text()
    wait_block = helper[helper.index("try {"):helper.index("function Write-Journal")]
    monkeypatch.setenv("ENGRAM_UPDATE_SKIP_PROCESS_WAIT", "1")
    script = tmp_path / "wait.ps1"
    script.write_text("""$Plan = [pscustomobject]@{}
$ParentPID = 42
$script:waited = $false
function Get-Process {
    param($Id, $ErrorAction)
    $p = [pscustomobject]@{}
    $p | Add-Member ScriptMethod WaitForExit { $script:waited = $true }
    return $p
}
""" + wait_block + "if (-not $script:waited) { exit 17 }", encoding="utf-8")
    cp = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script)], capture_output=True)
    assert cp.returncode == 0, cp.stderr


def test_candidate_transport_requires_external_digest(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.zip"
    _build_fixture_zip(candidate, "1.0.1", b"EXE", b"APP")
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate))
    monkeypatch.delenv("ENGRAM_UPDATE_CANDIDATE_SHA256", raising=False)
    with pytest.raises(urllib.error.URLError, match="require ENGRAM_UPDATE_CANDIDATE_SHA256"):
        provisioner._secure_download(candidate.as_uri(), tmp_path / "download.zip")


@pytest.mark.parametrize("undo_fails", [False, True])
@pytest.mark.parametrize("sys_name", ["_sys", "custom_sys"])
def test_helper_verified_rollback_inventory(tmp_path, monkeypatch, undo_fails, sys_name):
    """Real handoff: fail after candidate copy, then optionally fail backup restore."""
    import subprocess
    target = tmp_path / "installed"
    _setup_baseline_install(target, "1.0.0", b"OLD EXE", b"OLD APP")
    if sys_name != "_sys":
        (target / "_sys").rename(target / sys_name)
    before = upgrade_harness.take_inventory(target)
    candidate = tmp_path / "candidate.zip"
    sha = _build_fixture_zip(candidate, "1.0.1", b"NEW EXE", b"NEW APP",
                             {"_sys/core/introduced.txt": b"NEW FILE"})
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_ZIP", str(candidate))
    monkeypatch.setenv("ENGRAM_UPDATE_CANDIDATE_SHA256", sha)
    monkeypatch.setenv("ENGRAM_UPDATE_SKIP_PROCESS_WAIT", "1")
    observed = tmp_path / "undo-status.txt"

    def launch(helper, plan, workdir):
        wrapper = tmp_path / "fault.ps1"
        # Override only the filesystem boundary; execute the complete real helper.
        wrapper.write_text(r"""
param($Helper, $PlanPath, $Observed, $UndoFails)
$global:wavePayload = Get-Content -LiteralPath $PlanPath | ConvertFrom-Json
function Copy-Item {
    param($Path, $LiteralPath, $Destination, [switch]$Force, [switch]$Recurse)
    $source = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ([string]$source -like "$($global:wavePayload.backup_dir)*") {
        (Get-Content $global:wavePayload.journal_path | ConvertFrom-Json).status |
            Set-Content $Observed
        if ($UndoFails -eq 'True') { throw 'injected undo failure' }
    }
    if ($LiteralPath) {
        Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force -Recurse:$Recurse
    } else {
        Microsoft.PowerShell.Management\Copy-Item -Path $Path -Destination $Destination -Force:$Force -Recurse:$Recurse
    }
    if ([string]$source -like "$($global:wavePayload.staged_dir)*" -and
        (Test-Path (Join-Path $global:wavePayload.target_dir '""" + sys_name + r"""/core/introduced.txt'))) {
        throw 'injected failure after candidate file creation'
    }
}
& $Helper -PlanPath $PlanPath
exit $LASTEXITCODE
""", encoding="utf-8")
        return subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(wrapper), "-Helper", str(helper), "-PlanPath", str(plan),
             "-Observed", str(observed), "-UndoFails", str(undo_fails)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    monkeypatch.setattr(provisioner, "_launch_detached_powershell_helper", launch)
    result = _fixture_handoff(
        {"latest_version": "1.0.1", "url": candidate.as_uri(), "checksum_value": sha},
        sys_dir=target / sys_name, target_dir=target, parent_pid=999999)
    assert result["process"].wait(timeout=20) == 1
    journal = json.loads(result["journal_path"].read_text(encoding="utf-8-sig"))
    assert observed.read_text(encoding="utf-8-sig").strip() == "ROLLBACK_IN_PROGRESS"
    assert journal["status"] == ("FAILED_ROLLBACK_FAILED" if undo_fails else "FAILED_ROLLED_BACK")
    assert f"{sys_name}\\core\\introduced.txt" in journal["created_files"]
    if not undo_fails:
        after = {k: v for k, v in upgrade_harness.take_inventory(target).items()
                 if not k.startswith(f"{sys_name}/data/temp/")}
        upgrade_harness.assert_inventory_identical(before, after)



import unittest
try:
    from evidence_fixtures import evidence_fixture, temporary_directory
except ModuleNotFoundError:
    from _sys.tests.unit.evidence_fixtures import evidence_fixture, temporary_directory
import tempfile


class UpgradeGateTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def scratch_root(self, tmp_path):
        from functools import partial
        from unittest.mock import patch
        self.root = tmp_path
        self.temporary_directory = partial(temporary_directory, tmp_path)
        with patch.object(tempfile, 'TemporaryDirectory', self.temporary_directory):
            yield

    def fixture(self, root, previous_seam=True, prev_version="1.0.0", cand_version="1.0.1", cand_tag="v1.0.1"):
        target = root / "installed"
        target.mkdir()
        for name in ("core", "checks", "defaults"):
            shutil.copytree(_SYS_DIR / name, target / "_sys" / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (target / "Engram.exe").write_bytes(b"OLD EXE")
        (target / "README.md").write_bytes(b"OLD README")
        (target / "_sys/core/version.json").write_text(json.dumps({"version": prev_version}), encoding="utf-8")
        upgrade_harness.seed_user_data(target / ".engram")
        candidate = root / "candidate.zip"
        with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in target.rglob("*"):
                if path.is_file() and ".engram" not in path.parts:
                    rel = path.relative_to(target).as_posix()
                    if rel.endswith("release-manifest.json"):
                        continue
                    content = path.read_bytes()
                    if rel == "_sys/core/version.json":
                        content = json.dumps({"version": cand_version}).encode("utf-8")
                    archive.writestr(rel, content)
            archive.writestr("_sys/core/introduced.txt", b"candidate-only file")
        if not previous_seam:
            (target / "_sys/core/version_resolver.py").write_text("# old resolver", encoding="utf-8")
        identity = root / "candidate.json"
        identity.write_text(json.dumps({"tag": cand_tag, "candidate_sha256s": {
            candidate.name: hashlib.sha256(candidate.read_bytes()).hexdigest()}}), encoding="utf-8")
        return target, candidate, identity

    def test_upgrade_gate_offline_success(self):
        with self.temporary_directory() as temp:
            target, candidate, identity = self.fixture(Path(temp))
            evidence = upgrade_harness.run_upgrade_gate(target, candidate, identity, "v1.0.0")
            self.assertEqual(evidence["updater_source"], "previous")
            self.assertEqual(evidence["scenarios"], {"upgrade": "PASS", "rollback": "PASS"})

    def test_upgrade_gate_offline_failure_rollback(self):
        with self.temporary_directory() as temp:
            target, candidate, identity = self.fixture(Path(temp), previous_seam=False)
            evidence = upgrade_harness.run_upgrade_gate(target, candidate, identity, "v1.0.0")
            self.assertEqual(evidence["updater_source"], "candidate")
            self.assertEqual(evidence["scenarios"]["rollback"], "PASS")

    def test_candidate_version_equal_previous_stable_holds(self):
        with self.temporary_directory() as temp:
            target, candidate, identity = self.fixture(
                Path(temp), prev_version="3.7.0", cand_version="3.7.0", cand_tag="candidate-3.7.0"
            )
            with self.assertRaises(ValueError) as ctx:
                upgrade_harness.run_upgrade_gate(target, candidate, identity, "v3.7.0")
            self.assertIn("HOLD: candidate version 3.7.0 is not newer than previous v3.7.0", str(ctx.exception))

    def test_candidate_version_older_than_previous_holds(self):
        with self.temporary_directory() as temp:
            target, candidate, identity = self.fixture(
                Path(temp), prev_version="1.0.1", cand_version="1.0.0", cand_tag="v1.0.0"
            )
            with self.assertRaises(ValueError) as ctx:
                upgrade_harness.run_upgrade_gate(target, candidate, identity, "v1.0.1")
            self.assertIn("HOLD: candidate version 1.0.0 is not newer than previous v1.0.1", str(ctx.exception))

    def test_candidate_version_precondition_cli_output(self):
        import io
        from unittest.mock import patch
        with self.temporary_directory() as temp:
            target, candidate, identity = self.fixture(
                Path(temp), prev_version="3.7.0", cand_version="3.7.0", cand_tag="candidate-3.7.0"
            )
            stderr_buf = io.StringIO()
            with patch("sys.stderr", stderr_buf):
                ret = upgrade_harness.main([
                    "run",
                    "--target-dir", str(target),
                    "--candidate-zip", str(candidate),
                    "--candidate-json", str(identity),
                    "--prev-tag", "v3.7.0",
                ])
            self.assertEqual(ret, 1)
            output_lines = [l.strip() for l in stderr_buf.getvalue().splitlines() if l.strip()]
            self.assertIn("HOLD: candidate version 3.7.0 is not newer than previous v3.7.0", output_lines)

    def test_updater_not_started_fails_fast(self):
        import subprocess
        from unittest.mock import patch
        with self.temporary_directory() as temp:
            target = Path(temp) / "installed"
            target.mkdir()
            (target / "_sys/data/temp").mkdir(parents=True)
            mock_proc = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Everything Engram can check is up to date.\n", stderr=""
            )
            with patch("subprocess.run", return_value=mock_proc):
                with self.assertRaises(RuntimeError) as ctx:
                    upgrade_harness.public_update(
                        target=target,
                        code_sys=target / "_sys",
                        fault=Path(temp) / "fault",
                        env={},
                        version="3.7.0",
                        expected="COMPLETED",
                    )
                self.assertIn("updater did not start a core update: Everything Engram can check is up to date.", str(ctx.exception))

    def test_missing_rollback_blocks_pass(self):
        from _sys.checks import release_evidence
        with self.temporary_directory() as temp:
            root = Path(temp)
            hashes = {"candidate.zip": "a" * 64}
            candidate = {"tag": "v2", "commit": "b" * 40, "candidate_sha256s": hashes}
            base = {"status": "PASS", "candidate_sha256s": hashes, "cancelled": False,
                    "skipped": False, "run_id": "1", "run_attempt": "1"}
            sandbox = dict(base, provider="hosted-ephemeral-vm", runner_environment="github-hosted",
                           workflow_run_id="1", image="Windows")
            upgrade = dict(base, previous_tag="v1", updater_source="previous", scenarios={"upgrade": "PASS"})
            for name, value in (("candidate", candidate), ("sandbox", sandbox), ("upgrade", upgrade)):
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(release_evidence.Hold, "rollback"):
                release_evidence.verify(root / "candidate", root / "sandbox", root / "upgrade",
                    winget_evidence_path=evidence_fixture(root / "candidate", "winget", "1"), run_id="1", run_attempt="1")


if __name__ == "__main__":
    unittest.main()


