"""
updater.py - First-class update dispatch pipeline.
"""
import argparse
from typing import Any

from checks import check_tool_updates

def _parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Updater runner")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--install", action="store_true", help="Run INSTALL.bat after successful apply")
    parser.add_argument("--dry-run", action="store_true", help="Discover and show proposal, apply nothing")
    return parser.parse_args(args)

def run(ctx: dict[str, Any]) -> dict[str, Any]:
    args_list = ctx.get("args", [])
    try:
        args = _parse_args(args_list)
    except SystemExit as e:
        return {"status": "failed", "detail": f"Argument parsing failed with code {e.code}"}

    print(">>> Discovering updates...")
    try:
        payload = check_tool_updates.run(propose_diff=True)
    except Exception as e:
        return {"status": "failed", "detail": f"Update discovery failed: {e}"}

    if payload.get("errors"):
        return {"status": "failed", "detail": "Update discovery encountered errors", "errors": payload["errors"]}

    artifact_dir = payload.get("artifact_dir")
    updates = payload.get("updates_discovered", [])
    not_checked = payload.get("not_checked", [])

    def print_not_checked():
        if not_checked:
            print("\nNot checked (no discovery_provider or manual):")
            for nc in not_checked:
                print(f"  - {nc.get('component')} ({nc.get('reason')})")

    if not updates:
        print("up to date")
        print_not_checked()
        return {"status": "success", "detail": "No updates discovered"}

    print("\nPlanned changes:")
    for update in updates:
        tool = update.get("tool", "?")
        current = update.get("current_version", "?")
        latest = update.get("latest_version", "?")
        print(f"  {tool}: {current} -> {latest}")

    print_not_checked()

    if args.dry_run:
        print(f"\nDry run complete. Proposal written to {artifact_dir}")
        return {"status": "success", "detail": "Dry run complete"}

    if not args.yes:
        try:
            choice = input("\nApply these updates? [y/N] ")
        except EOFError:
            choice = "n"
        if choice.strip().lower() != "y":
            install_flag = " --install" if args.install else ""
            resume_cmd = f"python check_tool_updates.py --apply {artifact_dir} --yes{install_flag}"
            print(f"\nUpdate declined. To apply later, run:\n  {resume_cmd}")
            return {"status": "success", "detail": "Update declined by user"}

    exit_code, result = check_tool_updates.apply_proposal(
        artifact_dir, yes=True, install=args.install
    )

    if exit_code == 0:
        return {"status": "success", "apply_result": result}
    elif exit_code in (1, 2):
        return {"status": "failed", "detail": "Apply failed or proposal invalid/stale", "apply_result": result}
    elif exit_code == 4:
        backup = result.get("backup_path")
        print(f"\n[!] INCOMPLETE UPDATE: Declarations in runtimes.json were updated, but INSTALL failed.")
        print(f"    Reconciliation is incomplete. Backup of prior declarations: {backup}")
        return {
            "status": "incomplete",
            "detail": "applied but INSTALL failed",
            "backup": backup
        }
    else:
        return {"status": "failed", "detail": f"Unknown exit code {exit_code}", "apply_result": result}
