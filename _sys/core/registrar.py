"""
registrar.py - Windows context menu and registry management.
All entry definitions, registry target paths, and relay templates
are sourced from context_menu.json. No hardcoding.
"""
import os
import re
import json
import subprocess
import winreg
from pathlib import Path


def _load_context_menu(sys_dir: Path) -> dict:
    p = sys_dir / "context_menu.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [Warning] Failed to load context_menu.json: {e}")
    return {}


def _load_state(ctx: dict) -> dict:
    state_file = ctx["paths"]["state"] / "register.state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return ctx.get("prior_state", {})


def _safe_key(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", text)
    return re.sub(r"_+", "_", safe).strip("_")


def _registry_key_name(base_dir: Path) -> str:
    leaf   = base_dir.name
    parent = base_dir.parent.name if base_dir.parent else ""
    drive  = base_dir.drive.replace(":", "")
    base   = f"{drive}_{parent}_{leaf}" if parent and len(parent) > 2 else f"{drive}_{leaf}"
    return f"SandboxRun_{_safe_key(base)}"


def _expand(template: str, root: str, phys_root: str, drive: str) -> str:
    s = template.replace("{root}", root)
    s = s.replace("{phys_root}", phys_root)
    s = s.replace("{DRIVE}", drive)
    return s


def _resolve_icon(icon_template: str, paths: dict, relay_root: Path, key_name: str) -> str | None:
    if not icon_template:
        return None
    icon_str = icon_template
    for sym, path in paths.items():
        icon_str = icon_str.replace(f"{{{sym}}}", str(path).replace("\\", "/"))
    icon_path = Path(icon_str.replace("/", "\\"))
    if not icon_path.exists():
        return None
    # Cache .exe icon as .ico to avoid Explorer slowdown
    if icon_path.suffix.lower() == ".exe":
        ico_cache = relay_root / f"{key_name}.ico"
        ps = (
            "Add-Type -AssemblyName System.Drawing; "
            f"$i=[System.Drawing.Icon]::ExtractAssociatedIcon('{icon_path}'); "
            f"$s=[System.IO.File]::Create('{ico_cache}'); $i.Save($s); $s.Close()"
        )
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
            if res.returncode == 0 and ico_cache.exists():
                return str(ico_cache)
        except OSError:
            pass
    return str(icon_path)


def _write_relay(relay_path: Path, content: str) -> None:
    # mbcs → UTF-8 BOM-less: cmd.exe reads UTF-8 with BOM on Windows 10+,
    # but MBCS is safer for paths with Korean/special chars on Korean locale systems.
    # We use mbcs with 'replace' to avoid hard failures on unmappable chars.
    relay_path.write_bytes(content.encode("mbcs", errors="replace"))


def _register_entry(
    entry: dict, cfg: dict, base_key: str,
    relay_root: Path, paths: dict,
    root: str, phys_root: str, drive: str,
) -> dict | None:
    entry_id = entry.get("id", "entry")
    label    = entry.get("label", entry_id)
    label    = _expand(label, root, phys_root, drive)
    if not drive:
        label = re.sub(r"\s*\(?\{DRIVE\}:?\)?", "", label)

    targets_cfg = cfg.get("registry", {}).get("targets", {})
    relay_tmpl  = cfg.get("relay", {}).get("content_template", "")
    key_name    = f"{base_key}_{_safe_key(entry_id)}"
    targets     = entry.get("targets", list(targets_cfg.keys()))

    # Write relay bat
    relay_path = relay_root / f"{key_name}.bat"
    relay_content = _expand(relay_tmpl, root, phys_root, drive)
    _write_relay(relay_path, relay_content)

    # Resolve icon
    icon_val = _resolve_icon(entry.get("icon", ""), paths, relay_root, key_name)

    # Write registry keys
    written_keys = []
    errors = []
    for target_name in targets:
        target_cfg = targets_cfg.get(target_name)
        if not target_cfg:
            errors.append(f"unknown registry target: {target_name}")
            print(f"  [Warning] Unknown target '{target_name}' — skipped")
            continue
        path_base = target_cfg["path"]
        arg       = target_cfg["arg"]
        full_path = f"{path_base}\\{key_name}"
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_path)
            winreg.SetValueEx(key, "",        0, winreg.REG_SZ, label)
            winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, label)
            if icon_val:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_val)
            cmd_key = winreg.CreateKey(key, "command")
            # Outer quotes required for cmd /c "a" "b" to parse correctly
            cmd_str = f'cmd.exe /c ""{relay_path}" "{arg}""'
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)
            winreg.CloseKey(key)
            written_keys.append(f"HKCU\\{full_path}")
        except Exception as e:
            errors.append(f"registry write failed: {full_path}: {e}")
            print(f"  [Warning] Registry write failed ({full_path}): {e}")

    if errors:
        print(f"  [Fail] Context menu entry incomplete: {key_name} — {label}")
    else:
        print(f"  [OK] Context menu entry registered: {key_name} — {label}")
    return {
        "key_name":  key_name,
        "relay":     str(relay_path),
        "reg_keys":  written_keys,
        "_errors":   errors,
    }


