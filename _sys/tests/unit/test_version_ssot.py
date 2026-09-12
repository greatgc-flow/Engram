import sys
from pathlib import Path

import pytest

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from _sys.core.version import load_version_info

def test_version_json_exists():
    version_file = repo_root / "_sys" / "core" / "version.json"
    assert version_file.exists(), "version.json does not exist"

def test_version_json_valid():
    info = load_version_info()
    assert "version" in info
    assert "winget_schema_version" in info
    
    # Simple semver check for version
    version_parts = info["version"].split(".")
    assert len(version_parts) == 3
    for p in version_parts:
        assert p.isdigit()

def test_build_package_default_version():
    # tools/ is a maintainer-only release-packaging directory, deliberately
    # excluded from the portable zip build -- skip on a real release-zip
    # install rather than failing (see test_winget_manifests.py's own note).
    pytest.importorskip(
        "tools.winget.build_package",
        reason="tools/ is excluded from the portable release zip by design",
    )
    # Import build_package and check DEFAULT_VERSION
    from tools.winget.build_package import DEFAULT_VERSION, SCHEMA_VERSION
    info = load_version_info()
    assert DEFAULT_VERSION == info["version"]
    assert SCHEMA_VERSION == info["winget_schema_version"]


def test_engram_cmd_version_matches_version_json():
    """engram.cmd version output must dynamically match version.json."""
    import subprocess

    info = load_version_info()
    expected_version = info["version"]
    engram_cmd = repo_root / "engram.cmd"

    for cmd_arg in ["version", "--version", "-v"]:
        proc = subprocess.run(
            ["cmd.exe", "/c", ".\\engram.cmd", cmd_arg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_root),
        )
        assert proc.returncode == 0, f"engram.cmd {cmd_arg} failed: {proc.stderr}"
        assert expected_version in proc.stdout, f"Expected {expected_version} in output for '{cmd_arg}': {proc.stdout}"


def test_engram_cmd_help_matches_version_json_and_has_no_p_drive_mounting():
    """engram.cmd help output must use version.json and contain no stale P: drive mounting lines."""
    import subprocess

    info = load_version_info()
    expected_version = info["version"]

    for cmd_arg in ["help", "--help", "-h"]:
        proc = subprocess.run(
            ["cmd.exe", "/c", ".\\engram.cmd", cmd_arg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_root),
        )
        assert proc.returncode == 0, f"engram.cmd {cmd_arg} failed: {proc.stderr}"
        assert expected_version in proc.stdout, f"Expected {expected_version} in help header: {proc.stdout}"
        assert "(P:)" not in proc.stdout, f"Stale '(P:)' drive reference found in help text: {proc.stdout}"
        assert "virtual dev drive" not in proc.stdout.lower(), f"Stale 'virtual dev drive' found in help text: {proc.stdout}"


def test_no_semver_literal_in_engram_cmd_or_version_py():
    """No hardcoded \\d+\\.\\d+\\.\\d+ semver literal may remain in active code lines of engram.cmd or version.py."""
    import re

    semver_re = re.compile(r"\b\d+\.\d+\.\d+\b")

    # 1. engram.cmd
    engram_cmd = repo_root / "engram.cmd"
    for i, line in enumerate(engram_cmd.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("::") or stripped.lower().startswith("rem "):
            continue
        m = semver_re.search(line)
        assert not m, f"Hardcoded version literal '{m.group(0)}' found in engram.cmd:{i}: {line}"

    # 2. _sys/core/version.py
    version_py = repo_root / "_sys" / "core" / "version.py"
    for i, line in enumerate(version_py.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        m = semver_re.search(line)
        assert not m, f"Hardcoded version literal '{m.group(0)}' found in version.py:{i}: {line}"


def test_version_py_fallback_on_read_failure(tmp_path):
    """version.py must yield 'unknown' without hardcoded version fallbacks when version.json cannot be read."""
    from _sys.core.version import load_version_info

    # Non-existent file
    missing_file = tmp_path / "missing_version.json"
    res_missing = load_version_info(missing_file)
    assert res_missing.get("version") == "unknown" or res_missing.get("version") is None
    assert res_missing.get("version", "unknown") == "unknown"

    # Invalid JSON
    corrupted_file = tmp_path / "corrupt_version.json"
    corrupted_file.write_text("invalid json content", encoding="utf-8")
    res_corrupt = load_version_info(corrupted_file)
    assert res_corrupt.get("version", "unknown") == "unknown"


def test_build_package_refuses_unknown_version():
    """build_package.py must refuse to package a build whose resolved version is 'unknown'."""
    pytest.importorskip(
        "tools.winget.build_package",
        reason="tools/ is excluded from the portable release zip by design",
    )
    from tools.winget.build_package import main as build_package_main

    rc = build_package_main(["--version", "unknown", "--skip-zip", "--no-validate"])
    assert rc != 0, "build_package.py must refuse to package when version is 'unknown'"

