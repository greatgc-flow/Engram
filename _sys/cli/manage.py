"""
manage.py - Thin wrapper. Logic moved to core.virtualizer + core.registrar.
Kept for backward compatibility and direct CLI invocation.
"""
import subprocess
import sys
import traceback
from pathlib import Path

_sys = Path(__file__).parent.parent.resolve()
if str(_sys) not in sys.path:
    sys.path.insert(0, str(_sys))


def get_subst_mappings() -> dict[str, str]:
    """Return current SUBST mappings as {drive_letter: physical_path}.
    Uses encoding='oem' because Windows cmd tools output in OEM code page (cp949 on Korean locales).
    """
    try:
        raw = subprocess.check_output(["subst"], encoding='oem', stderr=subprocess.DEVNULL)
        result = {}
        for line in raw.splitlines():
            parts = line.split("=>")
            if len(parts) == 2:
                drive = parts[0].strip().rstrip(":\\")
                path  = parts[1].strip()
                result[drive] = path
        return result
    except Exception:
        return {}


def _make_ctx(base_dir: Path, extra_args: list) -> dict:
    sys_dir = base_dir / "_sys"
    return {
        "base_dir": base_dir,
        "sys_dir":  sys_dir,
        "paths": {
            "state":      sys_dir / "data" / "state",
            "generated":  sys_dir / "data" / "generated",
            "localappdata": Path(__import__("os").environ.get("LOCALAPPDATA", "")),
        },
        "args":  extra_args,
        "state": {},
    }


def uninstall(ctx: dict):
    import hashlib, json, os, subprocess, sys, uuid
    from pathlib import Path
    
    base_dir = ctx["base_dir"]
    state_file = ctx["paths"]["state"] / "register.state.json"
    is_registered = state_file.exists()
    
    install_id = hashlib.sha256(str(base_dir.absolute()).lower().encode("utf-8")).hexdigest()
    journal_dir = ctx["paths"]["localappdata"] / "Engram" / "uninstall" / install_id
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "journal.json"
    
    journal = {
        "operation": "uninstall",
        "status": "IN_PROGRESS",
        "steps": [],
        "error_recoverable": False
    }
    
    def write_journal():
        journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
        
    write_journal()
    print(f"Uninstall started. ID: {install_id}")
    
    if is_registered:
        print("  - Performing registry and junction cleanup...")
        from core.registrar import remove
        from core.virtualizer import unmount
        try:
            remove(ctx)
            journal["steps"].append("registry_cleanup")
            unmount(ctx)
            journal["steps"].append("junction_cleanup")
        except Exception as e:
            journal["status"] = "FAILED_RECOVERABLE"
            journal["error_recoverable"] = True
            write_journal()
            print(f"  [ERROR] Cleanup failed: {e}")
            sys.exit(1)
    else:
        print("  - Not registered. Skipping registry/junction cleanup.")
        
    write_journal()
    
    nonce = uuid.uuid4().hex
    temp_dir = Path(os.environ.get("TEMP", "C:/Temp")) / "EngramUninstall" / install_id / nonce
    temp_dir.mkdir(parents=True, exist_ok=True)
    helper_path = temp_dir / "EngramUninstallHelper.bat"
    
    helper_content = """@echo off
set "BASE_DIR=%~1"
set "JOURNAL_PATH=%~2"
set "PARENT_PID=%~3"
set "NPM_GLOBAL=%~4"
setlocal enabledelayedexpansion

echo Waiting for parent process (PID: !PARENT_PID!) to exit...
set wait_count=0
:WAIT_LOOP
tasklist /FI "PID eq !PARENT_PID!" 2>NUL | find "!PARENT_PID!" >NUL
if "!ERRORLEVEL!"=="0" (
    if !wait_count! geq 30 (
        echo Parent process did not exit within 30s.
        powershell -Command "$j=Get-Content '!JOURNAL_PATH!' -Raw|ConvertFrom-Json;$j.status='FAILED_FATAL';$j.steps+='directory_purge_timeout';$j|ConvertTo-Json -Depth 10|Set-Content '!JOURNAL_PATH!'"
        exit /b 1
    )
    timeout /t 1 /nobreak >NUL
    set /a wait_count+=1
    goto WAIT_LOOP
)

echo Parent exited. Purging "!BASE_DIR!" and "!NPM_GLOBAL!"...

if exist "!NPM_GLOBAL!" (
    rmdir /s /q "!NPM_GLOBAL!"
)

if exist "!BASE_DIR!" (
    rmdir /s /q "!BASE_DIR!"
)

if exist "!BASE_DIR!" (
    echo Failed to delete some files.
    powershell -Command "$j=Get-Content '!JOURNAL_PATH!' -Raw|ConvertFrom-Json;$j.status='FAILED_RECOVERABLE';$j.steps+='directory_purge';$j.error_recoverable=$true;$j|ConvertTo-Json -Depth 10|Set-Content '!JOURNAL_PATH!'"
) else (
    echo Purge completed successfully.
    powershell -Command "$j=Get-Content '!JOURNAL_PATH!' -Raw|ConvertFrom-Json;$j.status='COMPLETED';$j.steps+='directory_purge';$j|ConvertTo-Json -Depth 10|Set-Content '!JOURNAL_PATH!'"
)
exit /b 0
"""
    helper_path.write_text(helper_content, encoding="utf-8")
    
    npm_global = ctx["sys_dir"] / "env" / "nodejs" / "npm-global"
    parent_pid = os.getpid()
    
    print("  - Handing off to external uninstall helper...")
    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(
        ["cmd.exe", "/c", str(helper_path), str(base_dir), str(journal_path), str(parent_pid), str(npm_global)],
        creationflags=DETACHED_PROCESS,
        close_fds=True
    )
    sys.exit(0)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portable Dev Environment Manager")
    parser.add_argument("action", choices=["register", "unregister", "cleanup", "uninstall"])
    parser.add_argument("target",   nargs="?", default="")
    parser.add_argument("--base-dir", default="")
    args, unknown = parser.parse_known_args()

    base_dir = Path(args.base_dir).resolve() if args.base_dir else _sys.parent
    ctx      = _make_ctx(base_dir, unknown)

    try:
        if args.action == "register":
            from core.virtualizer import mount
            from core.registrar   import apply
            import datetime, json
            mount(ctx)
            apply(ctx)
            # Persist state
            state_dir = ctx["paths"]["state"]
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "register.state.json"
            payload = {"timestamp": datetime.datetime.now().isoformat(), "base_dir": str(base_dir), **ctx["state"]}
            state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  [OK] State saved → {state_file.relative_to(base_dir)}")

        elif args.action == "unregister":
            from core.registrar   import remove
            from core.virtualizer import unmount
            remove(ctx)
            unmount(ctx)
            for f in ("register.state.json",):
                sf = ctx["paths"]["state"] / f
                if sf.exists():
                    sf.unlink()
                    print(f"  [OK] State pruned: {f}")

        elif args.action == "cleanup":
            from core.scrubber import run
            run(ctx)

        elif args.action == "uninstall":
            uninstall(ctx)

    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



