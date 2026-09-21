"""Static analysis tests for tracked shell / harness scripts (Audit Finding L-4).

Contracts asserted:
1. Each listed harness script exists and is non-empty.
2. Every repo-relative script/file path invoked or referenced that is deterministically
   resolvable without running anything points to an existing file/directory in the repo.
   Runtime state dependencies (e.g. _sys/env/... venv paths, dynamic .wsb templates)
   are skipped with explanatory comments.
3. Tracked .bat files contain no statically checkable reference to a _sys-named path
   that does not exist in the repo tree. Genuine existing breakages are marked
   xfail(strict=True, reason=...).
"""

import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

HARNESS_SCRIPTS = [
    "_sys/checks/saturation-scan.bat",
    "_sys/tests/host-test.ps1",
    "_sys/tests/integration-test.ps1",
    "_sys/tests/launch-wsbtest.ps1",
    "_sys/tests/test-runner.ps1",
    "_sys/tests/local-test.bat",
    "_sys/tests/run-sandbox-test.bat",
    "_sys/tests/run-tests.bat",
    "_sys/tests/wsb-entry.bat",
]

# Statically determinable file references in each harness script.
# Runtime paths (e.g. _sys/env/..., _sys/data/..., temp files, dynamic wsb files) are omitted.
RESOLVABLE_REFERENCES = [
    # saturation-scan.bat
    # Runtime skip: %SYS_DIR%\env\venv\Scripts\python.exe (virtualenv runtime)
    pytest.param(
        "_sys/checks/saturation-scan.bat",
        "_sys/checks/saturation_scan.py",
        id="saturation_scan_bat->saturation_scan_py",
    ),
    # host-test.ps1
    # Runtime skip: $SysDir\env\vscode\..., $NpmGlobal\..., node.exe (host-installed tools)
    pytest.param(
        "_sys/tests/host-test.ps1",
        "CONVENTION.md",
        id="host_test_ps1->CONVENTION_md",
    ),
    pytest.param(
        "_sys/tests/host-test.ps1",
        "_archive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="host-test.ps1 line 123 expects '_archive' directory at repo root, but _archive is not committed to git repo",
        ),
        id="host_test_ps1->_archive",
    ),
    pytest.param(
        "_sys/tests/host-test.ps1",
        "_sys/start.bat",
        id="host_test_ps1->start_bat",
    ),
    # Broken reference: host-test.ps1 lines 125-126 reference _sys/test/... instead of _sys/tests/...
    pytest.param(
        "_sys/tests/host-test.ps1",
        "_sys/test/launch-wsbtest.ps1",
        marks=pytest.mark.xfail(
            strict=True,
            reason="host-test.ps1 references '_sys/test/launch-wsbtest.ps1' but folder was renamed to '_sys/tests/'",
        ),
        id="host_test_ps1->_sys_test_launch_wsbtest_ps1",
    ),
    pytest.param(
        "_sys/tests/host-test.ps1",
        "_sys/test/host-test.ps1",
        marks=pytest.mark.xfail(
            strict=True,
            reason="host-test.ps1 references '_sys/test/host-test.ps1' but folder was renamed to '_sys/tests/'",
        ),
        id="host_test_ps1->_sys_test_host_test_ps1",
    ),
    # integration-test.ps1
    # Runtime skip: $ENV\..., $TOOLS\..., $SYS\data\..., _archive\test-results (runtime env/state/results)
    pytest.param(
        "_sys/tests/integration-test.ps1",
        "_sys/dispatch.json",
        id="integration_test_ps1->_sys_dispatch_json",
    ),
    # launch-wsbtest.ps1
    # Runtime skip: porta-wsbtest-*.wsb in $env:TEMP, results folder (runtime state/outputs)
    pytest.param(
        "_sys/tests/launch-wsbtest.ps1",
        "_sys/tests/wsb-entry.bat",
        id="launch_wsbtest_ps1->wsb_entry_bat",
    ),
    # test-runner.ps1
    # Runtime skip: results folder, temp workspaces (runtime outputs)
    pytest.param(
        "_sys/tests/test-runner.ps1",
        "_sys/tests/host-test.ps1",
        id="test_runner_ps1->host_test_ps1",
    ),
    pytest.param(
        "_sys/tests/test-runner.ps1",
        "_sys/tests/launch-wsbtest.ps1",
        id="test_runner_ps1->launch_wsbtest_ps1",
    ),
    # Broken reference: test-runner.ps1 line 89 references sandbox-test.bat which does not exist
    pytest.param(
        "_sys/tests/test-runner.ps1",
        "_sys/tests/sandbox-test.bat",
        marks=pytest.mark.xfail(
            strict=True,
            reason="test-runner.ps1 references 'sandbox-test.bat' which does not exist in repo",
        ),
        id="test_runner_ps1->sandbox_test_bat",
    ),
    # local-test.bat
    # Runtime skip: %PD%\_sys\tools\..., %PD%\_sys\env\..., %TW%, %TR% (runtime tools/temp)
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/start.bat",
        id="local_test_bat->start_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/context",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat line 29 references '_sys/context/*.bat' but _sys/context directory does not exist",
        ),
        id="local_test_bat->_sys_context",
    ),
    # Broken references in local-test.bat: references _sys\test\... instead of _sys\tests\...
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/sandbox-test.bat",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat references '_sys/test/sandbox-test.bat' which does not exist in repo",
        ),
        id="local_test_bat->_sys_test_sandbox_test_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/run-sandbox-test.bat",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat references '_sys/test/run-sandbox-test.bat' but folder is '_sys/tests/'",
        ),
        id="local_test_bat->_sys_test_run_sandbox_test_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/sandbox-unit-test.wsb",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat references '_sys/test/sandbox-unit-test.wsb' but folder is '_sys/tests/'",
        ),
        id="local_test_bat->_sys_test_sandbox_unit_test_wsb",
    ),
    # run-sandbox-test.bat
    # Runtime skip: %SystemRoot%\Temp\porta_sandbox_test_*.wsb, %RESULTS_DIR% (runtime wsb/results)
    pytest.param(
        "_sys/tests/run-sandbox-test.bat",
        "_sys/tests/sandbox-unit-test.wsb",
        id="run_sandbox_test_bat->sandbox_unit_test_wsb",
    ),
    # run-tests.bat
    # Runtime skip: %PORTABLE_ROOT%\_sys\env\venv\Scripts (runtime venv)
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit",
        id="run_tests_bat->unit_dir",
    ),
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_system_lifecycle.py",
        id="run_tests_bat->test_system_lifecycle_py",
    ),
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_path_scenarios.py",
        id="run_tests_bat->test_path_scenarios_py",
    ),
    # wsb-entry.bat
    # Runtime skip: %TGT%\_sys\env\... (guest venv and python runtimes)
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/core/bootstrap.bat",
        id="wsb_entry_bat->bootstrap_bat",
    ),
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/tests/unit",
        id="wsb_entry_bat->unit_dir",
    ),
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/tests/lifecycle_tester.py",
        id="wsb_entry_bat->lifecycle_tester_py",
    ),
]


