import json
import subprocess
import os
from pathlib import Path

def test_core_update_helper_rollback_byte_identical(tmp_path):
    sys_dir = Path(__file__).resolve().parents[2]
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
