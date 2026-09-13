import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from _sys.checks.check_tool_updates import _atomic_write_json

logger = logging.getLogger(__name__)

def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _merge_component_maps(
    ours: Dict[str, Any], 
    base: Dict[str, Any], 
    theirs: Dict[str, Any], 
    reports: List[str], 
    path_name: str
) -> Dict[str, Any]:
    merged = {}
    all_keys = set(ours.keys()) | set(base.keys()) | set(theirs.keys())
    
    for key in all_keys:
        our_val = ours.get(key)
        base_val = base.get(key)
        their_val = theirs.get(key)
        
        if key in theirs:
            if key not in ours:
                # Component only in theirs -> add
                merged[key] = their_val
            else:
                if our_val == base_val:
                    # ours == base -> take theirs
                    merged[key] = their_val
                else:
                    # ours != base -> keep ours (locally updated) and report it
                    if our_val != their_val:
                        reports.append(f"{path_name} component {key} kept local modifications instead of taking upstream update.")
                    merged[key] = our_val
        else:
            # Not in theirs
            if key in base:
                # Component only in base
                if our_val == base_val:
                    # remove if ours == base
                    pass
                else:
                    # else keep and report
                    reports.append(f"{path_name} component {key} kept local modifications despite upstream removal.")
                    merged[key] = our_val
            else:
                # Not in theirs, not in base -> local addition
                # ours != base (since base is None)
                merged[key] = our_val
                
    # To ensure stable ordering based on 'ours' then 'theirs'
    ordered_merged = {}
    for k in ours:
        if k in merged:
            ordered_merged[k] = merged[k]
    for k in theirs:
        if k in merged and k not in ordered_merged:
            ordered_merged[k] = merged[k]
    for k in merged:
        if k not in ordered_merged:
            ordered_merged[k] = merged[k]
            
    return ordered_merged

# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="Called dynamically by P1-6 layout migration."
def merge_declarations(dry_run: bool = False) -> List[str]:
    files = ["runtimes.json", "tool-catalog.v1.json"]
    
    defaults_dir = Path("_sys/defaults")
    live_dir = Path("_sys")
    base_state_dir = Path("_sys/data/state/defaults-base")
    manifest_base_dir = Path("_sys/core/release-manifests/3.2.6-defaults")
    
    return merge_declarations_impl(defaults_dir, live_dir, base_state_dir, manifest_base_dir, files, dry_run=dry_run)

def merge_declarations_impl(defaults_dir: Path, live_dir: Path, base_state_dir: Path, manifest_base_dir: Path, files: List[str], dry_run: bool = False) -> List[str]:
    if not dry_run:
        base_state_dir.mkdir(parents=True, exist_ok=True)
    
    all_reports = []
    
    for filename in files:
        live_path = live_dir / filename
        default_path = defaults_dir / filename
        
        if not live_path.exists():
            if default_path.exists() and not dry_run:
                shutil.copy2(default_path, live_path)
            continue
            
        try:
            ours = _load_json(live_path)
            theirs = _load_json(default_path) if default_path.exists() else {}
            
            base_path = base_state_dir / filename
            manifest_path = manifest_base_dir / filename
            
            if base_path.exists():
                base = _load_json(base_path)
            elif manifest_path.exists():
                base = _load_json(manifest_path)
            else:
                base = {}
                
            reports = []
            merged = {}
            
            if filename == "runtimes.json":
                def flatten(d):
                    flat = {}
                    for section in ["runtimes", "tools"]:
                        if section in d:
                            for name, val in d[section].items():
                                flat[f"{section}/{name}"] = val
                    return flat
                
                our_flat = flatten(ours)
                base_flat = flatten(base)
                their_flat = flatten(theirs)
                
                merged_flat = _merge_component_maps(our_flat, base_flat, their_flat, reports, filename)
                
                for k, v in theirs.items():
                    if k not in ["runtimes", "tools"]:
                        merged[k] = v
                        
                for comp_key, val in merged_flat.items():
                    section, name = comp_key.split("/", 1)
                    if section not in merged:
                        merged[section] = {}
                    merged[section][name] = val
                    
            elif filename == "tool-catalog.v1.json":
                def flatten(d):
                    flat = {}
                    for tool in d.get("tools", []):
                        flat[tool["tool_id"]] = tool
                    return flat
                    
                our_flat = flatten(ours)
                base_flat = flatten(base)
                their_flat = flatten(theirs)
                
                merged_flat = _merge_component_maps(our_flat, base_flat, their_flat, reports, filename)
                
                for k, v in theirs.items():
                    if k != "tools":
                        merged[k] = v
                        
                merged["tools"] = list(merged_flat.values())
                
            if reports:
                for r in reports:
                    logger.info(r)
                all_reports.extend(reports)
                    
            if not dry_run:
                pre_merge_bak = base_state_dir / f"{filename}.pre-merge.bak"
                shutil.copy2(live_path, pre_merge_bak)
                
                _atomic_write_json(live_path, merged)
                
                if default_path.exists():
                    shutil.copy2(default_path, base_path)
                
        except Exception as e:
            logger.error(f"Failed to merge {filename}: {e}")
            sys.exit(1)
            
    return all_reports

# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="P1-6 orchestration wiring happens in a follow-up dispatch."
def m0_preflight(base_dir: Path, sys_dir: Path) -> bool:
    from _sys.core.doctor import check_legacy_host_integration
    result = check_legacy_host_integration(base_dir, sys_dir)
    if result.get("level") == "warning":
        # Reuse the already-correct instructions from the doctor check itself
        # (it accounts for both register.state.json's subst_drive AND the
        # legacy _sys/config.json SUBST_DRIVE_LETTER fallback) rather than
        # re-deriving a narrower version here that would print a placeholder
        # drive letter when only the config.json signal is present.
        print(result.get("detail", "legacy host integration recorded."))
        return False
    return True
# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="P1-6 wiring happens in follow-up dispatch."
def m1_retire_shipped_files(base_dir: Path, sys_dir: Path, dry_run: bool = False) -> tuple[bool, Dict[str, List[str]]]:
    import os

    current_manifest_path = sys_dir / "core" / "release-manifest.json"
    if not current_manifest_path.exists():
        return True, {"retired": [], "kept_modified": []}
    
    current_manifest = {}
    try:
        with open(current_manifest_path, "r", encoding="utf-8") as f:
            current_manifest = json.load(f).get("files", {})
    except Exception:
        pass

    layout_file = sys_dir / "data" / "state" / "layout.json"
    candidate_manifests = []
    manifests_dir = sys_dir / "core" / "release-manifests"
    
    engram_version = None
    if layout_file.exists():
        try:
            with open(layout_file, "r", encoding="utf-8") as f:
                engram_version = json.load(f).get("engram_version")
        except Exception:
            pass
            
    if engram_version and (manifests_dir / f"{engram_version}.json").exists():
        candidate_manifests.append(manifests_dir / f"{engram_version}.json")
    elif manifests_dir.exists():
        candidate_manifests.extend(manifests_dir.glob("*.json"))

    def _is_protected(rel_path_str: str) -> bool:
        p = rel_path_str.replace("\\", "/")
        if p in ("_sys/runtimes.json", "_sys/tool-catalog.v1.json"):
            return True
        protected_prefixes = (
            ".engram/",
            "workspace/",
            "_sys/env/",
            "_sys/tools/",
            "_sys/data/",
        )
        for pref in protected_prefixes:
            if p.startswith(pref):
                return True
        return False

    def _compute_sha256(file_path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().upper()

    to_retire = {}
    for cand in candidate_manifests:
        try:
            with open(cand, "r", encoding="utf-8") as f:
                files_map = json.load(f).get("files", {})
                for path_str, hash_val in files_map.items():
                    if path_str not in current_manifest:
                        if not _is_protected(path_str):
                            to_retire.setdefault(path_str, set()).add(hash_val)
        except Exception:
            pass

    retired = []
    kept_modified = []
    errors_occurred = False
    
    dirs_to_check = set()

    for path_str, expected_hashes in to_retire.items():
        file_path = base_dir / path_str
        if file_path.exists() and file_path.is_file():
            try:
                actual_hash = _compute_sha256(file_path)
                if actual_hash in expected_hashes:
                    if not dry_run:
                        file_path.unlink()
                    retired.append(path_str)
                    dirs_to_check.add(file_path.parent)
                else:
                    kept_modified.append(path_str)
            except Exception as e:
                logger.error(f"Error processing {path_str}: {e}")
                errors_occurred = True

    sorted_dirs = sorted(list(dirs_to_check), key=lambda p: len(p.parts), reverse=True)
    
    def _is_dir_protected(d: Path) -> bool:
        try:
            rel = d.relative_to(base_dir).as_posix()
        except ValueError:
            return True
        if rel == ".":
            return True
        
        protected_prefixes = (
            ".engram",
            "workspace",
            "_sys/env",
            "_sys/tools",
            "_sys/data",
        )
        for pref in protected_prefixes:
            if rel == pref or rel.startswith(pref + "/"):
                return True
        return False

    if not dry_run:
        for d in sorted_dirs:
            curr = d
            while curr != base_dir and curr.is_relative_to(base_dir):
                if _is_dir_protected(curr):
                    break
                if curr.exists() and curr.is_dir():
                    try:
                        if not any(curr.iterdir()):
                            curr.rmdir()
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Error removing dir {curr}: {e}")
                        errors_occurred = True
                        break
                else:
                    break
                curr = curr.parent

    return not errors_occurred, {"retired": retired, "kept_modified": kept_modified}

# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="P1-6 orchestration wiring happens in a follow-up dispatch"
def m2_move_engram_state(base_dir: Path, sys_dir: Path, dry_run: bool = False) -> tuple[bool, Dict[str, List[str]]]:
    import os
    
    moved = []
    external_left = []
    conflicts = []
    errors_occurred = False
    
    def is_owned(rel_path_str: str) -> bool:
        if rel_path_str in [".ai/tool_discovery_cache.json", ".ai/tool_deferred_retries.json"]:  # legacy-source: migration only
            return True
        if rel_path_str.startswith("_archive/logs/start_") and rel_path_str.endswith(".log"):  # legacy-source: migration only
            parts = rel_path_str.split("/")
            if len(parts) == 3:
                return True
        if rel_path_str.startswith("_archive/tool-updates/"):  # legacy-source: migration only
            return True
        return False
        
    def is_base_dir(rel_path_str: str) -> bool:
        return rel_path_str in [".ai", "_archive", "_archive/logs", "_archive/tool-updates"]  # legacy-source: migration only
        
    owned_to_move = []
    
    for root_name in [".ai", "_archive"]:  # legacy-source: migration only
        root_path = base_dir / root_name
        if root_path.exists() and root_path.is_dir():
            for p in root_path.rglob("*"):
                try:
                    rel = p.relative_to(base_dir).as_posix()
                except ValueError:
                    continue
                
                if is_base_dir(rel):
                    continue
                    
                if is_owned(rel):
                    owned_to_move.append(p)
                else:
                    external_left.append(rel)
                    
    dirs_to_check = set()
    
    for p in owned_to_move:
        try:
            rel = p.relative_to(base_dir).as_posix()
        except ValueError:
            continue
            
        if p.is_file():
            dst = None
            if rel == ".ai/tool_discovery_cache.json":  # legacy-source: migration only
                dst = sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json"
            elif rel == ".ai/tool_deferred_retries.json":  # legacy-source: migration only
                dst = sys_dir / "data" / "state" / "update" / "tool_deferred_retries.json"
            elif rel.startswith("_archive/logs/start_"):  # legacy-source: migration only
                dst = sys_dir / "data" / "logs" / "launcher" / p.name
            elif rel.startswith("_archive/tool-updates/"):  # legacy-source: migration only
                sub_rel = p.relative_to(base_dir / "_archive" / "tool-updates")  # legacy-source: migration only
                dst = sys_dir / "data" / "state" / "update" / "proposals" / sub_rel
                
            if dst:
                if dst.exists():
                    conflicts.append(rel)
                else:
                    try:
                        if not dry_run:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(p, dst)
                        moved.append(rel)
                        dirs_to_check.add(p.parent)
                    except Exception as e:
                        logger.error(f"Error moving {rel}: {e}")
                        errors_occurred = True
                        
    def _is_dir_allowed_to_remove(d: Path) -> bool:
        try:
            rel = d.relative_to(base_dir).as_posix()
        except ValueError:
            return False
        if rel == ".":
            return False
        allowed = [".ai", "_archive", "_archive/logs", "_archive/tool-updates"]  # legacy-source: migration only
        if rel in allowed:
            return True
        if rel.startswith("_archive/tool-updates/"):  # legacy-source: migration only
            return True
        return False
        
    for root_name in [".ai", "_archive/logs", "_archive/tool-updates", "_archive"]:  # legacy-source: migration only
        p = base_dir / root_name
        if p.exists() and p.is_dir():
            dirs_to_check.add(p)
            
    if not dry_run:
        sorted_dirs = sorted(list(dirs_to_check), key=lambda p: len(p.parts), reverse=True)
        for d in sorted_dirs:
            curr = d
            while curr != base_dir and curr.is_relative_to(base_dir):
                if not _is_dir_allowed_to_remove(curr):
                    break
                if curr.exists() and curr.is_dir():
                    try:
                        if not any(curr.iterdir()):
                            curr.rmdir()
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Error removing dir {curr}: {e}")
                        errors_occurred = True
                        break
                else:
                    break
                curr = curr.parent
            
    moved.sort()
    external_left.sort()
    conflicts.sort()
    
    return not errors_occurred, {
        "moved": moved,
        "external_left": external_left,
        "conflicts": conflicts
    }
# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="P1-6 orchestration wiring happens in a follow-up dispatch"
def migrate_layout(base_dir: Path, sys_dir: Path, dry_run: bool = False) -> int:
    import datetime
    from _sys.core.version import load_version_info
    
    if not m0_preflight(base_dir, sys_dir):
        return 1
        
    m1_ok, m1_report = m1_retire_shipped_files(base_dir, sys_dir, dry_run=dry_run)
    m2_ok, m2_report = m2_move_engram_state(base_dir, sys_dir, dry_run=dry_run)
    
    m3_report = merge_declarations(dry_run=dry_run)
    
    version_file = sys_dir / "data" / "state" / "version.json"
    if not version_file.exists():
        version_file = sys_dir / "core" / "version.json"
        
    engram_version = load_version_info(version_file).get("version", "unknown")
    
    migrated_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    
    report = {
        "retired": m1_report["retired"],
        "kept_modified": m1_report["kept_modified"],
        "moved": m2_report["moved"],
        "external_left": m2_report["external_left"],
        "conflicts": m2_report.get("conflicts", []),
        "merged": m3_report
    }
    
    layout_data = {
        "layout_version": 2,
        "engram_version": engram_version,
        "migrated_at": migrated_at,
        "report": report
    }
    
    print("\n--- Layout Migration Summary ---")
    if dry_run:
        print("[DRY RUN] No changes were made.")
    print(f"Engram Version: {engram_version}")
    print(f"Retired shipped files: {len(report['retired'])}")
    print(f"Kept modified shipped files: {len(report['kept_modified'])}")
    print(f"Moved engram state files: {len(report['moved'])}")
    print(f"Conflicts moving engram state files: {len(report['conflicts'])}")
    print(f"External/unknown legacy state left behind: {len(report['external_left'])}")
    print(f"Merge actions: {len(report['merged'])}")
    
    if not dry_run:
        layout_json_path = sys_dir / "data" / "state" / "layout.json"
        layout_json_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(layout_json_path, layout_data)
        
    if not m1_ok or not m2_ok:
        return 1
        
    return 0



# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="Called dynamically by core.dispatcher via dispatch.json."
def run_pipeline(ctx: dict) -> dict:
    base_dir = Path(ctx.get("base_dir", "."))
    sys_dir = Path(ctx.get("sys_dir", "_sys"))
    args = ctx.get("args", [])
    dry_run = "--dry-run" in args
    
    result = migrate_layout(base_dir, sys_dir, dry_run=dry_run)
    
    if result == 0:
        return {"status": "ok"}
    else:
        return {"status": "error"}
