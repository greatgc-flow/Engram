"""
_sys/core/uninstaller.py - Safe, allowlist-based uninstaller for Engram.

Contract (Ratified §6):
- Deletion is strictly allowlist-based; anything not positively identified
  as Engram program files is kept and reported.
- Default uninstall preserves .engram/, workspace/, and legacy user items.
- Link guard allows file reparse points (the link itself is deleted) and
  refuses external or unverifiable directory junctions/symlinks.
- Two-tier confirmation: prompt 1 bypassed by --yes; prompt 2 (--purge-data)
  requires typing the folder basename and cannot be bypassed.
- Hand-off to static PowerShell helper (uninstall_helper.ps1) with parent wait.
"""
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, List, Tuple
import uuid

_CORE_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CORE_DIR.parent
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from root import bootstrap_root_package, find_root  # noqa: E402
bootstrap_root_package(_SYS_DIR)

from core.layout import INSTALL_ROOT_ENTRIES
from core import cli_help, provisioner, state_paths

# Constant list of top-level _sys program entries for v3.2.7 (Ratified §6.1)
V326_SYS_PROGRAM_ENTRIES = {
    "checks",
    "cli",
    "config",
    "context_menu.json",
    "core",
    "data",
    "defaults",
    "dispatch.json",
    "docs",
    "env",
    "env.json",
    "local.config.bat.template",
    "managed-links.json",
    "paths.json",
    "runtimes.json",
    "start.bat",
    "tests",
    "tool-catalog.v1.json",
    "tools",
}


@dataclass
class UninstallPlan:
    base_dir: Path
    sys_dir: Path
    purge_data: bool
    targets: List[Path] = field(default_factory=list)
    items_to_keep: List[Tuple[Path, str]] = field(default_factory=list)

    def compute_removal_stats(self) -> Tuple[int, int]:
        """Compute total file count and byte size of planned removal targets."""
        total_count = 0
        total_bytes = 0
        for t in self.targets:
            if not t.exists():
                continue
            if t.is_file():
                total_count += 1
                try:
                    total_bytes += t.stat().st_size
                except OSError:
                    pass
            elif t.is_dir():
                for root, _, files in os.walk(t):
                    for f in files:
                        p = Path(root) / f
                        total_count += 1
                        try:
                            total_bytes += p.stat().st_size
                        except OSError:
                            pass
        return total_count, total_bytes


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def plan_uninstall(base_dir: Path, sys_dir: Path, purge_data: bool = False) -> UninstallPlan:
    """Pure function computing allowable removal targets and preserved items."""
    base_dir = Path(base_dir).resolve()
    sys_dir = Path(sys_dir).resolve()
    plan = UninstallPlan(base_dir=base_dir, sys_dir=sys_dir, purge_data=purge_data)

    # 1. Scan root entries in base_dir
    if base_dir.exists() and base_dir.is_dir():
        for entry in os.scandir(base_dir):
            entry_path = Path(entry.path)
            name_lower = entry.name.lower()

            if name_lower == sys_dir.name.lower():
                continue  # Handled in detail under sys_dir
            elif name_lower == ".engram":
                if purge_data:
                    plan.targets.append(entry_path)
                else:
                    plan.items_to_keep.append((entry_path, "your AI-CLI settings, memory and credentials"))
            elif name_lower == "workspace":
                if purge_data:
                    plan.targets.append(entry_path)
                else:
                    plan.items_to_keep.append((entry_path, "your projects"))
            elif name_lower in {s.lower() for s in INSTALL_ROOT_ENTRIES} or name_lower.endswith(".bat"):
                plan.targets.append(entry_path)
            elif entry.name.startswith("."):
                if purge_data:
                    plan.targets.append(entry_path)
                else:
                    plan.items_to_keep.append((entry_path, "custom configuration or data directory"))
            else:
                # Unknown root entry
                plan.items_to_keep.append((entry_path, "user-authored or external item"))

    # 2. Scan entries under sys_dir
    if sys_dir.exists() and sys_dir.is_dir():
        for entry in os.scandir(sys_dir):
            entry_path = Path(entry.path)
            name = entry.name
            name_lower = name.lower()

            # local.config.bat is user-authored and MUST be kept
            if name_lower == "local.config.bat":
                plan.items_to_keep.append((entry_path, "user-authored local configuration"))
            elif name in V326_SYS_PROGRAM_ENTRIES or name_lower in {s.lower() for s in V326_SYS_PROGRAM_ENTRIES}:
                plan.targets.append(entry_path)
            else:
                # Legacy items like claude/, codex/, ai/, common/ or other user files
                plan.items_to_keep.append((entry_path, "legacy or user-authored item"))

    return plan


def _path_is_within(path: Path, roots: List[Path]) -> bool:
    """Return whether *path* is lexically inside one of *roots*.

    The roots intentionally are not resolved through reparse points: if a
    planned removal target is itself a junction, resolving both sides would
    make an external target appear safe by definition.
    """
    candidate = os.path.normcase(os.path.abspath(path))
    for root in roots:
        boundary = os.path.normcase(os.path.abspath(root))
        try:
            if os.path.commonpath((candidate, boundary)) == boundary:
                return True
        except ValueError:
            # Different Windows drives cannot have a common path.
            continue
    return False


