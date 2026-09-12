"""
Unit tests for Engram.exe wrapper (§3.1 and §10 P0-2).

Scenarios tested:
1. Compilation via build_exe.py (skips gracefully if csc.exe unavailable).
2. Arguments with spaces, '!', '&', trailing backslash, and embedded quotes arrive intact.
3. Exit code propagation (e.g. exit 7).
4. v3.2.7-only special case: with no args and _sys/env/python/python.exe absent, forwards 'install'.
5. When _sys/env/python/python.exe exists and no args given, runs with no extra args.
6. Missing engram.cmd displays 'engram.cmd not found next to <path>' and exits 1.
7. Invocation through a file symlink resolves final target directory and finds engram.cmd.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

_SYS_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = _SYS_DIR.parent

if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))
if str(REPO_ROOT / "tools" / "winget") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "winget"))


def _find_csc() -> str | None:
    """Check for csc.exe on PATH or standard Framework directories."""
    import shutil
    csc = shutil.which("csc.exe") or shutil.which("csc")
    if csc:
        return csc
    candidates = [
        r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


@pytest.fixture(scope="module")
def csc_compiler():
    csc = _find_csc()
    if not csc:
        pytest.skip("csc.exe compiler genuinely unavailable on this machine")
    return csc


@pytest.fixture
def built_engram_exe(tmp_path, csc_compiler):
    """Build Engram.exe into a directory with special characters ('a&b!c')."""
    special_dir = tmp_path / "a&b!c"
    special_dir.mkdir(parents=True, exist_ok=True)
    out_exe = special_dir / "Engram.exe"

    # Try importing tools/winget/build_exe.py
    try:
        from build_exe import build_wrapper_exe
        rc = build_wrapper_exe(output_path=out_exe)
        assert rc == 0, f"build_wrapper_exe returned {rc}"
    except ImportError:
        # If build_exe.py not implemented yet, compile directly to test wrapper.cs or fail
        wrapper_cs = REPO_ROOT / "tools" / "winget" / "wrapper.cs"
        if not wrapper_cs.exists():
            wrapper_cs = REPO_ROOT / "wrapper.cs"
        cmd = [csc_compiler, "/target:exe", "/optimize+", f"/out:{out_exe}", str(wrapper_cs)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            pytest.fail(f"csc compilation failed: {res.stderr}")

    assert out_exe.exists(), "Engram.exe was not built"
    return special_dir, out_exe


def test_build_exe_module_exists():
    """tools/winget/build_exe.py must exist and be importable."""
    build_exe_path = REPO_ROOT / "tools" / "winget" / "build_exe.py"
    assert build_exe_path.exists(), "tools/winget/build_exe.py must exist"
    from build_exe import find_csc, build_wrapper_exe
    assert find_csc() is not None, "find_csc() must find available csc.exe"


def test_wrapper_cs_moved_to_tools_winget():
    """wrapper.cs must be at tools/winget/wrapper.cs per §3.5, and deleted from root."""
    assert (REPO_ROOT / "tools" / "winget" / "wrapper.cs").exists()
    assert not (REPO_ROOT / "wrapper.cs").exists()


def test_args_forwarding_and_exit_code_propagation(built_engram_exe):
    """Engram.exe forwards spaces, '!', '&', trailing backslash, embedded quotes and exit code 7."""
    special_dir, exe_path = built_engram_exe

    stub_cmd = special_dir / "engram.cmd"
    stub_cmd.write_text(
        "@echo off\r\n"
        "echo ARGS=%*\r\n"
        "exit /b 7\r\n",
        encoding="utf-8"
    )

    args = [
        "simple",
        "with spaces",
        "excl!mark",
        "amp&persand",
        "trailing\\",
        "embed\"quote",
    ]

    proc = subprocess.run([str(exe_path)] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert proc.returncode == 7, f"Expected exit code 7, got {proc.returncode}. Output: {proc.stdout} {proc.stderr}"
    assert "ARGS=" in proc.stdout
    assert "simple" in proc.stdout
    assert '"with spaces"' in proc.stdout
    assert '"excl!mark"' in proc.stdout
    assert '"amp&persand"' in proc.stdout
    assert "trailing\\" in proc.stdout
    assert '"embed\\"quote"' in proc.stdout


def test_double_click_install_special_case_v327(built_engram_exe):
    """When called with no args and _sys/env/python/python.exe absent, forwards 'install'."""
    special_dir, exe_path = built_engram_exe

    stub_cmd = special_dir / "engram.cmd"
    stub_cmd.write_text(
        "@echo off\r\n"
        "echo CALLED_WITH=%*\r\n"
        "exit /b 0\r\n",
        encoding="utf-8"
    )

    # Ensure python.exe does NOT exist
    py_path = special_dir / "_sys" / "env" / "python" / "python.exe"
    if py_path.exists():
        py_path.unlink()

    proc = subprocess.run([str(exe_path)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    assert "CALLED_WITH=install" in proc.stdout


def test_double_click_when_python_present(built_engram_exe):
    """When called with no args and python.exe exists, runs without extra args."""
    special_dir, exe_path = built_engram_exe

    stub_cmd = special_dir / "engram.cmd"
    stub_cmd.write_text(
        "@echo off\r\n"
        "echo CALLED_WITH=[%*]\r\n"
        "exit /b 0\r\n",
        encoding="utf-8"
    )

    py_dir = special_dir / "_sys" / "env" / "python"
    py_dir.mkdir(parents=True, exist_ok=True)
    py_path = py_dir / "python.exe"
    py_path.write_text("dummy", encoding="utf-8")

    proc = subprocess.run([str(exe_path)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    assert "CALLED_WITH=[]" in proc.stdout


def test_missing_engram_cmd_error(built_engram_exe):
    """When engram.cmd is missing next to Engram.exe, print error and exit 1."""
    special_dir, exe_path = built_engram_exe
    stub_cmd = special_dir / "engram.cmd"
    if stub_cmd.exists():
        stub_cmd.unlink()

    proc = subprocess.run([str(exe_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 1
    combined = proc.stdout + proc.stderr
    assert "engram.cmd not found next to" in combined.lower()


def test_symlink_resolution_to_target_directory(tmp_path, built_engram_exe):
    """Invocation through a symlink resolves to target dir and finds target's engram.cmd."""
    special_dir, real_exe = built_engram_exe

    stub_cmd = special_dir / "engram.cmd"
    stub_cmd.write_text(
        "@echo off\r\n"
        "echo REAL_CMD_EXECUTED\r\n"
        "exit /b 42\r\n",
        encoding="utf-8"
    )

    symlink_dir = tmp_path / "links_dir"
    symlink_dir.mkdir(parents=True, exist_ok=True)
    link_exe = symlink_dir / "engram.exe"

    try:
        os.symlink(str(real_exe), str(link_exe))
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"Creating file symlink not permitted on this host: {e}")

    # symlink_dir does NOT contain engram.cmd
    assert not (symlink_dir / "engram.cmd").exists()

    proc = subprocess.run([str(link_exe)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 42
    assert "REAL_CMD_EXECUTED" in proc.stdout
