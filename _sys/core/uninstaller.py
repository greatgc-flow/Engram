"""
_sys/core/uninstaller.py - Safe, allowlist-based uninstaller for Engram.

Contract (Ratified §6):
- Deletion is strictly allowlist-based; anything not positively identified
  as Engram program files is kept and reported.
- Default uninstall preserves .engram/, workspace/, and legacy user items.
- Link guard refuses deletion if any junction or symlink exists under delete targets.
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
import subprocess
import sys
from typing import List, Tuple
import uuid

# Constant list of top-level _sys program entries for v3.2.7 (Ratified §6.1)
V326_SYS_PROGRAM_ENTRIES = {
    "checks",
    "cli",
    "config",
    "context_menu.json",
    "core",
    "data",
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

ROOT_PROGRAM_NAMES = {
    "engram.exe",
    "engram.cmd",
    "readme.md",
    "license",
    "wrapper.cs",
    "convention.md",
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

            if name_lower == "_sys":
                continue  # Handled in detail under _sys
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
            elif name_lower in ROOT_PROGRAM_NAMES or name_lower.endswith(".bat"):
                plan.targets.append(entry_path)
            else:
                # Unknown root entry
                plan.items_to_keep.append((entry_path, "user-authored or external item"))

    # 2. Scan entries under _sys
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


def check_links_under_targets(targets: List[Path]) -> List[Path]:
    """Scan targets for junctions or symlinks. Returns list of detected links."""
    links = []
    for t in targets:
        if not t.exists():
            continue

        # Check target itself
        try:
            if t.is_symlink() or (hasattr(t, "is_junction") and t.is_junction()):
                links.append(t)
                continue
        except OSError:
            pass

        if t.is_dir():
            for root, dirs, files in os.walk(t):
                for d in dirs:
                    p = Path(root) / d
                    try:
                        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                            links.append(p)
                    except OSError:
                        pass
                for f in files:
                    p = Path(root) / f
                    try:
                        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                            links.append(p)
                    except OSError:
                        pass
    return links


def run(ctx: dict) -> None:
    """Main uninstaller execution entry point invoked via dispatch pipeline."""
    base_dir = ctx["base_dir"]
    sys_dir = ctx.get("sys_dir", base_dir / "_sys")

    # Parse arguments from ctx["args"]
    args = ctx.get("args", [])
    yes = ("--yes" in args) or ("-y" in args)
    purge_data = "--purge-data" in args

    plan = plan_uninstall(base_dir=base_dir, sys_dir=sys_dir, purge_data=purge_data)

    # 1. Link guard
    links = check_links_under_targets(plan.targets)
    if links:
        print("[Error] Refusing to uninstall: symlink or junction found under removal targets:")
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
    state_file = ctx.get("paths", {}).get("state", sys_dir / "data" / "state") / "register.state.json"
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
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_dest),
            "-PlanPath",
            str(plan_file),
        ],
        cwd=str(temp_dir),
        creationflags=flags,
        close_fds=True,
    )
    sys.exit(0)
