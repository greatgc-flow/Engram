"""
updater.py - First-class update dispatch pipeline.
"""
import argparse
import sys
import shutil
import json
from pathlib import Path
from typing import Any

from checks import check_tool_updates
from core import provisioner
from core.doctor import check_components

_PORTABLE_ROOT = Path(__file__).resolve().parent.parent.parent
_SYS_DIR = _PORTABLE_ROOT / "_sys"


def _parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Updater runner")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--check", action="store_true", help="Stop after printing plan. Exit 1 if Could not check is non-empty")
    parser.add_argument("--dry-run", action="store_true", help="Discover and show proposal, apply nothing")
    return parser.parse_args(args)


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    args_list = ctx.get("args", [])
    try:
        args = _parse_args(args_list)
    except SystemExit as e:
        return {"status": "failed", "detail": f"Argument parsing failed with code {e.code}"}

    print(">>> Discovering updates...")
    sys_dir = _SYS_DIR
    
    try:
        payload = check_tool_updates.run(propose_diff=True)
    except Exception as e:
        return {"status": "failed", "detail": f"Update discovery failed: {e}"}

    if payload.get("errors"):
        return {"status": "failed", "detail": "Update discovery encountered errors", "errors": payload["errors"]}

    artifact_dir = payload.get("artifact_dir")
    if not artifact_dir:
        return {"status": "failed", "detail": "No artifact dir returned by update discovery"}
    
    runtimes_updates = []
    tools_updates = []
    ai_clis_updates = []
    
    for update in payload.get("updates_discovered", []):
        section = update.get("section")
        if section == "runtimes":
            runtimes_updates.append(update)
        elif section == "tools":
            tools_updates.append(update)
        elif section == "catalog":
            ai_clis_updates.append(update)
            
    repairs_needed = check_components(sys_dir).get("missing", [])
    not_checked = payload.get("not_checked", [])
    could_not_check = payload.get("could_not_check", [])
    
    has_actionable = bool(runtimes_updates or tools_updates or ai_clis_updates or repairs_needed)
    
    if not has_actionable and not could_not_check and not not_checked:
        print("Everything Engram can check is up to date.")
        if args.check:
            sys.exit(0)
        return {"status": "success", "detail": "No updates discovered"}

    if could_not_check:
        print("\nCould not check (provider failures):")
        for cnc in could_not_check:
            print(f"  - {cnc.get('component')} ({cnc.get('error_type')}: {cnc.get('detail')})")
            
    if runtimes_updates:
        print("\nRuntimes:")
        for update in runtimes_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if tools_updates:
        print("\nTools:")
        for update in tools_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if ai_clis_updates:
        print("\nAI CLIs:")
        for update in ai_clis_updates:
            print(f"  {update.get('tool')}: {update.get('current_version')} -> {update.get('latest_version')}")
            
    if repairs_needed:
        print("\nRepairs (missing components planned for reinstall):")
        for r in repairs_needed:
            print(f"  - {r}")

    if not_checked:
        print("\nNot checked:")
        for nc in not_checked:
            print(f"  - {nc.get('component')} ({nc.get('reason')})")

    if args.check:
        if could_not_check:
            sys.exit(1)
        sys.exit(0)

    if not has_actionable:
        print("\nEverything Engram can check is up to date.")
        return {"status": "success", "detail": "No updates discovered"}

    total_changes = len(runtimes_updates) + len(tools_updates) + len(ai_clis_updates) + len(repairs_needed)

    if args.dry_run:
        print(f"\nDry run complete. Proposal written to {artifact_dir}")
        return {"status": "success", "detail": "Dry run complete"}

    if not args.yes:
        try:
            choice = input(f"\nApply {total_changes} changes? [y/N] ")
        except EOFError:
            choice = "n"
        if choice.strip().lower() != "y":
            print(f"\nUpdate declined.")
            sys.exit(3)

    print("\nApplying declarations...")
    exit_code, apply_result = check_tool_updates.apply_proposal(
        artifact_dir, yes=True
    )

    if exit_code in (1, 2):
        return {"status": "failed", "detail": "Apply failed or proposal invalid/stale", "apply_result": apply_result}
    elif exit_code != 0:
        return {"status": "failed", "detail": f"Unknown exit code {exit_code}", "apply_result": apply_result}

    print("\nReconciling via provisioner (in-process)...")
    try:
        deploy_result = provisioner.deploy(ctx)
        if deploy_result.get("status") == "error":
            print(f"Provisioner deploy error: {deploy_result.get('detail')}")
            return {"status": "incomplete", "detail": "applied but deploy failed"}
    except Exception as e:
        print(f"Provisioner deploy exception: {e}")
        return {"status": "incomplete", "detail": "applied but deploy threw exception"}

    failed = deploy_result.get("failed", [])
    deferred = deploy_result.get("deferred", [])
    reverted_components = []
    
    if failed or deferred:
        # We need to revert the specific components in runtimes.json and tool-catalog.v1.json
        print(f"\nReverting {len(failed) + len(deferred)} failed/deferred components...")
        
        backup_path = apply_result.get("backup_path")
        catalog_backup_path = apply_result.get("catalog_backup_path")
        
        if backup_path and Path(backup_path).exists():
            try:
                old_runtimes = json.loads(Path(backup_path).read_text(encoding="utf-8"))
                live_runtimes_path = _SYS_DIR / "runtimes.json"
                live_runtimes = json.loads(live_runtimes_path.read_text(encoding="utf-8"))
                
                changed = False
                for comp in failed + deferred:
                    for section in ["runtimes", "tools"]:
                        if section in live_runtimes and section in old_runtimes and comp in live_runtimes[section]:
                            if comp in old_runtimes[section]:
                                live_runtimes[section][comp] = old_runtimes[section][comp]
                            else:
                                del live_runtimes[section][comp]
                            changed = True
                            reverted_components.append(comp)
                            
                if changed:
                    check_tool_updates._atomic_write_json(live_runtimes_path, live_runtimes)
            except Exception as e:
                print(f"Failed to revert runtimes.json: {e}")

        if catalog_backup_path and Path(catalog_backup_path).exists():
            try:
                old_catalog = json.loads(Path(catalog_backup_path).read_text(encoding="utf-8"))
                live_catalog_path = _SYS_DIR / "tool-catalog.v1.json"
                live_catalog = json.loads(live_catalog_path.read_text(encoding="utf-8"))
                
                changed = False
                for comp in failed + deferred:
                    if "tools" in live_catalog and "tools" in old_catalog:
                        # Find index in live
                        for i, tool in enumerate(live_catalog["tools"]):
                            if tool.get("tool_id") == comp:
                                # Find in old
                                old_tool = next((t for t in old_catalog["tools"] if t.get("tool_id") == comp), None)
                                if old_tool:
                                    live_catalog["tools"][i] = old_tool
                                else:
                                    del live_catalog["tools"][i]
                                changed = True
                                reverted_components.append(comp)
                                break
                                
                if changed:
                    check_tool_updates._atomic_write_json(live_catalog_path, live_catalog)
            except Exception as e:
                print(f"Failed to revert tool-catalog.v1.json: {e}")

    receipt = {
        "artifact_dir": artifact_dir,
        "planned_changes": apply_result.get("planned_changes", []),
        "applied": deploy_result.get("installed", []),
        "reverted": reverted_components,
        "deferred": deferred,
        "errors": failed,
    }
    receipt_dir = _SYS_DIR / "data" / "state" / "update" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    if artifact_dir:
        stamp = Path(artifact_dir).name
        receipt_path = receipt_dir / f"{stamp}.json"
        check_tool_updates._write_json(receipt_path, receipt)
        print(f"\nUpdate receipt written to {receipt_path}")

    # Core update handoff would go here (Section 8.4)

    if failed:
        sys.exit(1)
        
    return {"status": "success", "apply_result": apply_result}
