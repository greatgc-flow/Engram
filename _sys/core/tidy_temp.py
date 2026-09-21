"""
tidy_temp.py - periodic sweep of accumulated debris across the portable dev
environment (stale IPC query files, pytest/probe temp directories, old
antigravity task logs, old VSCode session logs, and — as of 2026-08-09 —
regenerable package-manager/editor caches: npm, pip, WinGet, pytest's own
tmp_path rotation, and VSCode's renderer/extension caches).

Safe by default: prints a plan and does nothing unless --apply is passed.
Deletion targets are allowlisted by name pattern (not blanket age-based),
based on a 2026-08-06 joint cc/cx audit of P:\\_sys\\data\\temp, extended
2026-08-09 (cc + ag joint audit) to cover the pure package/editor caches
below — each verified to be fully regenerable (next `npm`/`pip`/`winget`
install just re-downloads; VSCode rebuilds its renderer caches on next
launch) and independently re-measured before being added here.

Usage:
    python _sys/core/tidy_temp.py                # dry-run, all targets
    python _sys/core/tidy_temp.py --apply         # actually delete
    python _sys/core/tidy_temp.py --only tmp,data_temp  # limit to specific targets
"""
import argparse
import datetime
import fnmatch
import subprocess
import sys
from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parents[1]
ROOT = _SYS_DIR.parent

sys.path.insert(0, str(_SYS_DIR / "core"))
from root import bootstrap_root_package  # noqa: E402
bootstrap_root_package(_SYS_DIR)

# ── root tmp/: leftover test-probe files ────────────────────────────────
ROOT_TMP_MIN_AGE_DAYS = 7

# ── _sys/data/temp: pytest/probe fixture debris ─────────────────────────
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
# NOTE: "pytest-of-GREAT" and "WinGet" were removed from this set 2026-08-09
# after being manually investigated, confirmed to be pure regenerable caches
# (pytest's own tmp_path rotation; winget's download/install cache), and
# given their own dedicated, safety-scoped plan_* functions below instead of
# a blanket never-touch. See plan_pytest_of_great() and plan_winget_cache().
DATA_TEMP_NEVER_TOUCH = {
    "claude", "python-languageserver-cancellation",
    "node-compile-cache", "sandbox-probe", "ask_ask-ce76",
}
DATA_TEMP_NEVER_TOUCH_PATTERNS = ["pyright-*", "vscode-stable-*", "ag_*"]

# ── pytest's own tmp_path rotation dir (accumulates pytest-NNNN subdirs
# across every test run system-wide, not just peerhub's) ────────────────────
PYTEST_OF_GREAT_MIN_AGE_DAYS = 5

# ── VSCode renderer/extension-download caches (regenerate on next launch;
# workspaceStorage is deliberately excluded -- it's per-workspace recent-
# file/extension state, not a pure cache, and was small enough (~1.6MB
# measured 2026-08-09) not to be worth the extra risk) ───────────────────
VSCODE_CACHE_SUBDIRS = ["CachedData", "CachedExtensionVSIXs", "Cache", "GPUCache"]

# Loose 8-char temp files verified (cx audit) to contain exactly "blat"
# (4 bytes) - pytest tempfile-probe artifacts.
BLAT_NAME_LEN = 8

# ── ag (antigravity) internal task logs ─────────────────────────────────
BRAIN_LOG_MAX_AGE_DAYS = 14

# ── VSCode dated session log dirs ───────────────────────────────────────
VSCODE_LOGS_KEEP = 2

_SYS_DIR_EXPLICIT = False


def configure_paths(
    root: Path | None = None,
    sys_dir: Path | None = None,
    explicit_sys_dir: bool | None = None,
) -> dict[str, Path]:
    """Configure and return all derived path constants for the given root and sys_dir.

    Updates module-level path constants (ROOT, _SYS_DIR, DATA_TEMP_DIR, etc.)
    and returns a dictionary of the derived paths for testing or programmatic inspection.
    """
    global ROOT, _SYS_DIR, _SYS_DIR_EXPLICIT
    global ROOT_TMP_DIR, DATA_TEMP_DIR, PYTEST_OF_GREAT_DIR, WINGET_CACHE_DIR
    global NPM_CACHE_DIR, PIP_CACHE_DIR, VSCODE_USER_DATA_DIR, VSCODE_LOGS_DIR, BRAIN_DIR

    if root is not None:
        ROOT = Path(root).resolve()
    if sys_dir is not None:
        _SYS_DIR = Path(sys_dir).resolve()
        _SYS_DIR_EXPLICIT = True if explicit_sys_dir is None else explicit_sys_dir
    elif root is not None:
        _SYS_DIR = ROOT / _SYS_DIR.name
        _SYS_DIR_EXPLICIT = False if explicit_sys_dir is None else explicit_sys_dir
    elif explicit_sys_dir is not None:
        _SYS_DIR_EXPLICIT = explicit_sys_dir

    ROOT_TMP_DIR = ROOT / "tmp"
    DATA_TEMP_DIR = _SYS_DIR / "data" / "temp"
    PYTEST_OF_GREAT_DIR = DATA_TEMP_DIR / "pytest-of-GREAT"
    WINGET_CACHE_DIR = DATA_TEMP_DIR / "WinGet"
    NPM_CACHE_DIR = _SYS_DIR / "env" / "nodejs" / "npm-cache"
    PIP_CACHE_DIR = _SYS_DIR / "env" / "python" / "pip-cache"
    VSCODE_USER_DATA_DIR = _SYS_DIR / "env" / "vscode" / "data" / "user-data"
    VSCODE_LOGS_DIR = _SYS_DIR / "env" / "vscode" / "data" / "user-data" / "logs"
    BRAIN_DIR = _SYS_DIR / "antigravity" / "config" / "brain"

    return {
        "root": ROOT,
        "sys_dir": _SYS_DIR,
        "root_tmp": ROOT_TMP_DIR,
        "data_temp": DATA_TEMP_DIR,
        "pytest_of_great": PYTEST_OF_GREAT_DIR,
        "winget_cache": WINGET_CACHE_DIR,
        "npm_cache": NPM_CACHE_DIR,
        "pip_cache": PIP_CACHE_DIR,
        "vscode_user_data": VSCODE_USER_DATA_DIR,
        "vscode_logs": VSCODE_LOGS_DIR,
        "brain": BRAIN_DIR,
    }


