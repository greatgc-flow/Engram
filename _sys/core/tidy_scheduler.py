"""
tidy_scheduler.py - Windows Task Scheduler management for PortableDev-TidyTemp.

Configures a weekly background cleanup task running tidy_temp.py --apply against
the resolved physical root (bypassing any SUBST drive letter mapping).

Usage:
    python _sys/core/tidy_scheduler.py query
    python _sys/core/tidy_scheduler.py create          # dry-run
    python _sys/core/tidy_scheduler.py create --apply  # register task
    python _sys/core/tidy_scheduler.py delete          # dry-run
    python _sys/core/tidy_scheduler.py delete --apply  # remove task
"""
import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "PortableDev-TidyTemp"


def get_physical_paths() -> tuple[Path, Path, Path]:
    """Resolves physical root bypassing SUBST drive letter."""
    physical_root = Path(__file__).resolve().parents[2]
    python_exe = physical_root / "_sys" / "env" / "python" / "python.exe"
    tidy_temp_script = physical_root / "_sys" / "core" / "tidy_temp.py"
    return physical_root, python_exe, tidy_temp_script


def create_task(apply: bool = False) -> int:
    """Create or overwrite the PortableDev-TidyTemp scheduled task."""
    _, python_exe, tidy_temp_script = get_physical_paths()
    tr_cmd = f'"{python_exe}" "{tidy_temp_script}" --apply'
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", tr_cmd,
        "/SC", "WEEKLY",
        "/RL", "LIMITED",
        "/F",
    ]
    cmd_str = f'schtasks /Create /TN "{TASK_NAME}" /TR \'{tr_cmd}\' /SC WEEKLY /RL LIMITED /F'

    if not apply:
        print(f"[dry-run] Would register task '{TASK_NAME}' with action:")
        print(f"    {tr_cmd}")
        print(f"[dry-run] Command: {cmd_str}")
        print("Pass --apply to execute.")
        return 0

    print(f"Registering task '{TASK_NAME}'...")
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode == 0:
        print(f"Successfully registered task '{TASK_NAME}'.")
        if res.stdout:
            print(res.stdout.strip())
        return 0
    else:
        print(f"Error registering task '{TASK_NAME}' (exit code {res.returncode}):")
        print(res.stderr.strip() or res.stdout.strip())
        return res.returncode


def query_task() -> int:
    """Query the PortableDev-TidyTemp scheduled task."""
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode == 0:
        print(f"Task '{TASK_NAME}' status:\n")
        print(res.stdout.strip())
        return 0
    else:
        print(f"Task '{TASK_NAME}' not found or error (exit code {res.returncode}).")
        if res.stderr:
            print(res.stderr.strip())
        return res.returncode


def delete_task(apply: bool = False) -> int:
    """Delete the PortableDev-TidyTemp scheduled task."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    cmd_str = f'schtasks /Delete /TN "{TASK_NAME}" /F'

    if not apply:
        print(f"[dry-run] Would delete task '{TASK_NAME}'.")
        print(f"[dry-run] Command: {cmd_str}")
        print("Pass --apply to execute.")
        return 0

    print(f"Deleting task '{TASK_NAME}'...")
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode == 0:
        print(f"Successfully deleted task '{TASK_NAME}'.")
        if res.stdout:
            print(res.stdout.strip())
        return 0
    else:
        print(f"Error deleting task '{TASK_NAME}' (exit code {res.returncode}):")
        print(res.stderr.strip() or res.stdout.strip())
        return res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage PortableDev-TidyTemp Windows Scheduled Task."
    )
    parser.add_argument(
        "action",
        choices=["create", "query", "delete"],
        help="Action to perform: create, query, or delete task",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute creation/deletion (default: dry-run)",
    )
    args = parser.parse_args()

    if args.action == "create":
        return create_task(apply=args.apply)
    elif args.action == "query":
        return query_task()
    elif args.action == "delete":
        return delete_task(apply=args.apply)
    return 1


if __name__ == "__main__":
    sys.exit(main())
