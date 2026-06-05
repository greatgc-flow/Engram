"""
manage.py - Unified Sandbox Environment Manager (Python Refactored)
Handles PC registration, drive mapping, registry context menus, and Gemini portability.
"""
import os
import sys
import json
import re
import shutil
import subprocess
import winreg
from pathlib import Path

def get_base_dir():
    # Assume script is in _sys/cli/manage.py or similar
    return Path(__file__).parent.parent.parent.resolve()

def get_registry_key_name(base_dir):
    leaf = base_dir.name
    parent = base_dir.parent.name if base_dir.parent else ""
    drive = base_dir.drive.replace(":", "")

    key_base = f"{drive}_{parent}_{leaf}" if parent and len(parent) > 2 else f"{drive}_{leaf}"
    safe_key = re.sub(r'[^A-Za-z0-9]', '_', key_base)
    safe_key = re.sub(r'_+', '_', safe_key).strip('_')
    return f"SandboxRun_{safe_key}"


def get_relay_path(ascii_key: str) -> Path:
    localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
    return localappdata / f"{ascii_key}.bat"


def write_relay_bat(base_dir: Path, ascii_key: str) -> Path:
    relay_path = get_relay_path(ascii_key)
    launch_script = base_dir / "_sys" / "cli" / "launch.bat"
    content = (
        "@echo off\r\n"
        f"set \"SANDBOX_ROOT={base_dir}\"\r\n"
        "call \"%SANDBOX_ROOT%\\_sys\\cli\\launch.bat\" %*\r\n"
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
            # Format: P:\: => D:\Path
            match = re.match(r'^([A-Z]):\\: => (.*)$', line, re.IGNORECASE)
            if match:
                mappings[match.group(1).upper()] = Path(match.group(2).strip())
    except Exception:
        pass
    return mappings

def set_gemini_portability(base_dir):
    gemini_host = Path(os.environ["USERPROFILE"]) / ".gemini"
    gemini_portable = base_dir / "_sys" / "gemini" / "config"
    
    gemini_portable.mkdir(parents=True, exist_ok=True)
    
    if gemini_host.exists():
        # Check if it's already a junction or a real directory
        is_junction = False
        try:
            # Low-level check for junction on Windows
            if os.path.islink(gemini_host) or (gemini_host.is_dir() and getattr(gemini_host.stat(), 'st_reparse_tag', 0) == 0xA0000003):
                is_junction = True
        except Exception:
            pass

        if is_junction:
            try:
                subprocess.run(["cmd", "/c", f"rmdir \"{gemini_host}\""], check=True)
                print(f"  [Info] Removed existing junction: {gemini_host}")
            except Exception as e:
                print(f"  [Warning] Could not remove existing junction: {e}")
                return
        else:
            backup = gemini_host.with_suffix(".host_backup")
            if not backup.exists():
                try:
                    shutil.move(str(gemini_host), str(backup))
                    print(f"  [Info] Backed up host Gemini config to {backup.name}")
                except Exception as e:
                    print(f"  [Warning] Could not backup host Gemini config: {e}")
                    return
            else:
                # If backup exists, we might be in a broken state. Try to remove the .gemini folder if it's empty or just skip.
                print("  [Warning] .gemini and .gemini.host_backup both exist. Skipping junction to prevent data loss.")
                return

    # Create Junction via CMD
    try:
        subprocess.run(["cmd", "/c", f"mklink /J \"{gemini_host}\" \"{gemini_portable}\""], check=True, capture_output=True)
        print("  [OK] Gemini Portability enabled (Junction created)")
    except subprocess.CalledProcessError as e:
        print(f"  [Fail] Could not create Gemini junction: {e}")

def remove_gemini_portability(base_dir):
    gemini_host = Path(os.environ["USERPROFILE"]) / ".gemini"
    gemini_portable = base_dir / "_sys" / "gemini" / "config"
    
    if gemini_host.exists():
        # Check if it's a junction
        if os.path.islink(gemini_host) or (gemini_host.is_dir() and getattr(gemini_host.stat(), 'st_reparse_tag', 0) == 0xA0000003):
            # Remove junction
            try:
                subprocess.run(["cmd", "/c", f"rmdir \"{gemini_host}\""], check=True)
                print("  [OK] Gemini Portability disabled (Junction removed)")
                
                backup = gemini_host.with_suffix(".host_backup")
                if backup.exists():
                    shutil.move(str(backup), str(gemini_host))
                    print(f"  [Info] Restored host Gemini config from {backup.name}")
            except Exception as e:
                print(f"  [Fail] Error removing junction: {e}")

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
    
    config = {"permissions": {"allow": patterns}}
    settings_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
    print(f"  [OK] .claude/settings.local.json updated (Drive {drive_letter}:)")

def global_cleanup(base_dir):
    leaf = base_dir.name
    print(f"  [Info] Performing global cleanup for {leaf}...")
    
    # 1. SUBST cleanup
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

    # 2. Registry cleanup
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell"),
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\lnkfile\shell")
    ]
    
    target_pattern = rf"SandboxRun_.*({re.escape(leaf)}|_D_D_)"
    
    for hkey, path in roots:
        to_delete = []
        try:
            with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        if re.search(target_pattern, subkey_name, re.IGNORECASE):
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
                print(f"  [OK] Removed Orphan Registry: {subkey_name}")
                delete_relay_bat(subkey_name)
            else:
                print(f"  [Warning] Failed to delete registry key: {subkey_name}")