# Initialize path constants with defaults derived from _SYS_DIR
configure_paths(ROOT, _SYS_DIR, explicit_sys_dir=False)


def _age_days(p: Path, now: float) -> float:
    return (now - p.stat().st_mtime) / 86400


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


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


def plan_pytest_of_great(now: float) -> list[Path]:
    """pytest's own tmp_path rotation dirs, age-filtered (not a blanket
    clear) -- a currently-running test suite's own pytest-NNNN dir is
    always younger than PYTEST_OF_GREAT_MIN_AGE_DAYS and so is never a
    candidate, regardless of when this sweep runs."""
    if not PYTEST_OF_GREAT_DIR.exists():
        return []
    return [
        d for d in PYTEST_OF_GREAT_DIR.iterdir()
        if d.is_dir() and _age_days(d, now) >= PYTEST_OF_GREAT_MIN_AGE_DAYS
    ]


def plan_winget_cache() -> list[Path]:
    """WinGet's own download/install cache -- safe to clear in full any
    time no winget install is actively in progress; not age-filtered
    since every entry is disposable regardless of age."""
    if not WINGET_CACHE_DIR.exists():
        return []
    return list(WINGET_CACHE_DIR.iterdir())


def plan_npm_cache() -> list[Path]:
    """npm's own download cache (_cacache) -- `npm install` re-downloads
    on demand; clearing does not affect any already-installed package."""
    if not NPM_CACHE_DIR.exists():
        return []
    return list(NPM_CACHE_DIR.iterdir())


def plan_pip_cache() -> list[Path]:
    """pip's own wheel/sdist download cache -- `pip install` re-downloads
    on demand; clearing does not affect any already-installed package."""
    if not PIP_CACHE_DIR.exists():
        return []
    return list(PIP_CACHE_DIR.iterdir())



def plan_pycache() -> list[Path]:
    return [p for p in _SYS_DIR.rglob("__pycache__") if p.is_dir()]

def plan_pytest_cache_default() -> list[Path]:
    p = _SYS_DIR / "tests" / ".pytest_cache"
    return [p] if p.exists() else []

def plan_launcher_logs(deep: bool) -> list[Path]:
    if not deep:
        return []
    log_dir = _SYS_DIR / "data" / "logs"
    if not log_dir.exists():
        return []
    logs = sorted(
        [f for f in log_dir.rglob("*.log") if f.is_file()],
        key=lambda f: f.stat().st_mtime
    )
    # keep the 5 most recent
    return logs[:-5] if len(logs) > 5 else []

def _vscode_is_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Code.exe"],
            capture_output=True, timeout=10,
        )
        # tasklist's output encoding depends on the system's active code
        # page (observed non-UTF-8 bytes on a Korean-locale Windows host,
        # 2026-08-09) -- decode leniently, we only need an ASCII substring.
        stdout = result.stdout.decode("utf-8", errors="replace")
        return "Code.exe" in stdout
    except (OSError, subprocess.SubprocessError):
        # If we can't check, be conservative and assume it might be running.
        return True


def plan_vscode_caches() -> list[Path]:
    """VSCode's renderer/extension-download caches -- rebuilt automatically
    on next launch. Skipped entirely (returns []) if a Code.exe process is
    currently detected, since clearing a live editor's active cache files
    risks instability in the running session -- confirmed as a real,
    observed risk during the 2026-08-09 manual cleanup, not theoretical."""
    if not VSCODE_USER_DATA_DIR.exists():
        return []
    if _vscode_is_running():
        return []
    return [
        VSCODE_USER_DATA_DIR / name
        for name in VSCODE_CACHE_SUBDIRS
        if (VSCODE_USER_DATA_DIR / name).exists()
    ]