BAT_FILES = [
    "_sys/checks/saturation-scan.bat",
    "_sys/tests/local-test.bat",
    "_sys/tests/run-sandbox-test.bat",
    "_sys/tests/run-tests.bat",
    "_sys/tests/wsb-entry.bat",
]

# Statically checkable _sys-named tokens in .bat files
BAT_SYS_TOKENS = [
    # _sys/checks/saturation-scan.bat
    # Runtime skip: %SYS_DIR%\env\venv\Scripts\python.exe

    # _sys/tests/local-test.bat
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/start.bat",
        id="local_test_bat->_sys_start_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/context",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat line 29 references '_sys/context/*.bat' but _sys/context directory does not exist",
        ),
        id="local_test_bat->_sys_context",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/sandbox-test.bat",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat line 53 references '_sys/test/sandbox-test.bat' which does not exist in repo",
        ),
        id="local_test_bat->_sys_test_sandbox_test_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/run-sandbox-test.bat",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat line 54 references '_sys/test/run-sandbox-test.bat' but folder is '_sys/tests/'",
        ),
        id="local_test_bat->_sys_test_run_sandbox_test_bat",
    ),
    pytest.param(
        "_sys/tests/local-test.bat",
        "_sys/test/sandbox-unit-test.wsb",
        marks=pytest.mark.xfail(
            strict=True,
            reason="local-test.bat line 55 references '_sys/test/sandbox-unit-test.wsb' but folder is '_sys/tests/'",
        ),
        id="local_test_bat->_sys_test_sandbox_unit_test_wsb",
    ),

    # _sys/tests/run-sandbox-test.bat:
    # No literal _sys\... tokens (uses %~dp0... anchored in _sys/tests)

    # _sys/tests/run-tests.bat
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys",
        id="run_tests_bat->_sys",
    ),
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit",
        id="run_tests_bat->_sys_tests_unit",
    ),
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_system_lifecycle.py",
        id="run_tests_bat->_sys_tests_unit_test_system_lifecycle_py",
    ),
    pytest.param(
        "_sys/tests/run-tests.bat",
        "_sys/tests/unit/test_path_scenarios.py",
        id="run_tests_bat->_sys_tests_unit_test_path_scenarios_py",
    ),

    # _sys/tests/wsb-entry.bat
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/core/bootstrap.bat",
        id="wsb_entry_bat->_sys_core_bootstrap_bat",
    ),
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/tests/unit",
        id="wsb_entry_bat->_sys_tests_unit",
    ),
    pytest.param(
        "_sys/tests/wsb-entry.bat",
        "_sys/tests/lifecycle_tester.py",
        id="wsb_entry_bat->_sys_tests_lifecycle_tester_py",
    ),
]


