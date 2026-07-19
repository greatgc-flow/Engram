"""Tests for invoke CLI resolution and health check auto-recovery logic."""
import sys
import os
import shutil
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def test_resolve_invoke_cli_relative_path_cwd_independent(monkeypatch, tmp_path):
    # Set up mock file in the mock portable root structure
    # We mock hub.__file__ to locate our mock portable root
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    # Create mock executable under the mock portable root
    exe_dir = tmp_path / "_sys" / "tools" / "agy"
    exe_dir.mkdir(parents=True, exist_ok=True)
    mock_exe = exe_dir / "agy.exe"
    mock_exe.touch()

    # Move current working directory to a different subdirectory
    different_cwd = tmp_path / "different_cwd"
    different_cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(different_cwd)

    # Use forward slash and backslash paths to verify platform path separators
    rel_path_forward = "_sys/tools/agy/agy.exe"
    rel_path_backward = "_sys\\tools\\agy\\agy.exe"

    # Standard shutil.which should fail on relative path from different cwd
    assert shutil.which(rel_path_forward) is None
    assert shutil.which(rel_path_backward) is None

    # hub._resolve_invoke_cli must correctly resolve relative to the portable root
    resolved_forward = hub._resolve_invoke_cli(rel_path_forward)
    assert resolved_forward is not None
    assert Path(resolved_forward).resolve() == mock_exe.resolve()

    resolved_backward = hub._resolve_invoke_cli(rel_path_backward)
    assert resolved_backward is not None
    assert Path(resolved_backward).resolve() == mock_exe.resolve()


def test_resolve_invoke_cli_pathext_fallback(monkeypatch, tmp_path):
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    # Create mock executable under the mock portable root
    exe_dir = tmp_path / "_sys" / "tools" / "agy"
    exe_dir.mkdir(parents=True, exist_ok=True)
    mock_exe = exe_dir / "agy.exe"
    mock_exe.touch()

    # Ensure PATHEXT has .EXE in it
    monkeypatch.setenv("PATHEXT", ".EXE;.BAT", prepend=os.pathsep)

    # Call with extensionless candidate
    resolved = hub._resolve_invoke_cli("_sys/tools/agy/agy")
    assert resolved is not None
    assert Path(resolved).resolve() == mock_exe.resolve()


def test_resolve_invoke_cli_absolute_and_bare(monkeypatch, tmp_path):
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    # 1. Absolute Path resolution
    abs_exe = tmp_path / "absolute_bin.exe"
    abs_exe.touch()
    
    # shutil.which of absolute path returns the path itself if it exists
    resolved_abs = hub._resolve_invoke_cli(str(abs_exe))
    assert resolved_abs is not None
    assert Path(resolved_abs).resolve() == abs_exe.resolve()

    # 2. Bare Command Name resolution
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    bare_exe = bin_dir / "my_cool_binary.exe"
    bare_exe.touch()

    # Modify path to contain bin_dir
    monkeypatch.setenv("PATH", str(bin_dir), prepend=os.pathsep)

    # Bare command name must go through shutil.which
    resolved_bare = hub._resolve_invoke_cli("my_cool_binary")
    assert resolved_bare is not None
    assert Path(resolved_bare).resolve() == bare_exe.resolve()


def test_resolve_invoke_cli_nonexistent(monkeypatch, tmp_path):
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    resolved = hub._resolve_invoke_cli("_sys/tools/agy/nonexistent.exe")
    assert resolved is None


