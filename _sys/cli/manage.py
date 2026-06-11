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


TARGET_MAP = {
    "Directory/Background": (r"Software\Classes\Directory\Background\shell", "%V"),
    "Directory":            (r"Software\Classes\Directory\shell",            "%V"),
    "Drive":                (r"Software\Classes\Drive\shell",                "%1"),
    "*":                    (r"Software\Classes\*\shell",                    "%1"),
    "lnkfile":              (r"Software\Classes\lnkfile\shell",              "%1"),
}


def load_context_menu(sys_dir: Path) -> list:
    """Load context menu entry definitions from _sys/context_menu.json."""
    path = sys_dir / "context_menu.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    except Exception:
        return []


def get_entry_key_name(base_key: str, entry_id: str) -> str:
    """Build registry key name: {base_key}_{entry_id} with sanitization."""
    safe_id = re.sub(r'[^A-Za-z0-9]', '_', entry_id)
    safe_id = re.sub(r'_+', '_', safe_id).strip('_')
    return f"{base_key}_{safe_id}"


def _register_entry(base_dir: Path, entry: dict, base_key: str, relay_root: Path,
                    phys_dir: Path = None, drive: str = "") -> None:
    """Register a single context_menu.json entry into the Windows registry.

    base_dir: path baked into the relay (SUBST drive if assigned).
    phys_dir: physical path fallback for when the SUBST drive is not mapped (e.g. after reboot).
    drive:    SUBST drive letter — expands the {DRIVE} placeholder in labels (e.g. "Open ({DRIVE}:)").
    """
    entry_id   = entry.get("id", "entry")
    label      = entry.get("label", entry_id)
    label      = label.replace("{DRIVE}", drive) if drive else re.sub(r"\s*\(?\{DRIVE\}:?\)?", "", label)
    icon_rel   = entry.get("icon", "")
    cmd_tmpl   = entry.get("command", "")
    targets    = entry.get("targets", list(TARGET_MAP.keys()))

    reg_key_name = get_entry_key_name(base_key, entry_id)

    # Relay bat: one per entry id. Falls back to the physical path if SUBST is unmapped.
    relay_path = relay_root / f"{reg_key_name}.bat"
    primary  = str(base_dir).rstrip("\\")
    fallback = str(phys_dir).rstrip("\\") if phys_dir and phys_dir != base_dir else None
    lines = [
        "@echo off",
        f"set \"SANDBOX_ROOT={primary}\"",
    ]
    if fallback:
        lines.append(
            f"if not exist \"%SANDBOX_ROOT%\\_sys\\start.bat\" set \"SANDBOX_ROOT={fallback}\""
        )
    lines.append("call \"%SANDBOX_ROOT%\\_sys\\start.bat\" \"%~1\"")
    relay_content = "\r\n".join(lines) + "\r\n"
    relay_path.write_bytes(relay_content.encode("mbcs"))

    icon_path = base_dir / icon_rel.replace("/", "\\") if icon_rel else None
    # Extracting icons from a large .exe slows down Explorer menus — cache a small .ico locally
    if icon_path and icon_path.suffix.lower() == ".exe" and icon_path.exists():
        ico_cache = relay_root / f"{reg_key_name}.ico"
        ps = (
            "Add-Type -AssemblyName System.Drawing; "
            f"$i=[System.Drawing.Icon]::ExtractAssociatedIcon('{icon_path}'); "
            f"$s=[System.IO.File]::Create('{ico_cache}'); $i.Save($s); $s.Close()"
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        if res.returncode == 0 and ico_cache.exists():
            icon_path = ico_cache

    for target_name in targets:
        if target_name not in TARGET_MAP:
            print(f"  [Warning] Unknown target '{target_name}' in context_menu.json — skipped")
            continue
        path_base, arg = TARGET_MAP[target_name]
        full_path = f"{path_base}\\{reg_key_name}"
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_path)
            winreg.SetValueEx(key, "",        0, winreg.REG_SZ, label)
            winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, label)
            if icon_path and icon_path.exists():
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(icon_path))
            cmd_key = winreg.CreateKey(key, "command")
            # Outer quotes are required: cmd /c "a" "b" mis-strips quotes without them
            cmd_str = f'cmd.exe /c ""{relay_path}" "{arg}""'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"  [Warning] Registry error on {full_path}: {e}")

    print(f"  [OK] Context menu entry registered: [{reg_key_name}] {label}")


