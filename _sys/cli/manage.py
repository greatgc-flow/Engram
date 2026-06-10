import os
import sys
import json
import re
import shutil
import subprocess
import winreg
import traceback
from pathlib import Path

# Add sys path to allow importing core modules
sys_dir = Path(__file__).parent.parent.resolve()
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

from core.config import config


def get_base_dir():
    return config.get_base_dir()


def load_peers(sys_dir: Path) -> dict:
    """Load AI peer definitions from _sys/ai/peers.json."""
    peers_path = sys_dir / "ai" / "peers.json"
    if peers_path.exists():
        try:
            return json.loads(peers_path.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass
    return {}

def get_registry_key_name(base_dir):
    leaf = base_dir.name
    parent = base_dir.parent.name if base_dir.parent else ""
    drive = base_dir.drive.replace(":", "")

    key_base = f"{drive}_{parent}_{leaf}" if parent and len(parent) > 2 else f"{drive}_{leaf}"
    safe_key = re.sub(r'[^A-Za-z0-9]', '_', key_base)
    safe_key = re.sub(r'_+', '_', safe_key).strip('_')
    return f"SandboxRun_{safe_key}"


def _cmd(command: str) -> None:
    """shell=True로 cmd 명령 실행 — list2cmdline 이중 인용 문제 없이 COMSPEC 사용."""
    subprocess.run(command, shell=True, check=True, capture_output=True)


def get_relay_path(ascii_key: str) -> Path:
    localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
    return localappdata / f"{ascii_key}.bat"


def write_relay_bat(base_dir: Path, ascii_key: str) -> Path:
    relay_path = get_relay_path(ascii_key)
    # The relay simply calls the newly refactored launcher with the target
    content = (
        "@echo off\r\n"
        f"set \"SANDBOX_ROOT={base_dir}\"\r\n"
        "call \"%SANDBOX_ROOT%\\_sys\\start.bat\" \"%~1\"\r\n"
    )
    relay_path.write_bytes(content.encode("mbcs"))
    return relay_path


def delete_relay_bat(ascii_key: str) -> None:
    relay_path = get_relay_path(ascii_key)
    if relay_path.exists():
        relay_path.unlink()
        print(f"  [OK] Relay removed: {relay_path.name}")

def get_subst_mappings():
    mappings = {}
    try:
        out = subprocess.check_output(["subst"], text=True, encoding='oem')
        for line in out.splitlines():
            match = re.match(r'^([A-Z]):\\: => (.*)$', line, re.IGNORECASE)
            if match:
                mappings[match.group(1).upper()] = Path(match.group(2).strip())
    except Exception:
        pass
    return mappings

def set_peer_portability(base_dir, peer_id, peer):
    sys_subdir = peer.get("sys_subdir")
    root_dir = peer.get("root_dir")
    
    # 1. Host Junction (Config)
    host_j = peer.get("host_junction")
    if host_j:
        host_env = host_j.get("host_env")
        host_dirname = host_j.get("host_dirname")
        portable_subpath = host_j.get("portable_subpath", "config")
        
        if host_env in os.environ:
            host_path = Path(os.environ[host_env]) / host_dirname
            portable_path = base_dir / "_sys" / sys_subdir / portable_subpath
            portable_path.mkdir(parents=True, exist_ok=True)
            
            host_exists = False
            is_junction = False
            try:
                st = host_path.lstat()
                host_exists = True
                # Check for junction reparse tag
                if os.path.islink(host_path) or getattr(st, 'st_reparse_tag', 0) == 0xA0000003:
                    is_junction = True
            except FileNotFoundError:
                pass
            
            if host_exists:
                if is_junction:
                    try:
                        host_path.unlink()
                    except Exception:
                        _cmd(f"rmdir \"{host_path}\"")
                else:
                    backup = host_path.with_suffix(".host_backup")
                    if not backup.exists():
                        try:
                            shutil.move(str(host_path), str(backup))
                            print(f"  [Info] Backed up host {peer_id} config to {backup.name}")
                        except Exception as e:
                            print(f"  [Warning] Could not backup host {peer_id} config: {e}")
                            return
                    else:
                        print(f"  [Warning] {host_dirname} and backup both exist. Skipping junction.")
                        return

            try:
                _cmd(f"mklink /J \"{host_path}\" \"{portable_path}\"")
                print(f"  [OK] {peer_id} Host Portability enabled ({host_dirname} -> _sys/{sys_subdir}/{portable_subpath})")
            except Exception as e:
                print(f"  [Fail] Could not create {peer_id} host junction: {e}")

    # 2. Project Junction
    proj_j = peer.get("project_junction")
    if proj_j:
        portable_subpath = proj_j.get("portable_subpath", "project")
        try:
            _ensure_junction(base_dir / root_dir, base_dir / "_sys" / sys_subdir / portable_subpath)
            print(f"  [OK] {peer_id} Project Portability enabled ({root_dir} -> _sys/{sys_subdir}/{portable_subpath})")
        except Exception as e:
            print(f"  [Fail] Could not set {peer_id} project junction: {e}")

def remove_peer_portability(base_dir, peer_id, peer):
    sys_subdir = peer.get("sys_subdir")
    root_dir = peer.get("root_dir")
    
    # 1. Host Junction
    host_j = peer.get("host_junction")
    if host_j:
        host_env = host_j.get("host_env")
        host_dirname = host_j.get("host_dirname")
        if host_env in os.environ:
            host_path = Path(os.environ[host_env]) / host_dirname
            
            is_junction = False
            try:
                st = host_path.lstat()
                if os.path.islink(host_path) or getattr(st, 'st_reparse_tag', 0) == 0xA0000003:
                    is_junction = True
            except Exception:
                pass

            if is_junction:
                try:
                    _cmd(f"rmdir \"{host_path}\"")
                    print(f"  [OK] {peer_id} Host Portability disabled ({host_dirname} junction removed)")
                    
                    backup = host_path.with_suffix(".host_backup")
                    if backup.exists():
                        shutil.move(str(backup), str(host_path))
                        print(f"  [Info] Restored host {peer_id} config from {backup.name}")
                except Exception as e:
                    print(f"  [Fail] Error removing {peer_id} host junction: {e}")

    # 2. Project Junction
    proj_j = peer.get("project_junction")
    if proj_j:
        try:
            if (base_dir / root_dir).exists():
                _remove_junction(base_dir / root_dir)
                print(f"  [OK] {peer_id} Project Portability disabled ({root_dir} junction removed)")
        except Exception as e:
            print(f"  [Fail] Error removing {peer_id} project junction: {e}")

def _ensure_junction(host: Path, portable: Path) -> None:
    """host -> portable 방향 Junction 생성. host가 실제 디렉터리면 내용을 이동 후 교체."""
    portable.mkdir(parents=True, exist_ok=True)

    is_reparse = False
    try:
        st = host.lstat()
        if os.path.islink(host) or getattr(st, 'st_reparse_tag', 0) == 0xA0000003:
            is_reparse = True
    except FileNotFoundError:
        pass

    if is_reparse:
        _cmd(f"rmdir \"{host}\"")
    elif host.exists():
        for item in list(host.iterdir()):
            if item.name == "settings.local.json":
                item.unlink()
                continue
            dest = portable / item.name
            if dest.exists():
                if dest.is_dir(): shutil.rmtree(str(dest))
                else: dest.unlink()
            shutil.move(str(item), str(portable))
        host.rmdir()

    _cmd(f"mklink /J \"{host}\" \"{portable}\"")


def _remove_junction(host: Path) -> None:
    is_reparse = False
    try:
        st = host.lstat()
        if os.path.islink(host) or getattr(st, 'st_reparse_tag', 0) == 0xA0000003:
            is_reparse = True
    except Exception:
        pass
    if is_reparse:
        _cmd(f"rmdir \"{host}\"")



def update_claude_settings(base_dir, drive_letter):
    if not drive_letter:
        return
    settings_path = base_dir / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    patterns = [
        f"Bash(cmd /c \"{drive_letter}:\\_sys\\cli\\msg.bat\" *)",
        f"PowerShell(cmd /c \"{drive_letter}:\\_sys\\cli\\msg.bat\" *)",
        f"PowerShell(cmd /c \"{drive_letter}:\\_sys\\cli\\msg.bat\" ask *)",
        f"PowerShell(Get-ChildItem \"{drive_letter}:\\_sys\\ *)",
        f"PowerShell(Get-Content \"{drive_letter}:\\ *)"
    ]
    
    c_config = {"permissions": {"allow": patterns}}
    settings_path.write_text(json.dumps(c_config, indent=4), encoding="utf-8")
    print(f"  [OK] .claude/settings.local.json updated (Drive {drive_letter}:)")

def global_cleanup(base_dir):
    leaf = base_dir.name
    print(f"  [Info] Performing global cleanup for {leaf}...")
    
    try:
        out = subprocess.check_output(["subst"], text=True, encoding='oem')
        for line in out.splitlines():
            match = re.match(r'^([A-Z]):.*' + re.escape(str(base_dir)), line, re.IGNORECASE)
            if match:
                drive = match.group(1)
                subprocess.run(["subst", f"{drive}:", "/D"])
                print(f"  [OK] Released SUBST: {drive}:")
    except Exception:
        pass

    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\lnkfile\shell")
    ]
    
    current_key_name = get_registry_key_name(base_dir)
    
    for hkey, path in roots:
        to_delete = []
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        if subkey_name.startswith("SandboxRun_"):
                            is_target = (subkey_name == current_key_name)
                            
                            is_orphan = False
                            if not is_target:
                                ascii_key = subkey_name
                                relay_path = get_relay_path(ascii_key)
                                if not relay_path.exists():
                                    is_orphan = True
                                else:
                                    content = relay_path.read_text(encoding="mbcs", errors="ignore")
                                    match = re.search(r'set "SANDBOX_ROOT=(.*?)"', content, re.IGNORECASE)
                                    if match:
                                        sandbox_root = Path(match.group(1))
                                        if not sandbox_root.exists():
                                            is_orphan = True
                                    else:
                                        is_orphan = True
                                        
                            if is_target or is_orphan:
                                to_delete.append(subkey_name)
                        i += 1
                    except OSError:
                        break
        except Exception:
            continue

        for subkey_name in to_delete:
            full_reg_path = f"HKCU\\{path}\\{subkey_name}"
            res = subprocess.run(["reg", "delete", full_reg_path, "/f"], capture_output=True)
            if res.returncode == 0:
                print(f"  [OK] Removed Registry: {subkey_name}")
                delete_relay_bat(subkey_name)
            else:
                print(f"  [Warning] Failed to delete registry key: {subkey_name}")

