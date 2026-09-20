"""test_engram_cmd_surface.py — Command-surface contract tests for engram.cmd (§3.2-§3.4).

Verifies the canonical command surface defined in the ratified spec:
- Every public verb and flag (§3.2)
- Every retired verb with rename guidance and exit code 2 (§3.4)
- Unknown command handling with exit code 2 and help guidance (§3.2 rule 5)
- Existing file/dir path routing to 'open' (§3.2 rule 4)
- The 'not set up' rule when python.exe is missing (§3.2)
- Literal '!' preservation in arguments forwarded across '%*'-boundaries in '&'-laden paths

Per the P1 ratified plan and terminal directive, forward-looking contract tests
that depend on the P1-7 rewrite are marked with:
"""
import os
import subprocess
from pathlib import Path
import pytest

from _sys.core.root import find_root

REPO_ROOT = find_root(__file__).parent
ENGRAM_CMD = REPO_ROOT / "engram.cmd"


@pytest.fixture
def surface_root(tmp_path: Path):
    """Fixture directory in an 'a&b!' path with stub dispatch.bat, python.exe, and version.json."""
    root = tmp_path / "a&b!"
    root.mkdir(parents=True, exist_ok=True)

    # Copy real engram.cmd from repo root
    assert ENGRAM_CMD.is_file(), f"engram.cmd not found at {ENGRAM_CMD}"
    (root / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")

    # Stub _sys/core/version.json
    core_dir = root / "_sys" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "version.json").write_text('{"version": "3.3.0"}', encoding="utf-8")

    # Stub _sys/core/dispatch.bat
    stub_dispatch = core_dir / "dispatch.bat"
    stub_dispatch.write_text(
        "@echo off\r\n"
        "echo DISPATCH_PIPELINE=%1\r\n"
        "echo DISPATCH_ARGS=%*\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    # Dummy python.exe so 'set up' condition holds by default
    py_dir = root / "_sys" / "env" / "python"
    py_dir.mkdir(parents=True, exist_ok=True)
    import sys, shutil
    shutil.copy(sys.executable, py_dir / "python.exe")
    
    state_dir = root / "_sys" / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "layout.json").write_text('{"layout_version": 2}', encoding="utf-8")

    return root