def test_refresh_peer_health_live_auto_recovery_success(monkeypatch, tmp_path):
    # Set up mock file in the mock portable root structure
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    # Set up protocol config
    proto_dir = tmp_path / "_sys" / "ai"
    proto_dir.mkdir(parents=True, exist_ok=True)
    (proto_dir / "protocol.json").write_text("{}", encoding="utf-8")

    # Set up mock health dir and initial state using correct peer sys dir
    peer_name = "ag"
    peer_dir = hub._peer_sys_dir(peer_name)
    peer_dir.mkdir(parents=True, exist_ok=True)
    health_file = peer_dir / "health.json"

    initial_health = {
        "availability": {
            "entrypoint_ok": False,
            "gate_open": False
        },
        "context_health": {
            "status": "RED",
            "checked_at": "20260719T190000"
        },
        "session_health": {
            "last_failure_reason": "cli_not_found"
        }
    }
    health_file.write_text(json.dumps(initial_health), encoding="utf-8")

    # Create lock dir to prevent lock failure
    lock_dir = tmp_path / ".ai"
    lock_dir.mkdir(parents=True, exist_ok=True)

    # Create mock executable under the mock portable root
    exe_dir = tmp_path / "_sys" / "tools" / "agy"
    exe_dir.mkdir(parents=True, exist_ok=True)
    mock_exe = exe_dir / "agy.exe"
    mock_exe.touch()

    # Run auto-recovery branch when CLI is found again
    hub._refresh_peer_health_live(
        peer_name=peer_name,
        peer_dir=peer_dir,
        invoke_cmd="_sys/tools/agy/agy.exe",
        ai_root=lock_dir
    )

    # Verify that the health got healed to GREEN
    updated_health = json.loads(health_file.read_text(encoding="utf-8"))
    assert updated_health["availability"]["entrypoint_ok"] is True
    assert updated_health["availability"]["gate_open"] is True
    assert updated_health["context_health"]["status"] == "GREEN"
    assert updated_health["session_health"]["last_failure_reason"] is None


def test_refresh_peer_health_live_auto_recovery_not_touched_if_other_reason(monkeypatch, tmp_path):
    # Set up mock file in the mock portable root structure
    mock_hub_file = tmp_path / "_sys" / "core" / "hub.py"
    mock_hub_file.parent.mkdir(parents=True, exist_ok=True)
    mock_hub_file.touch()
    monkeypatch.setattr(hub, "__file__", str(mock_hub_file))

    # Set up protocol config
    proto_dir = tmp_path / "_sys" / "ai"
    proto_dir.mkdir(parents=True, exist_ok=True)
    (proto_dir / "protocol.json").write_text("{}", encoding="utf-8")

    # Set up mock health dir and initial state using correct peer sys dir
    peer_name = "ag"
    peer_dir = hub._peer_sys_dir(peer_name)
    peer_dir.mkdir(parents=True, exist_ok=True)
    health_file = peer_dir / "health.json"

    initial_health = {
        "availability": {
            "entrypoint_ok": False,
            "gate_open": False
        },
        "context_health": {
            "status": "RED",
            "checked_at": "20260719T190000"
        },
        "session_health": {
            "last_failure_reason": "quarantined"
        }
    }
    health_file.write_text(json.dumps(initial_health), encoding="utf-8")

    # Create lock dir to prevent lock failure
    lock_dir = tmp_path / ".ai"
    lock_dir.mkdir(parents=True, exist_ok=True)

    # Create mock executable under the mock portable root
    exe_dir = tmp_path / "_sys" / "tools" / "agy"
    exe_dir.mkdir(parents=True, exist_ok=True)
    mock_exe = exe_dir / "agy.exe"
    mock_exe.touch()

    # Run health check when CLI is found again
    hub._refresh_peer_health_live(
        peer_name=peer_name,
        peer_dir=peer_dir,
        invoke_cmd="_sys/tools/agy/agy.exe",
        ai_root=lock_dir
    )

    # Verify that the health was NOT healed (status is still RED, last_failure_reason is quarantined)
    updated_health = json.loads(health_file.read_text(encoding="utf-8"))
    assert updated_health["availability"]["entrypoint_ok"] is True  # updated because CLI exists now
    assert updated_health["availability"]["gate_open"] is False     # not healed
    assert updated_health["context_health"]["status"] == "RED"       # not healed
    assert updated_health["session_health"]["last_failure_reason"] == "quarantined"  # not healed
