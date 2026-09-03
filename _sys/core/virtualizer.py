"""
virtualizer.py - Directory junction management.
All managed junctions sourced from managed-links.json. No hardcoding.
"""
import os
import re
import json
import shutil
import subprocess
from pathlib import Path


def _load_managed_links(sys_dir: Path) -> dict:
    managed_links = sys_dir / "managed-links.json"
    if not managed_links.exists():
        pathmap_links = sys_dir / "data" / "state" / "pathmap" / "managed-links.json"
        if pathmap_links.exists():
            managed_links = pathmap_links
    if managed_links.exists():
        try:
            return json.loads(managed_links.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[virtualizer] managed-links.json error: {exc}")
    return {}


def _cmd(command: str) -> None:
    subprocess.run(command, shell=True, check=True, capture_output=True)


def _get_subst_mappings() -> dict:
    mappings = {}
    try:
        out = subprocess.check_output(["subst"], text=True, encoding="oem")
        for line in out.splitlines():
            m = re.match(r"^([A-Z]):\\: => (.*)$", line, re.IGNORECASE)
            if m:
                mappings[m.group(1).upper()] = Path(m.group(2).strip())
    except Exception:
        pass
    return mappings


def _on_error(func, path, exc_info):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _ensure_junction(host: Path, portable: Path) -> None:
    """Ensure host is a directory junction pointing to portable.
    If host exists as a regular directory (not a junction), merge its contents
    into portable before replacing it with a junction."""
    host = host.resolve()
    portable = portable.resolve()
    host.parent.mkdir(parents=True, exist_ok=True)
    portable.mkdir(parents=True, exist_ok=True)

    is_reparse = False
    try:
        st = host.lstat()
        is_reparse = os.path.islink(host) or getattr(st, "st_reparse_tag", 0) == 0xA0000003
    except FileNotFoundError:
        pass
    except OSError:
        raise

    if is_reparse:
        _cmd(f'rmdir "{host}"')
    elif host.exists():
        for item in list(host.iterdir()):
            if item.name == "settings.local.json":
                item.unlink()
                continue
            dest = portable / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(str(dest), onerror=_on_error)
                else:
                    os.chmod(str(dest), 0o777)
                    dest.unlink()
            shutil.move(str(item), str(portable))
        host.rmdir()
    _cmd(f'mklink /J "{host}" "{portable}"')


def _remove_junction(host: Path) -> bool:
    try:
        st = host.lstat()
        is_reparse = os.path.islink(host) or getattr(st, "st_reparse_tag", 0) == 0xA0000003
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if is_reparse:
        try:
            host.unlink()
        except Exception:
            try:
                os.rmdir(host)
            except Exception as e:
                print(f"  [Fail] Could not remove junction {host}: {e}")
                return False
    try:
        st = host.lstat()
        return not (os.path.islink(host) or getattr(st, "st_reparse_tag", 0) == 0xA0000003)
    except FileNotFoundError:
        return True
    except OSError:
        return False


def mount(ctx: dict) -> dict:
    """Create generic directory junctions from managed-links.json."""
    base_dir = ctx["base_dir"]
    sys_dir  = ctx["sys_dir"]
    registry = _load_managed_links(sys_dir)
    entries  = registry.get("entries", {})
    errors   = []
    junctions = []

    print(f"\n{'='*50}")
    print(f" Virtualizer: mount — {base_dir.name}")
    print(f"{'='*50}")

    for entry_id, entry in entries.items():
        link_path_raw = entry.get("relative_link_path", "")
        target_raw    = entry.get("relative_target_path", "")
        if link_path_raw.startswith("EXTERNAL:"):
            expanded = os.path.expandvars(link_path_raw[len("EXTERNAL:"):])
            host_path = Path(expanded)
        else:
            host_path = (sys_dir / link_path_raw).resolve()
        target_path = (sys_dir / target_raw).resolve()
        target_path.mkdir(parents=True, exist_ok=True)
        try:
            _ensure_junction(host_path, target_path)
            print(f"  [OK] {entry_id}: {host_path.name} → {target_raw}")
            junctions.append({"id": entry_id, "host": str(host_path), "target": str(target_path)})
        except Exception as exc:
            print(f"  [Fail] {entry_id}: {exc}")
            errors.append(f"{entry_id}: {exc}")

    ctx.setdefault("state", {})["junctions"] = junctions
    if errors:
        print(f"\n  Mount incomplete: {'; '.join(errors)}")
        return {"status": "failed", "operation": "virtual.mount", "errors": errors}
    print("\n  Mount complete.")
    return {"status": "success"}


def unmount(ctx: dict) -> dict:
    """Remove generic directory junctions defined in managed-links.json."""
    base_dir = ctx["base_dir"]
    sys_dir  = ctx["sys_dir"]
    registry = _load_managed_links(sys_dir)
    entries  = registry.get("entries", {})
    errors   = []

    print(f"\n{'='*50}")
    print(f" Virtualizer: unmount — {base_dir.name}")
    print(f"{'='*50}")

    for entry_id, entry in entries.items():
        link_path_raw = entry.get("relative_link_path", "")
        if link_path_raw.startswith("EXTERNAL:"):
            expanded = os.path.expandvars(link_path_raw[len("EXTERNAL:"):])
            host_path = Path(expanded)
        else:
            host_path = (sys_dir / link_path_raw).resolve()
        if not _remove_junction(host_path):
            errors.append(f"could not remove junction {host_path}")
        else:
            print(f"  [OK] {entry_id}: junction removed ({host_path.name})")

    if errors:
        print(f"\n  Unmount incomplete: {'; '.join(errors)}")
        return {"status": "failed", "operation": "virtual.unmount", "errors": errors}
    print("\n  Unmount complete.")
    return {"status": "success"}


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def _cli_apply(sys_dir: Path, base_dir: Path, force: bool) -> None:
    """Re-create all managed directory junctions from managed-links.json."""
    managed_links = sys_dir / "managed-links.json"
    if not managed_links.exists():
        pathmap_links = sys_dir / "data" / "state" / "pathmap" / "managed-links.json"
        if pathmap_links.exists():
            managed_links = pathmap_links

    if managed_links.exists():
        try:
            registry = json.loads(managed_links.read_text(encoding="utf-8"))
            entries = registry.get("entries", {})
            print(f"[apply] Using managed-links.json ({len(entries)} entries)")
            for entry_id, entry in entries.items():
                link_path_raw = entry.get("relative_link_path", "")
                target_raw    = entry.get("relative_target_path", "")
                if link_path_raw.startswith("EXTERNAL:"):
                    expanded = os.path.expandvars(link_path_raw[len("EXTERNAL:"):])
                    host_path = Path(expanded)
                else:
                    host_path = sys_dir / link_path_raw
                target_path = sys_dir / target_raw
                if force:
                    _remove_junction(host_path)
                target_path.mkdir(parents=True, exist_ok=True)
                try:
                    _ensure_junction(host_path, target_path)
                    print(f"  [OK] {entry_id}: {host_path.name} → {target_raw}")
                except Exception as exc:
                    print(f"  [Fail] {entry_id}: {exc}")
            return
        except Exception as exc:
            print(f"[apply] managed-links.json error: {exc}")
            return
    print("[apply] No managed-links.json found. Nothing to apply.")


def _cli_status(sys_dir: Path, base_dir: Path) -> None:
    """Show current junction state for all managed links."""
    registry = _load_managed_links(sys_dir)
    entries = registry.get("entries", {})
    print(f"{'─'*60}")
    print(f"  Junction Status  (sys_dir: {sys_dir})")
    print(f"{'─'*60}")
    for entry_id, entry in entries.items():
        link_path_raw = entry.get("relative_link_path", "")
        target_raw    = entry.get("relative_target_path", "")
        if link_path_raw.startswith("EXTERNAL:"):
            expanded = os.path.expandvars(link_path_raw[len("EXTERNAL:"):])
            host_path = Path(expanded)
        else:
            host_path = (sys_dir / link_path_raw).resolve()
        portable = (sys_dir / target_raw).resolve()
        try:
            st = host_path.lstat()
            is_junc = (st.st_file_attributes & 0x400) != 0 if hasattr(st, 'st_file_attributes') else False
        except FileNotFoundError:
            is_junc = False
        print(f"  {entry_id:<20}  {str(host_path):<40}  {'JUNCTION' if is_junc else 'DIR/MISSING'}  → {portable}")
    print(f"{'─'*60}")


if __name__ == "__main__":
    import argparse

    _self_sys_dir  = Path(__file__).resolve().parent.parent
    _self_base_dir = _self_sys_dir.parent

    parser = argparse.ArgumentParser(description="virtualizer.py — junction management")
    sub = parser.add_subparsers(dest="cmd")

    p_apply = sub.add_parser("apply", help="Re-create all managed junctions")
    p_apply.add_argument("--force", action="store_true", help="Remove existing junctions before re-creating")
    p_apply.add_argument("--sys-dir", type=Path, default=_self_sys_dir)

    p_status = sub.add_parser("status", help="Show current junction state")
    p_status.add_argument("--sys-dir", type=Path, default=_self_sys_dir)

    args = parser.parse_args()

    if args.cmd == "apply":
        sd = args.sys_dir.resolve()
        _cli_apply(sd, sd.parent, force=args.force)
    elif args.cmd == "status":
        sd = args.sys_dir.resolve()
        _cli_status(sd, sd.parent)
    else:
        parser.print_help()