def action_register(base_dir):
    print(f"\n{'='*50}")
    print(f" Registering: {base_dir.name}")
    print(f"{'='*50}")

    global_cleanup(base_dir)
    set_gemini_portability(base_dir)

    # 1. Drive Mapping
    assigned_letter = None
    subst_map = get_subst_mappings()
    
    # Check if we already have a mapping for THIS base_dir
    for letter, path in subst_map.items():
        if path.resolve() == base_dir.resolve():
            assigned_letter = letter
            print(f"  [OK] Reusing existing mapping: {letter}: -> {base_dir}")
            break
            
    if not assigned_letter:
        prefer = base_dir.name[0].upper()
        reserved = ['A', 'B', 'C']
        candidates = [prefer] + [chr(x) for x in range(65, 91) if chr(x) not in reserved and chr(x) != prefer]
        
        for letter in candidates:
            # Check if drive letter is taken by SUBST
            if letter in subst_map:
                mapped_path = subst_map[letter]
                if not mapped_path.exists():
                    print(f"  [Info] Drive {letter}: points to dead path. Releasing.")
                    subprocess.run(["subst", f"{letter}:", "/D"], capture_output=True)
                else:
                    continue # Truly occupied

            # Check if drive letter exists (physical or network)
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

    # 2. Context Menu
    target_key = get_registry_key_name(base_dir)
    menu_label = f"Open in Sandbox: {base_dir.name}" + (f" ({base_dir} -> {assigned_letter}:)" if assigned_letter else f" ({base_dir})")

    # Always use physical path so the command works even after reboot (SUBST not yet mapped).
    # start.bat restores the SUBST mapping itself once it runs.
    launch_script = base_dir / "_sys" / "cli" / "launch.bat"
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
            # relay_path is always at ASCII-safe %LOCALAPPDATA% — avoids cmd.exe
            # parser failures caused by Korean chars or parentheses in base_dir.
            cmd_str = f'cmd.exe /c ""{relay_path}" "{arg}""'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"  [Warning] Registry error on {full_path}: {e}")
            
    print(f"  [OK] Context Menu registered: {menu_label}")

    # 3. State Saving
    config_path = base_dir / "_sys" / "local.config.bat"
    auto_block = [
        ":: [/auto] Generated by manage.py - do not edit this block",
        f"set \"SUBST_DRIVE_LETTER={assigned_letter or ''}\"",
        "set \"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1\"",
        ":: [/auto]"
    ]
    
    user_lines = []
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        in_auto = False
        for line in content.splitlines():
            if ":: [/auto] Generated by" in line:
                in_auto = True
            if not in_auto:
                user_lines.append(line)
            if line.strip() == ":: [/auto]" and in_auto:
                in_auto = False
        user_lines = [l for l in user_lines if l.strip()]  # remove blank-only lines

    new_config = "\n".join(auto_block) + "\n\n:: ── User Overrides (edit below) ─────────────────────────────\n" + "\n".join(user_lines)
    config_path.write_text(new_config.replace("\n", "\r\n"), encoding="utf-8")
    print("  [OK] State saved to local.config.bat")
    print("\n Registration complete!")

def action_unregister(base_dir):
    print(f"\n{'='*50}")
    print(f" Unregistering: {base_dir.name}")
    print(f"{'='*50}")

    delete_relay_bat(get_registry_key_name(base_dir))
    global_cleanup(base_dir)
    remove_gemini_portability(base_dir)

    settings_path = base_dir / ".claude" / "settings.local.json"
    if settings_path.exists():
        settings_path.unlink()
        print("  [OK] .claude/settings.local.json removed")

    config_path = base_dir / "_sys" / "local.config.bat"
    if config_path.exists():
        # Keep only user lines
        content = config_path.read_text(encoding="utf-8")
        user_lines = [line for line in content.splitlines() if "[/auto]" not in line and "set \"" not in line]
        if any(l.strip() for l in user_lines):
            config_path.write_text("\n".join(user_lines).replace("\n", "\r\n"), encoding="utf-8")
        else:
            config_path.unlink()
        print("  [OK] local.config.bat cleaned")

    print("\n Unregistration complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["Register", "Unregister"])
    parser.add_argument("--base-dir", type=str)
    args = parser.parse_args()

    bdir = Path(args.base_dir).resolve() if args.base_dir else get_base_dir()
    
    if args.action == "Register":
        action_register(bdir)
    else:
        action_unregister(bdir)