def run_engram(root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Helper to run engram.cmd inside root with reliable quote handling."""
    target_cwd = cwd or root
    cmd_file = root / "engram.cmd"
    quoted_args = " ".join(f'"{a}"' if (" " in a or "!" in a) else a for a in args)
    if quoted_args:
        cmd_line = f'cmd.exe /c ""{cmd_file}" {quoted_args}"'
    else:
        cmd_line = f'cmd.exe /c ""{cmd_file}""'

    return subprocess.run(
        cmd_line,
        cwd=str(target_cwd),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )


# ----------------------------------------------------------------------------
# 1. Public verbs and flags (§3.2)
# ----------------------------------------------------------------------------

def test_bare_invocation_routes_to_open(surface_root):
    """engram with no args routes to 'open' (§3.2 rule 1)."""
    proc = run_engram(surface_root)
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=start" in proc.stdout


@pytest.mark.parametrize("verb_args,expected_pipeline", [
    (["open"], "start"),
    (["open", "workspace"], "start"),
    (["update"], "update"),
    (["update", "--check"], "update"),
    (["update", "--yes"], "update"),
    (["update", "--only", "codex,peerhub"], "update"),
    (["doctor"], "doctor"),
    (["doctor", "--json"], "doctor"),
    (["menu"], "menu-status"),
    (["menu", "status"], "menu-status"),
    (["menu", "enable"], "menu-enable"),
    (["menu", "disable"], "menu-disable"),
    (["menu", "clean"], "menu-clean"),
    (["tidy"], "tidy"),
    (["tidy", "--apply"], "tidy"),
    (["tidy", "--deep"], "tidy"),
])
def test_public_verbs_dispatch(surface_root, verb_args, expected_pipeline):
    """Every §3.2 verb routes to its canonical dispatch pipeline."""
    proc = run_engram(surface_root, *verb_args)
    assert proc.returncode == 0, f"Failed for {verb_args}: rc={proc.returncode}, out={proc.stdout}"
    assert f"DISPATCH_PIPELINE={expected_pipeline}" in proc.stdout


@pytest.mark.parametrize("uninstall_args", [
    ["uninstall"],
    ["uninstall", "--yes"],
    ["uninstall", "--purge-data"],
])
def test_uninstall_dispatches_cleanly(surface_root, uninstall_args):
    """'engram uninstall' routes to the uninstall pipeline (wired in P0-1)."""
    proc = run_engram(surface_root, *uninstall_args)
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=uninstall" in proc.stdout


@pytest.mark.parametrize("version_flag", ["version", "--version", "-v"])
def test_version_surface(surface_root, version_flag):
    """'engram version', '--version', '-v' output 'Engram <version> (Portable Dev Runtime)' without 'v' prefix (§3.2, §3.3)."""
    proc = run_engram(surface_root, version_flag)
    assert proc.returncode == 0
    # §3.3 strictly specifies "Engram <version> (Portable Dev Runtime)" without 'v' prefix
    assert "Engram 3.3.0 (" in proc.stdout


@pytest.mark.parametrize("help_flag", ["help", "--help", "-h", "/?"])
def test_help_surface_clean(surface_root, help_flag):
    """'engram help' lists canonical §3.2 verbs with no mention of P: or legacy batch files."""
    proc = run_engram(surface_root, help_flag)
    assert proc.returncode == 0
    # Canonical verbs listed
    assert "engram open" in proc.stdout
    assert "engram update" in proc.stdout
    assert "engram doctor" in proc.stdout
    assert "engram menu" in proc.stdout
    assert "engram tidy" in proc.stdout
    assert "engram uninstall" in proc.stdout
    # No legacy host artifacts
    assert "P:" not in proc.stdout
    assert "SUBST" not in proc.stdout
    assert ".bat" not in proc.stdout.lower()


# ----------------------------------------------------------------------------
# 2. Retired verbs (§3.4)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("retired_verb,recommended_replacement", [
    ("install", "engram"),
    ("setup", "engram"),
    ("status", "engram doctor"),
    ("register", "engram menu enable"),
    ("unregister", "engram menu disable"),
    ("menu-cleanup", "engram menu clean"),
    ("cleanup", "engram tidy"),
    ("launch", "engram open"),
    ("start", "engram open"),
])
def test_retired_verbs_exit_2_with_guidance(surface_root, retired_verb, recommended_replacement):
    """Retired verbs exit 2 and print replacement guidance (§3.4)."""
    proc = run_engram(surface_root, retired_verb)
    assert proc.returncode == 2, f"Expected exit code 2 for retired verb '{retired_verb}', got {proc.returncode}"
    assert f"'{retired_verb}'" in proc.stdout or f"engram {retired_verb}" in proc.stdout
    assert recommended_replacement in proc.stdout


# ----------------------------------------------------------------------------
# 3. Unknown command (§3.2 rule 5)
# ----------------------------------------------------------------------------

def test_unknown_command_exits_2(surface_root):
    """Unknown command exits 2 and directs user to 'engram help' (§3.2 rule 5)."""
    proc = run_engram(surface_root, "totally_unknown_subcmd_xyz")
    assert proc.returncode == 2, f"Expected exit code 2 for unknown command, got {proc.returncode}"
    assert "Unknown command: totally_unknown_subcmd_xyz" in proc.stdout
    assert "Run 'engram help'" in proc.stdout


# ----------------------------------------------------------------------------
# 4. Existing path routes to open (§3.2 rule 4)
# ----------------------------------------------------------------------------

def test_existing_path_routes_to_open(surface_root):
    """First arg matching an existing directory routes to open <path> (§3.2 rule 4)."""
    proj_dir = surface_root / "my_project"
    proj_dir.mkdir()

    proc = run_engram(surface_root, "my_project")
    assert proc.returncode == 0
    # Must route to start pipeline with that path, not dispatch a pipeline named 'my_project'
    assert "DISPATCH_PIPELINE=start" in proc.stdout


def test_verb_name_directory_still_runs_the_verb(surface_root):
    """A directory literally named like a verb runs the verb, not 'open' on
    that directory -- verb matching (rule 2) takes priority over the
    existing-path fallback (rule 4). Accessing such a folder requires the
    explicit 'engram open <name>' (§3.2)."""
    verb_dir = surface_root / "update"
    verb_dir.mkdir()

    proc = run_engram(surface_root, "update")
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=update" in proc.stdout


# ----------------------------------------------------------------------------
# 5. The 'Not set up' rule (§3.2)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("verb", ["doctor", "menu", "tidy", "uninstall"])
def test_not_set_up_rule_rejects_with_exit_1(surface_root, verb):
    """When python.exe is missing, doctor/menu/tidy/uninstall exit 1 with setup message (§3.2)."""
    # Remove python stub to simulate fresh/not-set-up environment
    py_exe = surface_root / "_sys" / "env" / "python" / "python.exe"
    if py_exe.exists():
        py_exe.unlink()

    proc = run_engram(surface_root, verb)
    assert proc.returncode == 1
    assert "Engram is not set up" in proc.stdout
    assert "Run 'engram'" in proc.stdout


# ----------------------------------------------------------------------------
# 6. Literal '!' preservation across forwarding
# ----------------------------------------------------------------------------

def test_literal_exclamation_preserved_in_open(surface_root):
    """Literal '!' in arguments is preserved in an 'a&b!' directory (§3.1)."""
    proc = run_engram(surface_root, "open", "file!name.txt")
    assert proc.returncode == 0
    assert "file!name.txt" in proc.stdout


# ----------------------------------------------------------------------------
# 7. Renamed system directory discovery (§2)
# ----------------------------------------------------------------------------

def test_renamed_sys_dir_routes_commands_correctly(tmp_path: Path):
    """When _sys is renamed (e.g. 'my_runtime'), engram.cmd discovers it via Tier 3 and routes commands."""
    root = tmp_path / "renamed_inst"
    root.mkdir(parents=True, exist_ok=True)

    # Copy real engram.cmd
    (root / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")

    # Create renamed system folder (NO _sys folder at all)
    sys_dir = root / "my_runtime"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "version.json").write_text('{"version": "4.1.0"}', encoding="utf-8")
    stub_dispatch = core_dir / "dispatch.bat"
    stub_dispatch.write_text(
        "@echo off\r\n"
        "echo DISPATCH_PIPELINE=%1\r\n"
        "echo DISPATCH_ARGS=%*\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    py_dir = sys_dir / "env" / "python"
    py_dir.mkdir(parents=True, exist_ok=True)
    import sys as _sys_mod, shutil
    shutil.copy(_sys_mod.executable, py_dir / "python.exe")

    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "layout.json").write_text('{"layout_version": 2}', encoding="utf-8")

    # 1. Test version query discovers my_runtime/core/version.json
    proc = run_engram(root, "version")
    assert proc.returncode == 0
    assert "4.1.0" in proc.stdout

    # 2. Test doctor routing
    proc = run_engram(root, "doctor")
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=doctor" in proc.stdout

    # 3. Test open routing
    proc = run_engram(root)
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=start" in proc.stdout


def test_renamed_sys_dir_env_var_override(tmp_path: Path, monkeypatch):
    """When ENGRAM_SYS_DIR is set (Tier 1), engram.cmd routes to the specified sys directory."""
    root = tmp_path / "override_inst"
    root.mkdir(parents=True, exist_ok=True)

    (root / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")

    for name, marker in [("runtime_a", "TARGET_A"), ("runtime_b", "TARGET_B")]:
        core_dir = root / name / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "dispatch.bat").write_text(
            f"@echo off\r\necho DISPATCH_PIPELINE=%1\r\necho {marker}\r\nexit /b 0\r\n",
            encoding="utf-8",
        )
        py_dir = root / name / "env" / "python"
        py_dir.mkdir(parents=True, exist_ok=True)
        import sys as _sys_mod, shutil
        shutil.copy(_sys_mod.executable, py_dir / "python.exe")
        state_dir = root / name / "data" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "layout.json").write_text('{"layout_version": 2}', encoding="utf-8")

    # Explicitly select runtime_b via environment variable
    cmd_file = root / "engram.cmd"
    cmd_line = f'cmd.exe /c ""{cmd_file}" doctor"'
    env = os.environ.copy()
    env["ENGRAM_SYS_DIR"] = "runtime_b"

    proc = subprocess.run(
        cmd_line,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
        env=env,
    )
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=doctor" in proc.stdout
    assert "TARGET_B" in proc.stdout


# ----------------------------------------------------------------------------
# 8. Root entrypoint forwarding for backup, restore, reset (L-5)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("verb_args,expected_pipeline,expected_args", [
    (["backup"], "backup", "backup"),
    (["backup", "--out", "x.zip"], "backup", "backup --out x.zip"),
    (["restore", "x.zip"], "restore", "restore x.zip"),
    (["restore", "x.zip", "--force"], "restore", "restore x.zip --force"),
    (["reset"], "reset", "reset"),
    (["reset", "--yes"], "reset", "reset --yes"),
])
def test_backup_restore_reset_forwarding(surface_root, verb_args, expected_pipeline, expected_args):
    """engram.cmd backup, restore, reset forward args to matching dispatch pipelines (audit finding L-5)."""
    proc = run_engram(surface_root, *verb_args)
    assert proc.returncode == 0, f"Failed for {verb_args}: rc={proc.returncode}, out={proc.stdout}"
    assert f"DISPATCH_PIPELINE={expected_pipeline}" in proc.stdout
    assert f"DISPATCH_ARGS={expected_args}" in proc.stdout