def _rm(path: Path, apply: bool) -> int:
    """Returns bytes freed (best-effort, 0 for dry-run)."""
    # Defense in depth: NEVER delete from these protected paths
    protected = [
        ROOT / "workspace",
        ROOT / ".engram",
        ROOT / "_archive",  # legacy-source: migration only
        _SYS_DIR / "env" / "python",
        _SYS_DIR / "tools" / "rg",
        _SYS_DIR / "data" / "state",
        _SYS_DIR / "runtimes.json",
        _SYS_DIR / "tool-catalog.v1.json",
    ]
    
    # Also protect root files like .vscode, _state, WORKLOG.md, and all *.md
    if path.parent == ROOT and (path.name in [".vscode", "_state", "WORKLOG.md"] or path.name.endswith(".md")):
        raise AssertionError(f"Defense in depth: tidy attempted to delete protected root file {path}")
        
    for prot in protected:
        if path == prot or prot in path.parents:
            raise AssertionError(f"Defense in depth: tidy attempted to delete protected path {path}")

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


def build_plan(now: float | None = None, deep: bool = False) -> list[tuple[str, str, list[Path]]]:
    """Return categorized cleanup items: list of (label, key, items)."""
    if not _SYS_DIR_EXPLICIT and ROOT != _SYS_DIR.parent and _SYS_DIR.name:
        configure_paths(root=ROOT, sys_dir=ROOT / _SYS_DIR.name)
    if now is None:
        now = datetime.datetime.now().timestamp()
    dirs, blat = plan_data_temp(now)
    return [
        ("root_tmp", "tmp", plan_root_tmp(now)),
        ("data_temp_dirs", "data_temp", dirs),
        ("data_temp_blat_files", "data_temp", blat),
        ("ag_brain_logs", "brain", plan_brain_logs(now)),
        ("vscode_logs", "vscode", plan_vscode_logs()),
        ("pytest_of_great", "pytest_cache", plan_pytest_of_great(now)),
        ("winget_cache", "winget_cache", plan_winget_cache()),
        ("npm_cache", "npm_cache", plan_npm_cache()),
        ("pip_cache", "pip_cache", plan_pip_cache()),
        ("pycache", "pycache", plan_pycache()),
        ("pytest_cache_default", "pytest_cache_default", plan_pytest_cache_default()),
        ("launcher_logs", "launcher_logs", plan_launcher_logs(deep)),
        ("vscode_cache", "vscode_cache", plan_vscode_caches()),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=None, help="Root directory (default: ROOT)")
    ap.add_argument("--sys-dir", default=None, help="Sys directory (default: _SYS_DIR)")
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--deep", action="store_true", help="include deeper cleans (e.g., launcher logs)")
    ap.add_argument(
        "--only", default=None,
        help=(
            "comma-separated subset: tmp,data_temp,brain,vscode,"
            "pytest_cache,winget_cache,npm_cache,pip_cache,vscode_cache,pycache,pytest_cache_default,launcher_logs"
        ),
    )
    args = ap.parse_args()

    if args.base_dir or args.sys_dir:
        configure_paths(root=args.base_dir, sys_dir=args.sys_dir)

    default_targets = (
        "tmp,data_temp,brain,vscode,"
        "pytest_cache,winget_cache,npm_cache,pip_cache,vscode_cache,pycache,pytest_cache_default,launcher_logs"
    )
    targets = set((args.only or default_targets).split(","))
    now = datetime.datetime.now().timestamp()
    total_bytes = 0
    total_count = 0

    def run_item(label: str, key: str, items: list[Path]):
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

    plan = build_plan(now=now, deep=args.deep)
    if "vscode_cache" in targets and VSCODE_USER_DATA_DIR.exists() and _vscode_is_running():
        print("[vscode_cache] skipped: VSCode (Code.exe) is currently running")
    for label, key, items in plan:
        run_item(label, key, items)

    print(f"\nTOTAL: {total_count} item(s), {total_bytes / 1048576:.1f} MiB "
          f"({'applied' if args.apply else 'dry-run, pass --apply to execute'})")
    return 0


def run(ctx: dict) -> dict:
    """Entry point for dispatch.bat (engram tidy pipeline)."""
    if "base_dir" in ctx or "sys_dir" in ctx:
        configure_paths(root=ctx.get("base_dir"), sys_dir=ctx.get("sys_dir"))
    # Convert ctx["args"] to sys.argv for argparse inside main()
    # (or we could just call main() and let it read sys.argv, but ctx["args"] 
    # is the canonical way dispatch args are passed).
    old_argv = sys.argv
    try:
        sys.argv = ["tidy_temp.py"] + (ctx.get("args") or [])
        rc = main()
        return {"status": "success" if rc == 0 else "failed", "operation": "tidy.run"}
    except SystemExit as e:
        return {"status": "success" if e.code == 0 else "failed", "operation": "tidy.run"}
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    sys.exit(main())
