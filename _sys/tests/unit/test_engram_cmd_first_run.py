"""test_engram_cmd_first_run.py — First-run flow tests for engram.cmd."""
import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ENGRAM_CMD = REPO_ROOT / "engram.cmd"

@pytest.fixture
def first_run_root(tmp_path: Path):
    """Fixture directory for first-run tests without python.exe."""
    # Note: Use a path with literal '&' to prove it handles special chars well
    root = tmp_path / "a&b!"
    root.mkdir(parents=True, exist_ok=True)

    # Copy real engram.cmd
    (root / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")

    # Stub bootstrap.bat
    core_dir = root / "_sys" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "bootstrap.bat").write_text(
        "@echo off\r\n"
        "echo BOOTSTRAP_RUN\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )

    # Stub dispatch.bat
    (core_dir / "dispatch.bat").write_text(
        "@echo off\r\n"
        "echo DISPATCH_PIPELINE=%1\r\n"
        "echo CWD_ENV=\"%ENGRAM_CALLER_CWD%\"\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    
    # We do NOT create python.exe to trigger the first-run flow
    
    return root

def run_engram_interactive(root: Path, *args: str, input_text: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess:
    target_cwd = cwd or root
    cmd_file = root / "engram.cmd"
    quoted_args = " ".join(f'"{a}"' if (" " in a or "!" in a) else a for a in args)
    if quoted_args:
        cmd_line = f'cmd.exe /c ""{cmd_file}" {quoted_args}"'
    else:
        cmd_line = f'cmd.exe /c ""{cmd_file}""'

    # Use a temporary file for stdin because cmd.exe's set /p drops subsequent lines
    # when reading from an unseekable pipe due to internal buffering.
    stdin_file = target_cwd / "stdin.txt"
    stdin_file.write_text(input_text.replace('\n', '\r\n'), encoding="utf-8")
    
    with open(stdin_file, "r", encoding="utf-8") as f:
        return subprocess.run(
            cmd_line,
            stdin=f,
            cwd=str(target_cwd),
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
        )

def test_first_run_declined(first_run_root):
    proc = run_engram_interactive(first_run_root, input_text="n\n")
    assert proc.returncode == 1
    assert "workspace" not in [p.name for p in first_run_root.iterdir()]
    assert "BOOTSTRAP_RUN" not in proc.stdout

def test_first_run_accepted(first_run_root):
    proc = run_engram_interactive(first_run_root, input_text="y\nn\n")
    assert proc.returncode == 0
    assert "BOOTSTRAP_RUN" in proc.stdout
    assert (first_run_root / "workspace").is_dir()
    assert "DISPATCH_PIPELINE=start" in proc.stdout

def test_first_run_accept_menu(first_run_root):
    proc = run_engram_interactive(first_run_root, input_text="y\ny\n")
    assert proc.returncode == 0
    assert "DISPATCH_PIPELINE=menu-enable" in proc.stdout
    assert "DISPATCH_PIPELINE=start" in proc.stdout

def test_caller_cwd_is_captured(first_run_root, tmp_path):
    caller_dir = tmp_path / "caller_dir"
    caller_dir.mkdir()
    proc = run_engram_interactive(first_run_root, input_text="\n\n", cwd=caller_dir)
    assert proc.returncode == 0
    assert "BOOTSTRAP_RUN" in proc.stdout
    assert "DISPATCH_PIPELINE=start" in proc.stdout
    assert f"CWD_ENV=\"{caller_dir}\"" in proc.stdout
