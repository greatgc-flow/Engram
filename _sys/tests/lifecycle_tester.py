import sys
import os
import subprocess
import winreg
import re
import shutil
import time
from pathlib import Path

def log(msg):
    print(msg, flush=True)

def check_registry(leaf):
    pattern = rf"SandboxRun_.*({leaf}|_D_D_)"
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\lnkfile\shell")
    ]
    for hkey, path in roots:
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                        if re.search(pattern, sub, re.IGNORECASE):
                            return True
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass
    return False

def get_subst_drive(target_path):
    try:
        out = subprocess.check_output(["subst"], text=True, encoding='oem')
        for line in out.splitlines():
            if str(target_path).lower() in line.lower():
                match = re.match(r'^([A-Z]):', line, re.IGNORECASE)
                if match: return match.group(1)
    except:
        pass
    return None

def _run_bat(bat_path, cwd, **kwargs):
    """Run a .bat via relative path to avoid cmd.exe splitting on '&'.

    Uses ``cmd /c .\\<relative>`` with ``cwd=`` so that the command line
    passed to cmd.exe never contains an ampersand-laden absolute path
    (D11 ampersand fix).  ``bat_path`` must be under ``cwd``.
    """
    rel = Path(bat_path).relative_to(cwd)
    return subprocess.run(
        ["cmd", "/c", f".\\{rel}"], cwd=str(cwd), **kwargs,
    )


def main(target_dir):
    tgt = Path(target_dir).resolve()
    leaf = tgt.name
    manage_bat = tgt / "register.bat"
    unreg_bat = tgt / "unregister.bat"
    start_bat = tgt / "_sys" / "start.bat"
    install_bat = tgt / "install.bat"

    log(f"=== Starting MECE Lifecycle Test on {tgt} ===")

    log("\n=== 1. Test Register ===")
    _run_bat(manage_bat, cwd=tgt, check=True, input=b"\n")
    if not get_subst_drive(tgt): raise AssertionError("SUBST drive not created!")
    if not check_registry(leaf): raise AssertionError("Registry NOT found!")
    if not (tgt / "_sys" / "config.json").exists(): raise AssertionError("config.json not generated!")
    log("Register passed.")

    log("\n=== 2. Test Launcher (start.bat) Environment ===")
    # Create a dummy script to dump the environment variables provided by launcher.py
    dummy_script = tgt / "env_dump.py"
    dummy_script.write_text("import os, sys; print(os.environ.get('NPM_CONFIG_PREFIX','')); print(os.environ.get('PATH','')); sys.exit(0)", encoding="utf-8")
    
    # start.bat takes a script argument; use relative paths for both the bat
    # and the script so no absolute "&"-laden path reaches cmd.exe.
    rel_start = str(start_bat.relative_to(tgt))
    rel_dummy = str(dummy_script.relative_to(tgt))
    res = subprocess.run(
        ["cmd", "/c", f".\\{rel_start}", f".\\{rel_dummy}"],
        cwd=str(tgt), capture_output=True, text=True, input="\n",
    )
    if "npm-global" not in res.stdout: raise AssertionError("NPM_CONFIG_PREFIX not injected by launcher!")
    if "checks" not in res.stdout: raise AssertionError("checks path not injected, AI health tools inaccessible!")
    log("Launcher environment passed.")

    log("\n=== 3. Test Korean Path & Special Chars Scenario ===")
    # Simulate moving to another workspace
    korean_tgt = tgt.parent / "테스트!@#"
    if not korean_tgt.exists():
        shutil.copytree(tgt, korean_tgt, ignore=shutil.ignore_patterns("env", ".git"))
    
    # We just test the register script on the new path to ensure no batch parsing errors occur
    # Python must exist there for this to work
    if (tgt / "_sys" / "env").exists():
        if (korean_tgt / "_sys" / "env").exists():
            shutil.rmtree(korean_tgt / "_sys" / "env")
        shutil.copytree(tgt / "_sys" / "env", korean_tgt / "_sys" / "env")
        
    _run_bat(korean_tgt / "register.bat", cwd=korean_tgt, check=True, input=b"\n")
    if not get_subst_drive(korean_tgt): raise AssertionError("SUBST drive not created for Korean path!")
    _run_bat(korean_tgt / "unregister.bat", cwd=korean_tgt, check=True, input=b"\n")
    log("Korean Path Scenario passed.")

    log("\n=== 4. Test Unregister ===")
    _run_bat(unreg_bat, cwd=tgt, check=True, input=b"\n")
    if get_subst_drive(tgt): raise AssertionError("SUBST drive still exists!")
    if check_registry(leaf): raise AssertionError("Registry still exists!")
    log("Unregister passed.")

    log("\n=== 5. Test ZeroBase Cleanup (Tier 4) ===")
    cleanup_bat = tgt / "cleanup.bat"
    # Supply CLI args to answer 'yes' to prompts
    subprocess.run(
        ["cmd", "/c", f".\\{cleanup_bat.relative_to(tgt)}", "--tier", "4", "--all"],
        cwd=str(tgt), check=True, input=b"\n",
    )
    if (tgt / "_sys" / "env" / "venv").exists(): raise AssertionError("_sys/env/venv not deleted!")
    if (tgt / "_sys" / "env" / "nodejs").exists(): raise AssertionError("_sys/env/nodejs not deleted!")
    if (tgt / "workspace").exists(): raise AssertionError("workspace not deleted!")
    if list(tgt.glob("*.md")): raise AssertionError("Root markdown files not deleted!")
    log("ZeroBase Cleanup passed.")

    log("\n=== 6. Test Install (Setup) ===")
    subprocess.run(
        ["cmd", "/c", f".\\{install_bat.relative_to(tgt)}", "--skip-vscode", "--skip-claude"],
        cwd=str(tgt), check=True,
    )
    if not (tgt / "_sys" / "env" / "python" / "python.exe").exists(): raise AssertionError("Python not installed!")
    if not (tgt / "_sys" / "env" / "venv" / "Scripts" / "python.exe").exists(): raise AssertionError("venv not created!")
    log("Install passed.")

    log("\nALL LIFECYCLE TESTS PASSED.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lifecycle_tester.py <target_dir>")
        sys.exit(1)
    main(sys.argv[1])
