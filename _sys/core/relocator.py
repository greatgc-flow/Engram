import os
import json
import shutil
from pathlib import Path
from core.config import config

def relocate():
    """Detects drive letter changes and patches hardcoded paths in AI peer configs."""
    # current_base is the physical path where _sys resides
    current_base = config.get_base_dir()
    sys_dir = config.get_sys_dir()
    data_dir = sys_dir / "data"
    last_path_file = data_dir / "last_base_dir.txt"
    
    last_base_str = ""
    if last_path_file.exists():
        try:
            last_base_str = last_path_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    
    current_base_str = str(current_base)
    
    # Only relocate if we have a record of a previous path and it's different
    if last_base_str and last_base_str != current_base_str:
        print(f"\n[Relocator] Drive move detected: {last_base_str} -> {current_base_str}")
        
        # Files to patch (Claude Code internal configs that store absolute paths)
        targets = [
            sys_dir / "claude" / "project" / "settings.local.json",
            sys_dir / "claude" / "config" / "daemon" / "roster.json",
            sys_dir / "claude" / "config" / "plugins" / "known_marketplaces.json",
        ]
        
        # Files to delete (Runtime caches/locks that are environment-sensitive)
        to_delete = [
            sys_dir / "claude" / "config" / "daemon.lock",
            sys_dir / "claude" / "config" / ".claude.json",
        ]
        
        # Replacement patterns: Handle both backslash and forward slash variants
        # 1. Normal backslash: E:\
        # 2. Double backslash: E:\\ (JSON escaped)
        # 3. Forward slash: E:/
        replacements = [
            (last_base_str, current_base_str),
            (last_base_str.replace("\\", "\\\\"), current_base_str.replace("\\", "\\\\")),
            (last_base_str.replace("\\", "/"), current_base_str.replace("\\", "/")),
        ]
        
        for target in targets:
            if target.exists():
                print(f"  [i] Patching: {target.relative_to(current_base)}")
                try:
                    content = target.read_text(encoding="utf-8")
                    changed = False
                    for old, new in replacements:
                        if old in content:
                            content = content.replace(old, new)
                            changed = True
                    if changed:
                        target.write_text(content, encoding="utf-8")
                except Exception as e:
                    print(f"  [!] Failed to patch {target.name}: {e}")
        
        for item in to_delete:
            if item.exists():
                print(f"  [i] Removing cache: {item.relative_to(current_base)}")
                try:
                    if item.is_dir(): shutil.rmtree(item)
                    else: item.unlink()
                except Exception as e:
                    print(f"  [!] Failed to delete {item.name}: {e}")
        print("[Relocator] Patching complete.\n")

    # Always update the last path file to current base
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        last_path_file.write_text(current_base_str, encoding="utf-8")
    except Exception as e:
        print(f"[Relocator] Warning: Could not update last_base_dir.txt: {e}")

if __name__ == "__main__":
    relocate()
