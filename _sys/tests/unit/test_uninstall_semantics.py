import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

_SYS_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = _SYS_DIR.parent

if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))


def _get_dummy_exited_pid():
    """Return a PID of a process that has already exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


@pytest.fixture
def uninstall_fixture(tmp_path):
    """Full realistic Engram directory fixture with data, legacy files, and program files."""
    base_dir = tmp_path / "engram_test_inst"
    base_dir.mkdir(parents=True, exist_ok=True)
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir(parents=True, exist_ok=True)

    # 1. User data to preserve by default
    engram_dir = base_dir / ".engram"
    (engram_dir / "claude").mkdir(parents=True, exist_ok=True)
    (engram_dir / "claude" / ".credentials.json").write_text('{"token": "secret123"}', encoding="utf-8")
    (engram_dir / "codex").mkdir(parents=True, exist_ok=True)
    (engram_dir / "codex" / "auth.json").write_text('{"auth": "token456"}', encoding="utf-8")
    (engram_dir / "gh").mkdir(parents=True, exist_ok=True)
    (engram_dir / "gh" / "hosts.yml").write_text("github.com:\n  user: test", encoding="utf-8")
    (engram_dir / "nested" / "dir").mkdir(parents=True, exist_ok=True)
    (engram_dir / "nested" / "dir" / "state.txt").write_text("nested state", encoding="utf-8")

    workspace_dir = base_dir / "workspace"
    (workspace_dir / "proj" / ".peerhub").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "proj" / ".peerhub" / "peerhub.sqlite3").write_text("fake sqlite content", encoding="utf-8")
    (workspace_dir / "proj" / "main.py").write_text("print('hello')", encoding="utf-8")

    # Unknown user files at root
    (base_dir / "notes.txt").write_text("important user notes", encoding="utf-8")

    # Legacy _sys items that must be kept
    (sys_dir / "claude" / "config").mkdir(parents=True, exist_ok=True)
    (sys_dir / "claude" / "config" / "x.json").write_text('{"legacy": true}', encoding="utf-8")

    # User-authored config under _sys that must be kept
    (sys_dir / "local.config.bat").write_text("set CUSTOM_VAR=1", encoding="utf-8")

    # 2. Shipped root program files
    (base_dir / "Engram.exe").write_text("fake exe", encoding="utf-8")
    (base_dir / "engram.cmd").write_text("fake cmd", encoding="utf-8")
    (base_dir / "README.md").write_text("# Engram", encoding="utf-8")
    (base_dir / "LICENSE").write_text("MIT", encoding="utf-8")
    (base_dir / "UPDATE.bat").write_text("fake bat", encoding="utf-8")
    (base_dir / "wrapper.cs").write_text("// cs", encoding="utf-8")
    (base_dir / "CONVENTION.md").write_text("convention", encoding="utf-8")

    # 3. Shipped _sys program directories and files (v3.2.7 constant set)
    for d in ["checks", "cli", "config", "core", "data", "docs", "env", "tests", "tools"]:
        (sys_dir / d).mkdir(parents=True, exist_ok=True)
        (sys_dir / d / "sample.txt").write_text(f"content of {d}", encoding="utf-8")

    # Specific nested files to simulate real tree
    (sys_dir / "env" / "python").mkdir(parents=True, exist_ok=True)
    (sys_dir / "env" / "python" / "python.exe").write_text("fake py", encoding="utf-8")
    (sys_dir / "tools" / "rg").mkdir(parents=True, exist_ok=True)
    (sys_dir / "tools" / "rg" / "rg.exe").write_text("fake rg", encoding="utf-8")

    for f in [
        "context_menu.json", "dispatch.json", "env.json", "local.config.bat.template",
        "managed-links.json", "paths.json", "runtimes.json", "start.bat", "tool-catalog.v1.json"
    ]:
        (sys_dir / f).write_text(f'{{"file": "{f}"}}', encoding="utf-8")

    localappdata = tmp_path / "localappdata"
    localappdata.mkdir(parents=True, exist_ok=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    ctx = {
        "base_dir": base_dir,
        "sys_dir": sys_dir,
        "paths": {
            "state": state_dir,
            "generated": sys_dir / "data" / "generated",
            "localappdata": localappdata,
        },
        "args": [],
        "state": {},
    }
    return ctx, localappdata, temp_dir


def _build_dir_manifest(dir_path: Path) -> dict:
    manifest = {}
    if not dir_path.exists():
        return manifest
    for root, _, files in os.walk(dir_path):
        for f in files:
            p = Path(root) / f
            rel = str(p.relative_to(dir_path)).replace("\\", "/")
            manifest[rel] = p.read_bytes()
    return manifest


# =============================================================================
# Shape tests: PowerShell helper & dispatch pipeline
# =============================================================================

def test_uninstall_happy_path(uninstall_fixture):
    """Test uninstall handoff writes plan.json and spawns PowerShell helper."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--yes"]

    from core.uninstaller import run

    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(0)
        mock_popen.assert_called_once()

        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "powershell.exe"
        assert "-NoProfile" in call_args
        assert "-NonInteractive" in call_args
        assert "-ExecutionPolicy" in call_args
        assert "Bypass" in call_args
        assert "-File" in call_args
        assert "-PlanPath" in call_args

        plan_path_idx = call_args.index("-PlanPath") + 1
        plan_file = Path(call_args[plan_path_idx])
        assert plan_file.exists()
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))

        assert "targets" in plan_data
        assert "base_dir" in plan_data
        assert "journal_path" in plan_data
        assert "parent_pid" in plan_data

        journal_file = Path(plan_data["journal_path"])
        assert journal_file.exists()
        journal = json.loads(journal_file.read_text(encoding="utf-8"))
        assert journal["operation"] == "uninstall"
        assert journal["status"] == "IN_PROGRESS"