def check_links_under_targets(targets: List[Path]) -> List[Path]:
    """Return unsafe directory links that escape the removal target set.

    Python virtual environments may legitimately contain file symlinks or
    other file reparse points (DLL/PYD/ZIP/EXE launch shims). Removing such a
    path removes the link itself; it does not traverse into the linked file,
    so those entries must not block uninstall. Directory symlinks/junctions
    are different: an external target could make recursive deletion escape
    the allowlisted installation tree, so they remain fail-closed.
    """
    roots = [Path(os.path.abspath(t)) for t in targets]
    unsafe_links: List[Path] = []

    def inspect_link(path: Path) -> bool:
        """Inspect one link and return True when os.walk must not enter it."""
        try:
            is_link = path.is_symlink() or (
                hasattr(path, "is_junction") and path.is_junction()
            )
            if not is_link:
                return False
            if not path.is_dir():
                # File links/reparse points are removed as directory entries.
                return False
            try:
                destination = path.resolve(strict=True)
            except OSError:
                # An unreadable directory target cannot be proven safe.
                unsafe_links.append(path)
                return True
            if not _path_is_within(destination, roots):
                unsafe_links.append(path)
            return True
        except OSError:
            # Inspection failure for a candidate directory is fail-closed.
            unsafe_links.append(path)
            return True

    for t in targets:
        if not t.exists() and not t.is_symlink():
            continue

        # Check target itself
        if inspect_link(t):
            continue

        if t.is_dir():
            for root, dirs, _files in os.walk(t, followlinks=False):
                # Explicitly prune every directory link. Internal links are
                # safe to delete, but never need to be traversed to do so.
                for name in list(dirs):
                    if inspect_link(Path(root) / name):
                        dirs.remove(name)
    return unsafe_links


def run(ctx: dict) -> dict[str, Any] | None:
    """Main uninstaller execution entry point invoked via dispatch pipeline."""
    args = ctx.get("args", []) or []
    if cli_help.wants_help(args):
        cli_help.print_verb_help("uninstall")
        return {"status": "success", "detail": "help displayed"}
    for a in args:
        if a not in ("--yes", "-y", "--purge-data", "--dry-run", "--apply"):
            if a.startswith("-"):
                cli_help.unknown_option("uninstall", a)
            cli_help.unexpected_argument("uninstall", a)

    base_dir = ctx["base_dir"]
    sys_dir = ctx.get("sys_dir") or find_root(base_dir)

    # Parse arguments from ctx["args"]
    yes = ("--yes" in args) or ("-y" in args)
    purge_data = "--purge-data" in args
    dry_run = "--dry-run" in args

    plan = plan_uninstall(base_dir=base_dir, sys_dir=sys_dir, purge_data=purge_data)

    # 1. Link guard
    links = check_links_under_targets(plan.targets)
    if links:
        print("[Error] Refusing to uninstall: external or unverifiable directory link found under removal targets:")
        for link in links:
            print(f"  - {link}")
        sys.exit(1)

    # 2. Confirmation prompts
    count, size_bytes = plan.compute_removal_stats()
    print(f"Will remove ({count} files, {_format_size(size_bytes)}):")
    for t in plan.targets:
        print(f"  - {t}")
    print("\nWill keep:")
    for path, desc in plan.items_to_keep:
        suffix = "/" if path.is_dir() else ""
        print(f"  - {path.name}{suffix}  {desc}")
    print()

    if dry_run:
        print("[engram uninstall] Dry-run preview complete: no changes were made.")
        return {"status": "dry_run", "plan": plan}

    if not yes:
        try:
            resp = input(f"Uninstall Engram from {base_dir}? [y/N] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(3)
        if resp.lower() != "y":
            print("Uninstall cancelled.")
            sys.exit(3)

    if purge_data:
        try:
            prompt = f"Type the folder name '{base_dir.name}' to also permanently delete .engram/ and workspace/: "
            resp = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(3)
        if resp != base_dir.name:
            print("Folder name does not match. Aborting.")
            sys.exit(3)

    # 3. Journal setup
    install_id = hashlib.sha256(str(base_dir.resolve()).lower().encode("utf-8")).hexdigest()
    localappdata = ctx.get("paths", {}).get("localappdata") or Path(os.environ.get("LOCALAPPDATA", ""))
    journal_dir = localappdata / "Engram" / "uninstall" / install_id
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "journal.json"

    journal = {
        "operation": "uninstall",
        "status": "IN_PROGRESS",
        "steps": [],
        "error_recoverable": False,
    }
    journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Host cleanup
    state_file = ctx.get("paths", {}).get("state", state_paths.state_dir(sys_dir)) / state_paths.REGISTER_STATE_FILENAME
    if state_file.exists():
        from core.registrar import remove
        try:
            remove(ctx)
            journal["steps"].append("registry_cleanup")
            journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            journal["status"] = "FAILED_RECOVERABLE"
            journal["error_recoverable"] = True
            journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[Error] Host cleanup failed: {e}")
            sys.exit(1)

    # 5. Hand-off to external PowerShell helper
    nonce = uuid.uuid4().hex
    temp_root = Path(os.environ.get("TEMP", "C:/Temp"))
    temp_dir = temp_root / "EngramUninstall" / install_id / nonce
    temp_dir.mkdir(parents=True, exist_ok=True)

    plan_file = temp_dir / "plan.json"
    plan_payload = {
        "targets": [str(t) for t in plan.targets],
        "base_dir": str(plan.base_dir),
        "sys_dir": str(plan.sys_dir),
        "journal_path": str(journal_path),
        "parent_pid": os.getpid(),
    }
    plan_file.write_text(json.dumps(plan_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    helper_src = sys_dir / "core" / "uninstall_helper.ps1"
    if not helper_src.exists():
        helper_src = Path(__file__).resolve().parent / "uninstall_helper.ps1"
    helper_dest = temp_dir / "uninstall_helper.ps1"
    shutil.copyfile(helper_src, helper_dest)

    print("  - Handing off to external uninstall helper...")
    provisioner._launch_detached_powershell_helper(helper_dest, plan_file, temp_dir)
    sys.exit(0)