def _unregister_entry(base_key: str, entry_id: str, relay_root: Path) -> None:
    """Remove a single context menu entry from registry and relay bat."""
    reg_key_name = get_entry_key_name(base_key, entry_id)
    for path_base, _ in TARGET_MAP.values():
        full_reg_path = f"HKCU\\{path_base}\\{reg_key_name}"
        subprocess.run(["reg", "delete", full_reg_path, "/f"], capture_output=True)
    for ext in (".bat", ".ico"):
        p = relay_root / f"{reg_key_name}{ext}"
        if p.exists():
            p.unlink()
    print(f"  [OK] Context menu entry removed: {reg_key_name}")


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



def apply_local_settings(base_dir: Path, peer_id: str, peer_cfg: dict, drive: str = "") -> None:
    """Write peer-specific local settings files driven by peers.json local_settings field.

    Placeholders expanded in content strings:
        {DRIVE}    — drive letter only (e.g. "E")
        {BASE_DIR} — full physical base path, JSON-escaped (e.g. "E:\\\\PortableDev")
    Target path is relative to _sys/{sys_subdir}/.
    """
    sys_dir = base_dir / "_sys"
    peer_subdir = sys_dir / peer_cfg.get("sys_subdir", peer_id)
    base_dir_escaped = str(base_dir).replace("\\", "\\\\")

    for spec in peer_cfg.get("local_settings", []):
        target_rel = spec.get("target", "")
        if not target_rel:
            continue
        target_path = peer_subdir / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)

        content_str = json.dumps(spec.get("content", {}))
        content_str = content_str.replace("{DRIVE}", drive)
        content_str = content_str.replace("{BASE_DIR}", base_dir_escaped)
        target_path.write_text(
            json.dumps(json.loads(content_str), indent=4), encoding="utf-8"
        )
        print(f"  [OK] {peer_id}: {target_rel} written (drive={drive or 'none'})")

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
        (winreg.HKEY_CURRENT_USER, path_base) for path_base, _ in TARGET_MAP.values()
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

    # Remove Windows 11 classic menu key (restore default simplified menu)
    orch = config.get_orchestration_config()
    win11_clsid = orch.get("windows", {}).get("win11_classic_menu_clsid", "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}")
    win11_key = rf"Software\Classes\CLSID\{win11_clsid}"
    res = subprocess.run(["reg", "delete", f"HKCU\\{win11_key}", "/f"], capture_output=True)
    if res.returncode == 0:
        print(f"  [OK] Windows 11 classic menu key removed")

def action_register(base_dir):
    print(f"\n{'='*50}")
    print(f" Registering: {base_dir.name}")
    print(f"{'='*50}")

    global_cleanup(base_dir)

    sys_dir = base_dir / "_sys"
    peers = load_peers(sys_dir)
    for peer_id, peer in peers.items():
        if peer.get("enabled", True):
            set_peer_portability(base_dir, peer_id, peer)

    assigned_letter = None
    subst_map = get_subst_mappings()

    orch = config.get_orchestration_config()
    subst_cfg = orch.get("subst", {})
    reserved = subst_cfg.get("reserved_letters", ["A", "B", "C"])
    default_prefer = subst_cfg.get("default_preference_letter", "P")

    for letter, path in subst_map.items():
        if path.resolve() == base_dir.resolve():
            assigned_letter = letter
            print(f"  [OK] Reusing existing mapping: {letter}: -> {base_dir}")
            break

    if not assigned_letter:
        prefer = base_dir.name[0].upper()
        if not ('A' <= prefer <= 'Z'):
            prefer = default_prefer
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
    
    # Write per-peer local settings (e.g. settings.local.json with drive-specific permissions)
    # 폴백: SUBST 없을 때 물리 드라이브 레터 사용 (e.g. "E:" → "E")
    drive = assigned_letter or base_dir.drive.rstrip(":")
    for peer_id, peer_cfg in peers.items():
        if peer_cfg.get("enabled", True) and peer_cfg.get("local_settings"):
            apply_local_settings(base_dir, peer_id, peer_cfg, drive)

    # Use SUBST drive path in relay bat to avoid Korean/special chars in physical path
    relay_base_dir = Path(f"{assigned_letter}:\\") if assigned_letter else base_dir
    base_key   = get_registry_key_name(relay_base_dir)
    relay_root = Path(os.environ.get("LOCALAPPDATA", ""))
    entries    = load_context_menu(sys_dir)

    if not entries:
        print("  [Warning] context_menu.json has no entries — skipping context menu registration")
    for entry in entries:
        if entry.get("enabled", True):
            _register_entry(relay_base_dir, entry, base_key, relay_root,
                            phys_dir=base_dir, drive=assigned_letter or "")
        else:
            _unregister_entry(base_key, entry.get("id", "entry"), relay_root)

    # Enable Windows 11 classic context menu (per-user, HKCU)
    win11_clsid = orch.get("windows", {}).get("win11_classic_menu_clsid", "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}")
    win11_key = rf"Software\Classes\CLSID\{win11_clsid}\InprocServer32"
    try:
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, win11_key)
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "")
        winreg.CloseKey(k)
        print(f"  [OK] Windows 11 classic context menu enabled")
    except Exception as e:
        print(f"  [Warning] Could not set Win11 classic menu key: {e}")

    # State Saving via ConfigManager
    config.set("SUBST_DRIVE_LETTER", assigned_letter)
    print("  [OK] State saved to config.json")
    
    # Optional cleanup of legacy file
    legacy_filename = orch.get("legacy", {}).get("config_file", "local.config.bat")
    legacy_config = base_dir / "_sys" / legacy_filename
    if legacy_config.exists():
        legacy_config.unlink()
        print("  [OK] Legacy local.config.bat removed.")

    print("\n Registration complete!")