def test_uninstall_registered_branch(uninstall_fixture):
    """If registered, uninstaller calls registrar.remove but NOT virtualizer.unmount."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--yes"]

    # Mark as registered
    (ctx["paths"]["state"] / "register.state.json").write_text("{}", encoding="utf-8")

    from core.uninstaller import run

    with patch("subprocess.Popen"), \
         patch("sys.exit", side_effect=SystemExit), \
         patch("core.registrar.remove") as mock_remove, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_remove.assert_called_once_with(ctx)
        # Verify virtualizer is not used in v3.2.7 uninstaller
        assert not hasattr(sys.modules.get("core.uninstaller"), "unmount")


def test_uninstall_failure_path(uninstall_fixture):
    """If registrar.remove fails, journal records FAILED_RECOVERABLE and exits 1."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--yes"]

    (ctx["paths"]["state"] / "register.state.json").write_text("{}", encoding="utf-8")

    from core.uninstaller import run

    with patch("core.registrar.remove", side_effect=Exception("registry remove failed")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(1)
        mock_popen.assert_not_called()


# =============================================================================
# Ratified §6.2 Cases 1-7
# =============================================================================

def test_case_1_default_uninstall_preserves_data_with_yes(uninstall_fixture):
    """Case 1: Default uninstall with --yes.
    Manifests of .engram/, workspace/ and _sys/claude/ are byte-identical;
    every planned program path is gone; root still exists.
    Real powershell.exe runs with parent wait bypassed.
    """
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--yes"]
    base_dir = ctx["base_dir"]

    manifest_engram_before = _build_dir_manifest(base_dir / ".engram")
    manifest_workspace_before = _build_dir_manifest(base_dir / "workspace")
    manifest_legacy_sys_before = _build_dir_manifest(base_dir / "_sys" / "claude")

    exited_pid = _get_dummy_exited_pid()

    from core.uninstaller import run

    real_popen = subprocess.Popen
    spawned_procs = []

    def capturing_popen(*args, **kwargs):
        p = real_popen(*args, **kwargs)
        spawned_procs.append(p)
        return p

    with patch("os.getpid", return_value=exited_pid), \
         patch("subprocess.Popen", side_effect=capturing_popen), \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(0)

    for p in spawned_procs:
        p.wait(timeout=30)
        assert p.returncode == 0

    manifest_engram_after = _build_dir_manifest(base_dir / ".engram")
    manifest_workspace_after = _build_dir_manifest(base_dir / "workspace")
    manifest_legacy_sys_after = _build_dir_manifest(base_dir / "_sys" / "claude")

    assert manifest_engram_after == manifest_engram_before, ".engram bytes must be identical"
    assert manifest_workspace_after == manifest_workspace_before, "workspace bytes must be identical"
    assert manifest_legacy_sys_after == manifest_legacy_sys_before, "_sys/claude bytes must be identical"

    # local.config.bat and notes.txt must also be kept
    assert (base_dir / "_sys" / "local.config.bat").exists()
    assert (base_dir / "notes.txt").exists()

    # Program files must be gone
    assert not (base_dir / "Engram.exe").exists()
    assert not (base_dir / "engram.cmd").exists()
    assert not (base_dir / "README.md").exists()
    assert not (base_dir / "LICENSE").exists()
    assert not (base_dir / "UPDATE.bat").exists()
    assert not (base_dir / "_sys" / "checks").exists()
    assert not (base_dir / "_sys" / "env").exists()
    assert not (base_dir / "_sys" / "tools").exists()
    assert not (base_dir / "_sys" / "runtimes.json").exists()

    # Base dir still exists because kept data remains
    assert base_dir.exists()


def test_case_2_default_uninstall_declined_at_prompt(uninstall_fixture):
    """Case 2: Default uninstall with stdin 'n': nothing is deleted, exit 3."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = []
    base_dir = ctx["base_dir"]

    from core.uninstaller import run

    with patch("sys.stdin", io.StringIO("n\n")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(3)
        mock_popen.assert_not_called()

    # Nothing deleted
    assert (base_dir / "Engram.exe").exists()
    assert (base_dir / ".engram").exists()
    assert (base_dir / "workspace").exists()


def test_case_3_purge_data_with_matching_name_confirmation(uninstall_fixture):
    """Case 3: --purge-data --yes with stdin = correct folder name:
    .engram/ and workspace/ are deleted; unknown notes.txt at root is kept.
    """
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--purge-data", "--yes"]
    base_dir = ctx["base_dir"]

    exited_pid = _get_dummy_exited_pid()

    from core.uninstaller import run

    real_popen = subprocess.Popen
    spawned_procs = []

    def capturing_popen(*args, **kwargs):
        p = real_popen(*args, **kwargs)
        spawned_procs.append(p)
        return p

    # Feed exact base directory name
    stdin_input = f"{base_dir.name}\n"

    with patch("sys.stdin", io.StringIO(stdin_input)), \
         patch("os.getpid", return_value=exited_pid), \
         patch("subprocess.Popen", side_effect=capturing_popen), \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(0)

    for p in spawned_procs:
        p.wait(timeout=30)
        assert p.returncode == 0

    # Data directories are gone
    assert not (base_dir / ".engram").exists()
    assert not (base_dir / "workspace").exists()

    # Unknown file at root is kept
    assert (base_dir / "notes.txt").exists()
    assert (base_dir / "notes.txt").read_text(encoding="utf-8") == "important user notes"


def test_case_4_purge_data_with_mismatched_name_or_eof(uninstall_fixture):
    """Case 4: --purge-data --yes with wrong name or EOF: nothing deleted, exit 3."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--purge-data", "--yes"]
    base_dir = ctx["base_dir"]

    from core.uninstaller import run

    # 1. Wrong name
    with patch("sys.stdin", io.StringIO("wrong_folder_name\n")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(3)
        mock_popen.assert_not_called()

    # 2. EOF
    with patch("sys.stdin", io.StringIO("")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(3)
        mock_popen.assert_not_called()

    # Verify nothing was deleted
    assert (base_dir / "Engram.exe").exists()
    assert (base_dir / ".engram").exists()
    assert (base_dir / "workspace").exists()


def test_case_5_junction_under_delete_target_refused(uninstall_fixture, tmp_path):
    """Case 5: A junction planted at _sys/env/link -> outside: refused, exit 1, outside untouched."""
    ctx, localappdata, temp_dir = uninstall_fixture
    ctx["args"] = ["--yes"]
    base_dir = ctx["base_dir"]

    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("critical outside data", encoding="utf-8")

    link_target = base_dir / "_sys" / "env" / "link"
    try:
        # Create junction using _winapi if available
        import _winapi
        _winapi.CreateJunction(str(outside_dir), str(link_target))
    except Exception:
        # Fallback to mklink /J
        res = subprocess.run(f'cmd.exe /c mklink /J "{link_target}" "{outside_dir}"', shell=True, capture_output=True)
        if res.returncode != 0:
            pytest.skip("Could not create junction on this host/filesystem")

    from core.uninstaller import run

    with patch("subprocess.Popen") as mock_popen, \
         patch("sys.exit", side_effect=SystemExit) as mock_exit, \
         patch.dict(os.environ, {"LOCALAPPDATA": str(localappdata), "TEMP": str(temp_dir)}):

        with pytest.raises(SystemExit):
            run(ctx)

        mock_exit.assert_called_once_with(1)
        mock_popen.assert_not_called()

    # Outside untouched
    assert outside_file.exists()
    assert outside_file.read_text(encoding="utf-8") == "critical outside data"


def test_case_6_powershell_helper_in_ampersand_and_special_chars_dir(tmp_path):
    """Case 6: Paths tmp_path/'a&b!c%d': helper completes cleanly without batch/cmd parsing errors."""
    special_dir = tmp_path / "a&b!c%d"
    special_dir.mkdir(parents=True, exist_ok=True)

    target_file = special_dir / "file_to_remove.txt"
    target_file.write_text("delete me", encoding="utf-8")

    keep_file = special_dir / "keep_me.txt"
    keep_file.write_text("keep me", encoding="utf-8")

    journal_dir = tmp_path / "journal_special"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "journal.json"
    journal_path.write_text(json.dumps({
        "operation": "uninstall",
        "status": "IN_PROGRESS",
        "steps": [],
        "error_recoverable": False
    }), encoding="utf-8")

    plan_path = special_dir / "plan.json"
    exited_pid = _get_dummy_exited_pid()
    plan_path.write_text(json.dumps({
        "targets": [str(target_file)],
        "base_dir": str(special_dir),
        "sys_dir": str(special_dir / "_sys"),
        "journal_path": str(journal_path),
        "parent_pid": exited_pid
    }), encoding="utf-8")

    helper_source = _SYS_DIR / "core" / "uninstall_helper.ps1"
    assert helper_source.exists(), "uninstall_helper.ps1 must exist in _sys/core"

    helper_copy = special_dir / "uninstall_helper.ps1"
    helper_copy.write_text(helper_source.read_text(encoding="utf-8"), encoding="utf-8")

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", str(helper_copy),
        "-PlanPath", str(plan_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, f"Helper failed with stderr: {proc.stderr}\nstdout: {proc.stdout}"

    assert not target_file.exists(), "Target file must be removed"
    assert keep_file.exists(), "Keep file must remain"

    journal_data = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal_data["status"] == "COMPLETED"


def test_case_7_engram_cmd_uninstall_forwards_arguments(tmp_path):
    """Case 7: engram.cmd uninstall --yes reaches dispatch.bat with its args."""
    engram_cmd_src = REPO_ROOT / "engram.cmd"
    content = engram_cmd_src.read_text(encoding="utf-8")

    fixture_dir = tmp_path / "engram_cmd_test"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    engram_cmd_copy = fixture_dir / "engram.cmd"
    engram_cmd_copy.write_text(content, encoding="utf-8")

    # Create stub _sys/core/dispatch.bat
    core_dir = fixture_dir / "_sys" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    stub_dispatch = core_dir / "dispatch.bat"
    stub_dispatch.write_text(
        "@echo off\r\necho DISPATCH_CALLED\r\necho ARGS=%*\r\nexit /b 0\r\n",
        encoding="utf-8"
    )

    proc = subprocess.run(
        ["cmd.exe", "/c", str(engram_cmd_copy), "uninstall", "--yes", "--purge-data"],
        cwd=str(fixture_dir),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace"
    )
    if "&" in str(engram_cmd_copy) and "DISPATCH_CALLED" not in proc.stdout:
        proc = subprocess.run(
            f'cmd.exe /c ""{engram_cmd_copy}" uninstall --yes --purge-data"',
            cwd=str(fixture_dir),
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace"
        )

    assert "DISPATCH_CALLED" in proc.stdout, (
        f"Expected dispatch.bat to be invoked by engram.cmd uninstall.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert "uninstall --yes --purge-data" in proc.stdout, (
        f"Expected arguments to be forwarded.\nstdout: {proc.stdout}"
    )