def _hkcu_key_state(reg_key: str) -> str:
    relative = reg_key.replace("HKEY_CURRENT_USER\\", "").replace("HKCU\\", "")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, relative, 0, winreg.KEY_READ)
        winreg.CloseKey(key)
        return "present"
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unknown"


def _unregister_entry(key_name: str, targets_cfg: dict, relay_root: Path) -> list[str]:
    errors = []
    for target_cfg in targets_cfg.values():
        full_reg = f"HKCU\\{target_cfg['path']}\\{key_name}"
        try:
            subprocess.run(["reg", "delete", full_reg, "/f"], capture_output=True)
        except OSError:
            pass
        state = _hkcu_key_state(full_reg)
        if state != "absent":
            errors.append(f"registry key removal {state}: {full_reg}")
    for ext in (".bat", ".ico"):
        p = relay_root / f"{key_name}{ext}"
        if p.exists():
            try:
                p.unlink()
            except OSError as exc:
                errors.append(f"relay removal failed: {p}: {exc}")
        if p.exists():
            errors.append(f"relay remains: {p}")
    if errors:
        print(f"  [Fail] Entry removal incomplete: {key_name}")
    else:
        print(f"  [OK] Entry removed: {key_name}")
    return errors


def _clean_orphans(base_key: str, targets_cfg: dict, relay_root: Path) -> None:
    """Remove stale SandboxRun_ keys whose relay bat no longer points to a valid path."""
    for target_cfg in targets_cfg.values():
        path_base = target_cfg["path"]
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path_base, 0, winreg.KEY_READ) as key:
                i = 0
                orphans = []
                while True:
                    try:
                        subkey = winreg.EnumKey(key, i)
                        if subkey.startswith("SandboxRun_"):
                            relay = relay_root / f"{subkey}.bat"
                            if not relay.exists():
                                orphans.append(subkey)
                            else:
                                content = relay.read_text(encoding="mbcs", errors="ignore")
                                m = re.search(r'set "SANDBOX_ROOT=(.*?)"', content, re.IGNORECASE)
                                if m and not Path(m.group(1)).exists():
                                    orphans.append(subkey)
                        i += 1
                    except OSError:
                        break
            for subkey in orphans:
                subprocess.run(
                    ["reg", "delete", f"HKCU\\{path_base}\\{subkey}", "/f"],
                    capture_output=True,
                )
                for ext in (".bat", ".ico"):
                    p = relay_root / f"{subkey}{ext}"
                    if p.exists():
                        p.unlink()
                print(f"  [OK] Orphan removed: {subkey}")
        except Exception:
            continue


def apply(ctx: dict) -> dict:
    """Register all enabled context menu entries from context_menu.json."""
    base_dir   = ctx["base_dir"]
    sys_dir    = ctx["sys_dir"]
    paths      = ctx["paths"]
    virt_state = ctx.get("state", {})

    cfg = _load_context_menu(sys_dir)
    if not cfg:
        # A missing/empty context_menu.json is a valid state (context menus
        # intentionally disabled) — skip, do NOT fail the install pipeline.
        print("  [Warning] context_menu.json missing or empty — skipped (no context menus)")
        return {"status": "success", "operation": "registry.apply", "skipped": True}

    drive      = virt_state.get("subst_drive") or base_dir.drive.rstrip(":")
    root       = str(Path(f"{drive}:\\")) if virt_state.get("subst_drive") else str(base_dir)
    phys_root  = str(base_dir)
    relay_root = Path(os.environ.get("LOCALAPPDATA", ""))
    base_key   = _registry_key_name(Path(root))
    targets_cfg = cfg.get("registry", {}).get("targets", {})

    print(f"\n{'='*50}")
    print(f" Registrar: apply — {base_dir.name}")
    print(f"{'='*50}")

    # Orphan cleanup
    _clean_orphans(base_key, targets_cfg, relay_root)

    entries = cfg.get("entries", [])
    written = []
    errors = []
    if not entries:
        # No entries configured is a valid state, not a pipeline failure.
        print("  [Warning] No entries in context_menu.json — nothing to register")
    for entry in entries:
        if not entry.get("enabled", True):
            key_name = f"{base_key}_{_safe_key(entry.get('id', 'entry'))}"
            errors.extend(_unregister_entry(key_name, targets_cfg, relay_root))
            continue
        record = _register_entry(entry, cfg, base_key, relay_root, paths, root, phys_root, drive)
        if record:
            errors.extend(record.pop("_errors", []))
            written.append(record)

    # Windows 11 classic context menu (HKCU per-user)
    if cfg.get("win11_classic_menu", False):
        clsid = cfg.get("registry", {}).get("win11_classic_menu_clsid", "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}")
        win11_key = rf"Software\Classes\CLSID\{clsid}\InprocServer32"
        try:
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, win11_key)
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "")
            winreg.CloseKey(k)
            print(f"  [OK] Windows 11 classic menu enabled")
        except Exception as e:
            errors.append(f"Windows 11 classic-menu registration failed: {e}")
            print(f"  [Warning] Win11 classic menu: {e}")

    ctx["state"]["registry_entries"] = written
    ctx["state"]["relay_root"]       = str(relay_root)
    ctx["state"]["base_key"]         = base_key
    if errors:
        print(f"\n  Apply incomplete: {'; '.join(errors)}")
        return {"status": "failed", "operation": "registry.apply", "errors": errors}
    print("\n  Apply complete.")
    return {"status": "success"}