def action_unregister(base_dir):
    print(f"\n{'='*50}")
    print(f" Unregistering: {base_dir.name}")
    print(f"{'='*50}")

    base_key   = get_registry_key_name(base_dir)
    relay_root = Path(os.environ.get("LOCALAPPDATA", ""))
    entries    = load_context_menu(base_dir / "_sys")
    for entry in entries:
        _unregister_entry(base_key, entry.get("id", "entry"), relay_root)

    # Legacy relay cleanup (pre-JSON format)
    delete_relay_bat(base_key)
    global_cleanup(base_dir)

    sys_dir = base_dir / "_sys"
    peers = load_peers(sys_dir)
    for peer_id, peer in peers.items():
        remove_peer_portability(base_dir, peer_id, peer)

    # Remove per-peer local settings (driven by peers.json, no hardcoding)
    for peer_id, peer_cfg in peers.items():
        subdir = sys_dir / peer_cfg.get("sys_subdir", peer_id)
        settings_path = subdir / "project" / "settings.local.json"
        if settings_path.exists():
            settings_path.unlink()
            print(f"  [OK] {peer_id}/project/settings.local.json removed")

    # Clear SUBST mapping from config
    config.set("SUBST_DRIVE_LETTER", None)
    print("  [OK] config.json cleared of drive mapping")

    print("\n Unregistration complete.")

def _is_cli_available(peer_id: str, sys_dir: Path) -> bool:
    """Check if a peer CLI binary exists in npm-global."""
    npm_sub = config.get_env_config().get("tool_env_vars", {}).get("NPM_CONFIG_PREFIX", {}).get("sub", "nodejs/npm-global")
    npm_global = sys_dir / "env" / npm_sub
    return (npm_global / f"{peer_id}.cmd").exists()


