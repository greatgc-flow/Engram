"""
tidy_temp.py - periodic sweep of accumulated debris across the portable dev
environment (stale IPC query files, pytest/probe temp directories, old
antigravity task logs, old VSCode session logs).

Safe by default: prints a plan and does nothing unless --apply is passed.
Deletion targets are allowlisted by name pattern (not blanket age-based),
based on a 2026-08-06 joint cc/cx audit of P:\\_sys\\data\\temp.

Usage:
    python _sys/core/tidy_temp.py                # dry-run, all targets
    python _sys/core/tidy_temp.py --apply         # actually delete
    python _sys/core/tidy_temp.py --only ipc,tmp  # limit to specific targets
"""
import argparse
import datetime
import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── _sys/ai/ipc: stale single-use IPC query files ──────────────────────
IPC_DIR = ROOT / "_sys" / "ai" / "ipc"
IPC_MIN_AGE_DAYS = 2

# ── root tmp/: leftover test-probe files ────────────────────────────────
ROOT_TMP_DIR = ROOT / "tmp"
ROOT_TMP_MIN_AGE_DAYS = 7

# ── _sys/data/temp: pytest/probe fixture debris ─────────────────────────
DATA_TEMP_DIR = ROOT / "_sys" / "data" / "temp"
DATA_TEMP_MIN_AGE_DAYS = 5

# Allowlist of directory-name patterns confirmed as disposable test/probe
# debris (joint cc + cx.deepthink audit, 2026-08-06). Only names matching
# one of these AND older than DATA_TEMP_MIN_AGE_DAYS are candidates.
DATA_TEMP_DIR_PATTERNS = [
    "__pycache__",
    "ask_ask-17a2", "ask_ask-e119",
    "pytest_c1*", "pytest_broker1", "pytest_check_pre", "pytest_thd",
    "pytest-cx-review-*", "pytest-d2d4-*", "pytest-d3d6*",
    "c7_pytest_*", "c11-*",
    "cx_audit_pytest_*", "cx_hub_invoke_pytest_*", "cx-width-pytest",
    "cx_manual_acl_probe_*", "cx_p_acl_probe_*",
    "cx_probe_test", "cx_session_test", "cx_terminal_freshness_verify_*",
    "cx-full-review-*", "cx-mode777-probe-*", "cx-s3-review-*",
    "engram_c1_review_*", "c1_guard_verify_*", "c10-probe-*",
    "c8a-crossverify-*", "d3d6-validator-manual*",
    "codex-model-binding-empty-home", "sandbox-probe-outside-*",
    "system-commandline-sentinel-files",
    "t21-pytest-base", "t21_hold", "t41-manual",
    "t55_acl_parent", "t7_adapter_usage_direct", "test_d1",
]

# Defense-in-depth: never delete these regardless of pattern/age match.
DATA_TEMP_NEVER_TOUCH = {
    "claude", "pytest-of-GREAT", "python-languageserver-cancellation",
    "node-compile-cache", "WinGet", "sandbox-probe", "ask_ask-ce76",
}
DATA_TEMP_NEVER_TOUCH_PATTERNS = ["pyright-*", "vscode-stable-*", "ag_*"]

# Loose 8-char temp files verified (cx audit) to contain exactly "blat"
# (4 bytes) - pytest tempfile-probe artifacts.
BLAT_NAME_LEN = 8

# ── ag (antigravity) internal task logs ─────────────────────────────────
BRAIN_DIR = ROOT / "_sys" / "antigravity" / "config" / "brain"
BRAIN_LOG_MAX_AGE_DAYS = 14

# ── VSCode dated session log dirs ───────────────────────────────────────
VSCODE_LOGS_DIR = ROOT / "_sys" / "env" / "vscode" / "data" / "user-data" / "logs"
VSCODE_LOGS_KEEP = 2


def _age_days(p: Path, now: float) -> float:
    return (now - p.stat().st_mtime) / 86400


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def plan_ipc(now: float) -> list[Path]:
    if not IPC_DIR.exists():
        return []
    return [
        f for f in IPC_DIR.glob("*.txt")
        if f.is_file() and _age_days(f, now) >= IPC_MIN_AGE_DAYS
    ]