# ---------------------------------------------------------------------------
# CONTRACT 1: Each listed script exists and is non-empty
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("script_rel", HARNESS_SCRIPTS)
def test_harness_script_exists_and_non_empty(script_rel):
    script_path = REPO_ROOT / script_rel
    assert script_path.is_file(), f"Harness script missing: {script_rel}"
    assert script_path.stat().st_size > 0, f"Harness script empty: {script_rel}"


# ---------------------------------------------------------------------------
# CONTRACT 2: Statically resolvable references point to existing repo targets
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("script_rel,target_rel", RESOLVABLE_REFERENCES)
def test_resolvable_references(script_rel, target_rel):
    script_path = REPO_ROOT / script_rel
    assert script_path.exists(), f"Source script {script_rel} must exist"

    # Verify that the script actually contains a reference to the target (or its stem/tail)
    content = script_path.read_text(encoding="utf-8", errors="replace")
    target_name = Path(target_rel).name
    assert target_name.lower() in content.lower(), (
        f"{script_rel} does not mention target {target_name}"
    )

    # Check whether the target actually exists in repo
    target_path = REPO_ROOT / target_rel
    assert target_path.exists(), f"Referenced path '{target_rel}' not found in repo"


# ---------------------------------------------------------------------------
# CONTRACT 3: .bat files contain no unresolvable static _sys-named paths
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bat_rel,token", BAT_SYS_TOKENS)
def test_bat_sys_token_exists(bat_rel, token):
    target = REPO_ROOT / token
    assert target.exists(), (
        f"Batch script {bat_rel} references static path '{token}' which does not exist in repo"
    )


def test_no_unaccounted_bat_sys_tokens():
    """Dynamically scan all .bat files with regex to ensure no unrecorded _sys tokens exist."""
    # Pattern to extract _sys/... tokens
    pattern = r"(?:[A-Za-z]:[\\/]|%[A-Za-z0-9_~]+%[\\/])?(_sys[\\/][A-Za-z0-9_.\-\\/]+)"

    # Set of known / explicitly tracked tokens (both valid and xfailed)
    known_tokens = {
        # Valid
        "_sys",
        "_sys/start.bat",
        "_sys/tests/unit",
        "_sys/tests/unit/test_system_lifecycle.py",
        "_sys/tests/unit/test_path_scenarios.py",
        "_sys/core/bootstrap.bat",
        "_sys/tests/lifecycle_tester.py",
        # Known breakages
        "_sys/context",
        "_sys/context/*.bat",
        "_sys/test/sandbox-test.bat",
        "_sys/test/run-sandbox-test.bat",
        "_sys/test/sandbox-unit-test.wsb",
    }

    for bat_rel in BAT_FILES:
        bat_path = REPO_ROOT / bat_rel
        content = bat_path.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(pattern, content, re.IGNORECASE)

        for m in matches:
            norm = m.replace("\\", "/").rstrip("/.")
            # Skip runtime paths
            if norm.startswith("_sys/env") or norm.startswith("_sys/data") or norm.startswith("_sys/tools"):
                continue
            # Must either exist on disk or be in known_tokens
            target = REPO_ROOT / norm
            assert target.exists() or norm in known_tokens, (
                f"Unaccounted broken _sys token found in {bat_rel}: '{norm}'"
            )