def action_workspace_init(base_dir: Path, workspace_path: Path):
    """
    Initialize a workspace with MECE .ai/ shadow structure.

    Layout after init:
        workspace/proj/
        ├── .ai/
        │   ├── common/   → junction → _sys/ai/common/   (cross-workspace agents/skills/mcp)
        │   ├── claude/   (peer shadow — source of truth for .claude/)
        │   └── gemini/   (peer shadow — source of truth for .gemini/)
        ├── .claude/      → junction → .ai/claude/   (if Claude CLI available)
        ├── .gemini/      → junction → .ai/gemini/   (if Gemini CLI available)
        └── CONTEXT.md    (peer-agnostic project context)
    """
    sys_dir = base_dir / "_sys"
    peers = load_peers(sys_dir)

    print(f"\n{'='*50}")
    print(f" Workspace Init: {workspace_path}")
    print(f"{'='*50}")

    # ── Create workspace root from template (if new) ─────────────────────
    if not workspace_path.exists():
        template_dir = sys_dir / "templates" / "workspace"
        if template_dir.exists():
            shutil.copytree(str(template_dir), str(workspace_path))
            print(f"  [OK] Created from template: {workspace_path.name}")
        else:
            workspace_path.mkdir(parents=True)
            print(f"  [OK] Created (no template found): {workspace_path.name}")
    else:
        print(f"  [Info] Workspace exists — adding .ai/ structure only")

    # ── .ai/ shadow directory ─────────────────────────────────────────────
    ai_dir = workspace_path / ".ai"
    ai_dir.mkdir(exist_ok=True)

    # Common junction: .ai/common/ → _sys/ai/common/
    common_src  = sys_dir / "ai" / "common"
    common_link = ai_dir / "common"
    if common_src.exists() and not common_link.exists():
        try:
            _ensure_junction(common_link, common_src)
            print(f"  [OK] .ai/common → _sys/ai/common (junction)")
        except Exception as e:
            print(f"  [Warn] Could not create common junction: {e}")
    elif common_link.exists():
        print(f"  [--] .ai/common already set up")

    # ── Per-peer scaffold + junction ──────────────────────────────────────
    proj_name = workspace_path.name
    for peer_id, cfg in peers.items():
        ws_cfg        = cfg.get("workspace", {})
        shadow_subdir = ws_cfg.get("shadow_subdir", f".ai/{peer_id}")
        junction_name = ws_cfg.get("junction_name", cfg.get("root_dir", f".{peer_id}"))
        glue_file     = ws_cfg.get("glue_file")
        glue_template = ws_cfg.get("glue_template")

        shadow_path   = workspace_path / Path(shadow_subdir)
        shadow_path.mkdir(parents=True, exist_ok=True)

        # Glue file (peer-specific thin wrapper over CONTEXT.md)
        if glue_file:
            glue_dest = shadow_path / glue_file
            if not glue_dest.exists():
                glue_src = None
                if glue_template:
                    glue_src = sys_dir / cfg.get("sys_subdir", peer_id) / glue_template
                if glue_src and glue_src.exists():
                    content = glue_src.read_text(encoding="utf-8").replace(
                        "{{PROJECT_NAME}}", proj_name
                    )
                    glue_dest.write_text(content, encoding="utf-8")
                    print(f"  [OK] {peer_id}: {glue_file} created from template")
                else:
                    glue_dest.write_text(
                        f"# {peer_id.capitalize()} — {proj_name}\n"
                        f"> Core context: see [CONTEXT.md](../CONTEXT.md)\n",
                        encoding="utf-8"
                    )
                    print(f"  [OK] {peer_id}: {glue_file} created (default)")
            else:
                print(f"  [--] {peer_id}: {glue_file} already exists")

        # Junction: workspace/.{peer}/ → workspace/.ai/{peer}/
        junction_path = workspace_path / junction_name
        if _is_cli_available(peer_id, sys_dir):
            if not junction_path.exists():
                try:
                    _ensure_junction(junction_path, shadow_path)
                    print(f"  [OK] {peer_id}: {junction_name} → {shadow_subdir} (junction)")
                except Exception as e:
                    print(f"  [Fail] {peer_id}: Could not create junction: {e}")
            else:
                print(f"  [--] {peer_id}: {junction_name} already exists")
        else:
            if not cfg.get("enabled", True):
                print(f"  [--] {peer_id}: disabled (skipped)")
            else:
                print(f"  [--] {peer_id}: CLI not installed — scaffold ready, junction skipped")

    print(f"\n  Done. Workspace '{proj_name}' is ready.")


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
        parser = argparse.ArgumentParser(
            description="Portable Dev Environment Manager",
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument("action", type=str,
                            help="register | unregister | cleanup | workspace-init")
        parser.add_argument("target", nargs="?", default="",
                            help="workspace-init: workspace name (under bdir/workspace/) or absolute path")
        parser.add_argument("--base-dir", type=str, default="")
        args, _unknown = parser.parse_known_args()

        action = args.action.lower()
        bdir = Path(args.base_dir).resolve() if args.base_dir else get_base_dir()

        if action == "register":
            action_register(bdir)
        elif action == "unregister":
            action_unregister(bdir)
        elif action == "cleanup":
            action_cleanup(bdir)
        elif action in ("workspace-init", "workspace_init"):
            if not args.target:
                print("[Error] workspace-init requires a workspace name or path.")
                print("  Usage: manage.py workspace-init <name>    (creates bdir/workspace/<name>)")
                print("         manage.py workspace-init <abs-path>")
                sys.exit(1)
            t = Path(args.target)
            ws_path = t if t.is_absolute() else bdir / "workspace" / t
            action_workspace_init(bdir, ws_path)
        else:
            print(f"[Error] Unknown action: '{action}'")
            print("  Actions: register | unregister | cleanup | workspace-init <name>")
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