def action_register(base_dir):
    print(f"\n{'='*50}")
    print(f" Registering: {base_dir.name}")
    print(f"{'='*50}")

    global_cleanup(base_dir)
    
    peers = config.get_peers_config()
    for peer_id, peer in peers.items():
        if peer.get("enabled", True):
            set_peer_portability(base_dir, peer_id, peer)

    assigned_letter = None
    subst_map = get_subst_mappings()
    
    for letter, path in subst_map.items():
        if path.resolve() == base_dir.resolve():
            assigned_letter = letter
            print(f"  [OK] Reusing existing mapping: {letter}: -> {base_dir}")
            break
            
    if not assigned_letter:
        prefer = base_dir.name[0].upper()
        if not ('A' <= prefer <= 'Z'):
            prefer = 'P'
        reserved = ['A', 'B', 'C']
        candidates = [prefer] + [chr(x) for x in range(65, 91) if chr(x) not in reserved and chr(x) != prefer]
        
        for letter in candidates:
            if letter in subst_map:
                mapped_path = subst_map[letter]
                if not mapped_path.exists():
                    print(f"  [Info] Drive {letter}: points to dead path. Releasing.")
                    subprocess.run(["subst", f"{letter}:", "/D"], capture_output=True)
                else:
                    continue

            drive_path = f"{letter}:\\"
            if not os.path.exists(drive_path):
                try:
                    subprocess.run(["subst", f"{letter}:", str(base_dir)], check=True)
                    assigned_letter = letter
                    print(f"  [OK] Mapped {base_dir} to {letter}:")
                    break
                except Exception:
                    continue
    
    if assigned_letter:
        update_claude_settings(base_dir, assigned_letter)

    target_key = get_registry_key_name(base_dir)
    menu_label = f"Open in Sandbox: {base_dir.name}" + (f" ({base_dir} -> {assigned_letter}:)" if assigned_letter else f" ({base_dir})")

    code_path = base_dir / "_sys" / "env" / "vscode" / "Code.exe"

    reg_paths = [
        (r"Software\Classes\Directory\Background\shell", "%V"),
        (r"Software\Classes\Directory\shell", "%V"),
        (r"Software\Classes\*\shell", "%1"),
        (r"Software\Classes\lnkfile\shell", "%1")
    ]

    relay_path = write_relay_bat(base_dir, target_key)
    print(f"  [OK] Relay created: {relay_path}")

    for path_base, arg in reg_paths:
        full_path = f"{path_base}\\{target_key}"
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_path)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, menu_label)
            winreg.SetValueEx(key, "HasLUAShield", 0, winreg.REG_SZ, "")
            if os.path.exists(str(code_path)):
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(code_path))

            cmd_key = winreg.CreateKey(key, "command")
            cmd_str = f'cmd.exe /c ""{relay_path}" "{arg}.""'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"  [Warning] Registry error on {full_path}: {e}")
            
    print(f"  [OK] Context Menu registered: {menu_label}")

    # State Saving via ConfigManager
    config.set("SUBST_DRIVE_LETTER", assigned_letter)
    print("  [OK] State saved to config.json")
    
    # Optional cleanup of legacy file
    legacy_config = base_dir / "_sys" / "local.config.bat"
    if legacy_config.exists():
        legacy_config.unlink()
        print("  [OK] Legacy local.config.bat removed.")

    print("\n Registration complete!")

