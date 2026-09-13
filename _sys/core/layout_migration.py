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

# WIRING-EXEMPT: DYNAMIC_ENTRYPOINT reason="Called dynamically by P1-6 layout migration"
def merge_declarations() -> None:
    files = ["runtimes.json", "tool-catalog.v1.json"]
    
    defaults_dir = Path("_sys/defaults")
    live_dir = Path("_sys")
    base_state_dir = Path("_sys/data/state/defaults-base")
    manifest_base_dir = Path("_sys/core/release-manifests/3.2.6-defaults")
    
    merge_declarations_impl(defaults_dir, live_dir, base_state_dir, manifest_base_dir, files)

def merge_declarations_impl(defaults_dir: Path, live_dir: Path, base_state_dir: Path, manifest_base_dir: Path, files: List[str]) -> None:
    base_state_dir.mkdir(parents=True, exist_ok=True)
    
    for filename in files:
        live_path = live_dir / filename
        default_path = defaults_dir / filename
        
        if not live_path.exists():
            if default_path.exists():
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
                    
            pre_merge_bak = base_state_dir / f"{filename}.pre-merge.bak"
            shutil.copy2(live_path, pre_merge_bak)
            
            _atomic_write_json(live_path, merged)
            
            if default_path.exists():
                shutil.copy2(default_path, base_path)
                
        except Exception as e:
            logger.error(f"Failed to merge {filename}: {e}")
            sys.exit(1)
