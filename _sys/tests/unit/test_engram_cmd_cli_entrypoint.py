"""Regression tests for top-level engram.cmd CLI entrypoint in '&'-laden paths.

Covers commit 040618d (the goto-based fallback-dispatch redesign):
- Test A: baseline correctness for the :cmd_unknown branch (exit 1, correct
  message) in a directory containing literal '&'. This branch was never
  inside a parenthesized block in any historical version of engram.cmd, so
  it would NOT have caught the parenthesized-%ERRORLEVEL% regression --
  verified empirically against commits 857d381 and 023e5b4, both of which
  already passed this exact assertion. It's a smoke test for the fallback
  path, not a regression guard for that specific bug.
- Test B: this IS the real regression guard, verified empirically against
  both historical bugs it exists to catch: against 857d381 (pre-fix), the
  dispatch.bat stub's real `exit /b 7` was lost -- observed returncode 0,
  proving the parenthesized-%ERRORLEVEL% bug. Against 023e5b4 (fixed
  ERRORLEVEL via enabledelayedexpansion, but as a side effect), the
  forwarded "file!name.txt" argument was observed corrupted to
  "filename.txt". Only 040618d's goto-based redesign passes both
  assertions simultaneously.
"""
import subprocess
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
ENGRAM_CMD_SOURCE = REPO_ROOT / "engram.cmd"


@pytest.fixture
def ampersand_fixture(tmp_path: Path):
    """Fixture directory containing literal '&' in its path, with real engram.cmd copied."""
    assert ENGRAM_CMD_SOURCE.is_file(), f"engram.cmd not found at {ENGRAM_CMD_SOURCE}"
    content = ENGRAM_CMD_SOURCE.read_text(encoding="utf-8")

    fixture_dir = tmp_path / "engram&test_root"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    engram_cmd_copy = fixture_dir / "engram.cmd"
    engram_cmd_copy.write_text(content, encoding="utf-8")

    return fixture_dir, engram_cmd_copy


def test_fallback_unknown_subcommand_exit_code_fidelity_in_ampersand_dir(ampersand_fixture):
    """TEST A: Unknown command fallback exit code is 1 in '&'-laden path (baseline smoke test, not a regression guard -- see module docstring)."""
    fixture_dir, engram_cmd_copy = ampersand_fixture

    # Do NOT create _sys\core\dispatch.bat, deliberately triggering :cmd_unknown branch.
    proc = subprocess.run(
        ["cmd.exe", "/c", str(engram_cmd_copy), "some_totally_unknown_subcommand"],
        cwd=str(fixture_dir),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    if "&" in str(engram_cmd_copy) and "Unknown command" not in proc.stdout:
        # In paths containing '&', cmd.exe /c strips outer quotes from the batch path
        # when invoked as a list. Fall back to double-quoted command line matching
        # the documented workaround pattern (CONVENTION.md line 143, test_path_scenarios.py line 285).
        proc = subprocess.run(
            f'cmd.exe /c ""{engram_cmd_copy}" some_totally_unknown_subcommand"',
            cwd=str(fixture_dir),
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
        )

    assert proc.returncode == 1, (
        f"Expected exit code 1 for unknown subcommand, got {proc.returncode}.\n"
        f"stdout: {proc.stdout}\n"
        f"stderr: {proc.stderr}"
    )
    assert "Unknown command" in proc.stdout, (
        f"Expected 'Unknown command' in stdout.\n"
        f"stdout: {proc.stdout}\n"
        f"stderr: {proc.stderr}"
    )


def test_literal_exclamation_mark_preserved_in_forwarded_arg_in_ampersand_dir(ampersand_fixture):
    """TEST B: Literal '!' in CLI argument survives intact and dispatch return code 7 is propagated."""
    fixture_dir, engram_cmd_copy = ampersand_fixture

    # Create minimal _sys\core\dispatch.bat stub to exercise known dispatch branch.
    core_dir = fixture_dir / "_sys" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    stub_dispatch = core_dir / "dispatch.bat"
    stub_dispatch.write_text(
        "@echo off\r\necho DISPATCH_GOT_ARGS=%*\r\nexit /b 7\r\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["cmd.exe", "/c", str(engram_cmd_copy), "somecmd", "file!name.txt"],
        cwd=str(fixture_dir),
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    if "&" in str(engram_cmd_copy) and proc.returncode != 7:
        # In paths containing '&', cmd.exe /c strips outer quotes from the batch path
        # when invoked as a list. Fall back to double-quoted command line matching
        # the documented workaround pattern (CONVENTION.md line 143, test_path_scenarios.py line 285).
        proc = subprocess.run(
            f'cmd.exe /c ""{engram_cmd_copy}" somecmd file!name.txt"',
            cwd=str(fixture_dir),
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
        )

    assert proc.returncode == 7, (
        f"Expected exit code 7 from stub dispatch.bat, got {proc.returncode}.\n"
        f"stdout: {proc.stdout}\n"
        f"stderr: {proc.stderr}"
    )
    assert "file!name.txt" in proc.stdout, (
        f"Expected 'file!name.txt' with intact '!' in stdout.\n"
        f"stdout: {proc.stdout}\n"
        f"stderr: {proc.stderr}"
    )