def action_unregister(base_dir):
    print(f"\n{'='*50}")
    print(f" Unregistering: {base_dir.name}")
    print(f"{'='*50}")

    delete_relay_bat(get_registry_key_name(base_dir))
    global_cleanup(base_dir)
    
    peers = config.get_peers_config()
    for peer_id, peer in peers.items():
        remove_peer_portability(base_dir, peer_id, peer)

    settings_path = base_dir / "_sys" / "claude" / "project" / "settings.local.json"
    if settings_path.exists():
        settings_path.unlink()
        print("  [OK] claude/project/settings.local.json removed")

    # Clear SUBST mapping from config
    config.set("SUBST_DRIVE_LETTER", None)
    print("  [OK] config.json cleared of drive mapping")

    print("\n Unregistration complete.")

def action_cleanup(base_dir):
    # Delegate to cleanup.py
    cleanup_py = base_dir / "_sys" / "cli" / "cleanup.py"
    if cleanup_py.exists():
        subprocess.run([sys.executable, str(cleanup_py)] + sys.argv[2:])
    else:
        print("[Error] cleanup.py not found.")
        sys.exit(1)

def main():
    try:
        import argparse
        parser = argparse.ArgumentParser()
        # Accept 'register', 'unregister', 'cleanup' (case-insensitive due to batch %~n0)
        parser.add_argument("action", type=str)
        parser.add_argument("--base-dir", type=str, default="")
        # Allow trailing unknown args for cleanup
        args, unknown = parser.parse_known_args()

        action = args.action.lower()
        bdir = Path(args.base_dir).resolve() if args.base_dir else get_base_dir()
        
        if action == "register":
            action_register(bdir)
        elif action == "unregister":
            action_unregister(bdir)
        elif action == "cleanup":
            action_cleanup(bdir)
        else:
            print(f"[Error] Unknown action: {action}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected error occurred:")
        print(f"  {e}\n")
        print("--- Stack Trace ---")
        traceback.print_exc()
        print("-------------------")
        print("\nPress any key to exit...")
        os.system("pause >nul")
        sys.exit(1)

if __name__ == "__main__":
    main()