def remove(ctx: dict) -> dict:
    """Unregister context menu entries using saved state or context_menu.json."""
    base_dir   = ctx["base_dir"]
    sys_dir    = ctx["sys_dir"]
    prior      = _load_state(ctx)
    relay_root = Path(os.environ.get("LOCALAPPDATA", ""))

    cfg         = _load_context_menu(sys_dir)
    targets_cfg = cfg.get("registry", {}).get("targets", {})

    print(f"\n{'='*50}")
    print(f" Registrar: remove — {base_dir.name}")
    print(f"{'='*50}")
    errors = []
    if not cfg:
        # Missing/empty config is fine on remove — saved prior state (below) is
        # the authoritative teardown source; do NOT fail the unregister pipeline.
        print("  [Warning] context_menu.json missing or empty — using saved state for teardown")

    # Use saved state if available (most reliable)
    saved_entries = prior.get("registry_entries", [])
    if saved_entries:
        for record in saved_entries:
            key_name = record.get("key_name", "")
            # Remove relay
            relay = Path(record.get("relay", ""))
            for ext in ("", ".ico"):
                p = Path(str(relay).rstrip(".bat") + ext) if ext else relay
                if p.exists():
                    try:
                        p.unlink()
                    except OSError as exc:
                        errors.append(f"relay removal failed: {p}: {exc}")
                if p.exists():
                    errors.append(f"relay remains: {p}")
            # Remove registry keys
            for reg_key in record.get("reg_keys", []):
                try:
                    subprocess.run(["reg", "delete", reg_key.replace("HKCU\\", "HKCU\\"), "/f"], capture_output=True)
                except OSError:
                    pass
                state = _hkcu_key_state(reg_key)
                if state != "absent":
                    errors.append(f"registry key removal {state}: {reg_key}")
            print(f"  [OK] Removed: {key_name}")
    else:
        # Fallback: derive base_key from base_dir and remove all matching entries
        base_key = prior.get("base_key") or _registry_key_name(base_dir)
        for entry in cfg.get("entries", []):
            key_name = f"{base_key}_{_safe_key(entry.get('id', 'entry'))}"
            errors.extend(_unregister_entry(key_name, targets_cfg, relay_root))

    # Remove Windows 11 classic menu key
    if cfg.get("win11_classic_menu", False):
        clsid    = cfg.get("registry", {}).get("win11_classic_menu_clsid", "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}")
        win11_key = rf"Software\Classes\CLSID\{clsid}"
        try:
            subprocess.run(["reg", "delete", f"HKCU\\{win11_key}", "/f"], capture_output=True)
        except OSError:
            pass
        state = _hkcu_key_state(f"HKCU\\{win11_key}")
        if state != "absent":
            errors.append(f"registry key removal {state}: HKCU\\{win11_key}")
        print(f"  [OK] Windows 11 classic menu key removed")

    # Orphan cleanup sweep
    base_key = prior.get("base_key") or _registry_key_name(base_dir)
    _clean_orphans(base_key, targets_cfg, relay_root)

    if errors:
        print(f"\n  Remove incomplete: {'; '.join(errors)}")
        return {"status": "failed", "operation": "registry.remove", "errors": errors}
    print("\n  Remove complete.")
    return {"status": "success"}