def plan_root_tmp(now: float) -> list[Path]:
    if not ROOT_TMP_DIR.exists():
        return []
    return [
        f for f in ROOT_TMP_DIR.iterdir()
        if f.is_file() and _age_days(f, now) >= ROOT_TMP_MIN_AGE_DAYS
    ]


def plan_data_temp(now: float) -> tuple[list[Path], list[Path]]:
    if not DATA_TEMP_DIR.exists():
        return [], []
    dirs, blat_files = [], []
    for entry in DATA_TEMP_DIR.iterdir():
        if entry.name in DATA_TEMP_NEVER_TOUCH:
            continue
        if _matches_any(entry.name, DATA_TEMP_NEVER_TOUCH_PATTERNS):
            continue
        if _age_days(entry, now) < DATA_TEMP_MIN_AGE_DAYS:
            continue
        if entry.is_dir() and _matches_any(entry.name, DATA_TEMP_DIR_PATTERNS):
            dirs.append(entry)
        elif (
            entry.is_file()
            and len(entry.name) == BLAT_NAME_LEN
            and entry.name.replace("_", "").isalnum()
            and entry.stat().st_size == 4
        ):
            try:
                if entry.read_bytes() == b"blat":
                    blat_files.append(entry)
            except OSError:
                pass
    return dirs, blat_files


def plan_brain_logs(now: float) -> list[Path]:
    if not BRAIN_DIR.exists():
        return []
    return [
        f for f in BRAIN_DIR.glob("*/.system_generated/tasks/task-*.log")
        if f.is_file() and _age_days(f, now) >= BRAIN_LOG_MAX_AGE_DAYS
    ]


def plan_vscode_logs() -> list[Path]:
    if not VSCODE_LOGS_DIR.exists():
        return []
    dated = sorted(
        [d for d in VSCODE_LOGS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    return dated[:-VSCODE_LOGS_KEEP] if len(dated) > VSCODE_LOGS_KEEP else []


def _rm(path: Path, apply: bool) -> int:
    """Returns bytes freed (best-effort, 0 for dry-run)."""
    if path.is_dir():
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    else:
        size = path.stat().st_size
    if apply:
        import os
        import shutil
        import stat

        def _on_rm_error(func, p, exc_info):
            # Windows: git loose objects etc. are created read-only;
            # clear the bit and retry once instead of silently giving up.
            os.chmod(p, stat.S_IWRITE)
            func(p)

        if path.is_dir():
            shutil.rmtree(path, onerror=_on_rm_error)
        else:
            path.chmod(stat.S_IWRITE)
            path.unlink(missing_ok=True)
    return size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--only", default=None, help="comma-separated subset: ipc,tmp,data_temp,brain,vscode")
    args = ap.parse_args()

    targets = set((args.only or "ipc,tmp,data_temp,brain,vscode").split(","))
    now = datetime.datetime.now().timestamp()
    total_bytes = 0
    total_count = 0

    def run(label: str, key: str, items: list[Path]):
        nonlocal total_bytes, total_count
        if key not in targets:
            return
        freed = sum(_rm(p, args.apply) for p in items)
        total_bytes += freed
        total_count += len(items)
        verb = "deleted" if args.apply else "would delete"
        print(f"[{label}] {verb} {len(items)} item(s), {freed / 1048576:.1f} MiB")
        if not args.apply:
            for p in items[:10]:
                print(f"    {p}")
            if len(items) > 10:
                print(f"    ... and {len(items) - 10} more")

    run("ipc", "ipc", plan_ipc(now))
    run("root_tmp", "tmp", plan_root_tmp(now))
    dirs, blat = plan_data_temp(now)
    run("data_temp_dirs", "data_temp", dirs)
    run("data_temp_blat_files", "data_temp", blat)
    run("ag_brain_logs", "brain", plan_brain_logs(now))
    run("vscode_logs", "vscode", plan_vscode_logs())

    print(f"\nTOTAL: {total_count} item(s), {total_bytes / 1048576:.1f} MiB "
          f"({'applied' if args.apply else 'dry-run, pass --apply to execute'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
