import json
import subprocess
import os
from pathlib import Path
from _sys.core.root import find_root

def test_core_update_helper_rollback_byte_identical(tmp_path):
    sys_dir = find_root(__file__)
    ps1_path = sys_dir / "core" / "core_update_helper.ps1"
    
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    backup_dir = tmp_path / "backup"
    
    journal_path = tmp_path / "journal.json"
    
    # Original target files
    exe_path = target_dir / "Engram.exe"
    exe_path.write_bytes(b"ORIGINAL EXE")
    
    file1_path = target_dir / "file1.txt"
    file1_path.write_bytes(b"ORIGINAL CONTENT 1")
    
    locked_path = target_dir / "locked.txt"
    locked_path.mkdir()
    (locked_path / "dummy").write_text("dummy")
    
    # Staged update files
    (staged_dir / "Engram.exe").write_bytes(b"NEW EXE")
    (staged_dir / "file1.txt").write_bytes(b"NEW CONTENT 1")
    (staged_dir / "locked.txt").write_bytes(b"NEW LOCKED")
    
    plan = {
        "target_dir": str(target_dir),
        "staged_dir": str(staged_dir),
        "backup_dir": str(backup_dir),
        "journal_path": str(journal_path),
        "parent_pid": 999999 # dummy
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    
    cmd = f"& '{ps1_path}' -PlanPath '{plan_path}'"
    cp = subprocess.run([
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        cmd
    ], capture_output=True)
        
    assert cp.returncode == 1
    
    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal["status"] == "FAILED_ROLLED_BACK"
    
    assert (target_dir / "Engram.exe").read_bytes() == b"ORIGINAL EXE"
    assert (target_dir / "file1.txt").read_bytes() == b"ORIGINAL CONTENT 1"
    assert (target_dir / "locked.txt").is_dir()
    assert not (target_dir / "Engram.exe.old").exists()


def test_core_update_helper_renamed_sys_dir_success(tmp_path):
    sys_dir = find_root(__file__)
    ps1_path = sys_dir / "core" / "core_update_helper.ps1"

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    backup_dir = tmp_path / "backup"
    journal_path = tmp_path / "journal.json"

    # Original target files with renamed sys dir
    exe_path = target_dir / "Engram.exe"
    exe_path.write_bytes(b"ORIGINAL EXE")
    readme_path = target_dir / "README.md"
    readme_path.write_bytes(b"ORIGINAL README")

    custom_sys = target_dir / "my_custom_sys"
    (custom_sys / "core").mkdir(parents=True)
    (custom_sys / "core" / "version.json").write_text('{"version": "1.0.0"}', encoding="utf-8")
    (custom_sys / "local.config.bat").write_text("set CUSTOM=1", encoding="utf-8")

    # Staged update files (always literally _sys per packaging convention)
    (staged_dir / "Engram.exe").write_bytes(b"NEW EXE")
    (staged_dir / "README.md").write_bytes(b"NEW README")
    staged_sys = staged_dir / "_sys"
    (staged_sys / "core").mkdir(parents=True)
    (staged_sys / "core" / "version.json").write_text('{"version": "2.0.0"}', encoding="utf-8")
    (staged_sys / "core" / "new_feature.py").write_text("# new feature", encoding="utf-8")

    plan = {
        "target_dir": str(target_dir),
        "staged_dir": str(staged_dir),
        "backup_dir": str(backup_dir),
        "journal_path": str(journal_path),
        "parent_pid": 999999,  # dummy
        "sys_dir_name": "my_custom_sys",
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    cmd = f"& '{ps1_path}' -PlanPath '{plan_path}'"
    cp = subprocess.run([
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        cmd,
    ], capture_output=True, text=True)

    assert cp.returncode == 0, f"PowerShell failed with: {cp.stderr}"

    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal["status"] == "COMPLETED"

    # Root files updated
    assert (target_dir / "Engram.exe").read_bytes() == b"NEW EXE"
    assert (target_dir / "README.md").read_bytes() == b"NEW README"
    assert (target_dir / "Engram.exe.old").read_bytes() == b"ORIGINAL EXE"

    # Remapped sys content updated inside my_custom_sys
    assert (custom_sys / "core" / "version.json").read_text(encoding="utf-8") == '{"version": "2.0.0"}'
    assert (custom_sys / "core" / "new_feature.py").read_text(encoding="utf-8") == "# new feature"
    assert (custom_sys / "local.config.bat").read_text(encoding="utf-8") == "set CUSTOM=1"

    # CRITICAL: No duplicate _sys directory created at root
    assert not (target_dir / "_sys").exists()


def test_core_update_helper_renamed_sys_dir_rollback(tmp_path):
    sys_dir = find_root(__file__)
    ps1_path = sys_dir / "core" / "core_update_helper.ps1"

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    backup_dir = tmp_path / "backup"
    journal_path = tmp_path / "journal.json"

    # Original target files
    (target_dir / "Engram.exe").write_bytes(b"ORIGINAL EXE")
    custom_sys = target_dir / "my_custom_sys"
    (custom_sys / "core").mkdir(parents=True)
    (custom_sys / "core" / "layout.py").write_text("# original layout", encoding="utf-8")

    # Staged update files
    (staged_dir / "Engram.exe").write_bytes(b"NEW EXE")
    staged_sys = staged_dir / "_sys"
    (staged_sys / "core").mkdir(parents=True)
    (staged_sys / "core" / "layout.py").write_text("# new layout", encoding="utf-8")

    # Introduce a conflict that causes Copy-Item to fail:
    # A directory where a file wants to be written, or a locked file
    locked_dir = custom_sys / "locked"
    locked_dir.mkdir()
    (locked_dir / "sub").write_text("sub")
    (staged_sys / "locked").write_text("file conflicting with directory")

    plan = {
        "target_dir": str(target_dir),
        "staged_dir": str(staged_dir),
        "backup_dir": str(backup_dir),
        "journal_path": str(journal_path),
        "parent_pid": 999999,
        "sys_dir_name": "my_custom_sys",
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    cmd = f"& '{ps1_path}' -PlanPath '{plan_path}'"
    cp = subprocess.run([
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        cmd,
    ], capture_output=True, text=True)

    assert cp.returncode == 1

    journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    assert journal["status"] == "FAILED_ROLLED_BACK"

    # Original files preserved after rollback
    assert (target_dir / "Engram.exe").read_bytes() == b"ORIGINAL EXE"
    assert (custom_sys / "core" / "layout.py").read_text(encoding="utf-8") == "# original layout"
    assert not (target_dir / "Engram.exe.old").exists()
