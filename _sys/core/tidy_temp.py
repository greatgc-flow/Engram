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

from core import backups, env_lock, env_manifest  # noqa: E402

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

# ── Python swap runner copies ───────────────────────────────────────────
ENV_OP_RUNNERS_MIN_AGE_DAYS = 3


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
    env_dir = _SYS_DIR / "env"
    tools_dir = _SYS_DIR / "tools"
    return [
        p for p in _SYS_DIR.rglob("__pycache__")
        if p.is_dir()
        and env_dir not in p.parents
        and tools_dir not in p.parents
        and p != env_dir
        and p != tools_dir
    ]

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


def plan_env_op_runners(now: float) -> list[Path]:
    """Python swap runner copies live in <sys>/data/temp/env-op/<op_id>/runner.
    Returns the <op_id> directories under data/temp/env-op that are older than 3 days
    AND only when core.env_ops.journal_blocks(sys_dir) is None; never when a journal
    is active; never touches data/state."""
    if not DATA_TEMP_DIR.exists():
        return []
    env_op_dir = DATA_TEMP_DIR / "env-op"
    if not env_op_dir.exists():
        return []
    try:
        from core import env_ops
        if env_ops.journal_blocks(_SYS_DIR) is not None:
            return []
    except Exception:
        pass
    
    candidates = []
    for op_dir in env_op_dir.iterdir():
        if op_dir.is_dir() and _age_days(op_dir, now) >= ENV_OP_RUNNERS_MIN_AGE_DAYS:
            candidates.append(op_dir)
    return candidates


# ── environment backup registry (docs/design/engram-env-resilience-design-2026-10-02.md, 8.3) ──
# Only marker-bearing dirs under data/backups/env are ever candidates; name patterns never are.

def _utc_iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _active_op_ids() -> set[str]:
    """Operations that may still own a pending backup: manifest last_op + a live lock owner."""
    active: set[str] = set()
    manifest = env_manifest.read_manifest(_SYS_DIR)
    if manifest.status == "ok":
        last = (manifest.data or {}).get("last_op") or {}
        if last.get("id"):
            active.add(str(last["id"]))
    info = env_lock.inspect(_SYS_DIR)
    if info.get("state") == "held" and info.get("owner", {}).get("op_id"):
        active.add(str(info["owner"]["op_id"]))
    return active


def _active_journal() -> dict | None:
    """A non-terminal env-op journal (its recovery backups must survive); None when none/unreadable-as-none."""
    from core import env_ops
    try:
        return env_ops.active_journal(_SYS_DIR)
    except Exception:
        # Fail closed: an unreadable journal must be treated as active.
        return {"op_id": None, "phase": "UNREADABLE", "paths": {}, "unreadable": True}


def _journal_protected_paths() -> tuple[Path, ...]:
    j = _active_journal()
    if not j:
        return ()
    return tuple(Path(v) for v in (j.get("paths") or {}).values() if isinstance(v, str))


def plan_backups_retention(
    now: float, keep_override: int | None = None, size_cap_bytes: int | None = None,
    protect: tuple[Path, ...] = (),
) -> backups.RetentionPlan:
    protect = tuple(protect) + _journal_protected_paths()
    scan = backups.scan(_SYS_DIR)
    if size_cap_bytes is None:
        try:
            import shutil
            free = shutil.disk_usage(_SYS_DIR).free
        except OSError:
            free = None
        size_cap_bytes = backups.default_size_cap(free_bytes=free)
    return backups.plan_retention(
        scan.valid, now=_utc_iso(now), active_op_ids=_active_op_ids(),
        size_cap_bytes=size_cap_bytes, keep_override=keep_override,
        root=backups.backups_root(_SYS_DIR), protect=protect,
    )


def plan_backups(
    now: float, keep_override: int | None = None, size_cap_bytes: int | None = None,
    protect: tuple[Path, ...] = (),
) -> list[Path]:
    if _active_journal() is not None:
        return []
    return [ref.path for ref, _ in plan_backups_retention(now, keep_override, size_cap_bytes, protect).delete]


def _rm(path: Path, apply: bool) -> int:
    """Returns bytes freed (best-effort, 0 for dry-run)."""
    path = Path(path)
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
        # Deliberate carve-out: pip-cache lives under _sys/env/python but has its
        # own narrower cleanup feature; keep all other contents of python protected.
        if prot == _SYS_DIR / "env" / "python":
            if path == PIP_CACHE_DIR or PIP_CACHE_DIR in path.parents:
                continue
            try:
                p_res = path.resolve()
                pip_res = PIP_CACHE_DIR.resolve()
                if p_res == pip_res or pip_res in p_res.parents:
                    continue
            except (OSError, ValueError):
                pass
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


def build_plan(
    now: float | None = None,
    deep: bool = False,
    *,
    keep_override: int | None = None,
    size_cap_bytes: int | None = None,
    protect: tuple[Path, ...] = (),
) -> list[tuple[str, str, list[Path]]]:
    """Return categorized cleanup items: list of (label, key, items)."""
    if not _SYS_DIR_EXPLICIT and ROOT != _SYS_DIR.parent and _SYS_DIR.name:
        configure_paths(root=ROOT, sys_dir=ROOT / _SYS_DIR.name)
    if now is None:
        now = datetime.datetime.now().timestamp()
    dirs, blat = plan_data_temp(now)
    plan = [
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
        ("backups", "backups", plan_backups(now, keep_override, size_cap_bytes, protect)),
        ("env_op_runners", "env_op_runners", plan_env_op_runners(now)),
    ]
    # Registered backup payloads are only ever removed by the retention pruner.
    protected = backups.backups_root(_SYS_DIR).resolve()

    def _outside(p: Path) -> bool:
        rp = Path(p).resolve()
        return rp != protected and protected not in rp.parents

    return [(label, key, items if key == "backups" else [p for p in items if _outside(p)])
            for label, key, items in plan]


def main() -> int:
    ap = argparse.ArgumentParser(
        epilog=(
            "Examples:\n"
            "  engram tidy                       dry run: show what would be deleted\n"
            "  engram tidy --apply                actually delete the planned items\n"
            "  engram tidy --apply --deep         also clean old launcher logs\n"
            "  engram tidy --apply --only pycache,pip_cache   clean just those two categories\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--base-dir", default=None, help="Root directory (default: ROOT)")
    ap.add_argument("--sys-dir", default=None, help="Sys directory (default: _SYS_DIR)")
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--deep", action="store_true", help="include deeper cleans (e.g., launcher logs)")
    ap.add_argument("--keep", type=int, default=None,
                    help="backups: keep at least N newest committed per kind (can only raise the policy floor)")
    ap.add_argument("--max-size-gb", type=float, default=None,
                    help="backups: size cap in GiB (default: min(2 GiB, 10%% of free space))")
    ap.add_argument("--adopt-legacy", action="store_true",
                    help="backups: adopt structurally valid env/<name>_old dirs into the backup registry")
    ap.add_argument(
        "--only", default=None,
        help=(
            "comma-separated subset: tmp,data_temp,brain,vscode,"
            "pytest_cache,winget_cache,npm_cache,pip_cache,vscode_cache,pycache,pytest_cache_default,launcher_logs,backups,env_op_runners"
        ),
    )
    if "/?" in sys.argv[1:]:
        # argparse understands -h/--help natively but not the Windows /? convention.
        ap.print_help()
        return 0
    args = ap.parse_args()

    if args.base_dir or args.sys_dir:
        configure_paths(root=args.base_dir, sys_dir=args.sys_dir)

    default_targets = (
        "tmp,data_temp,brain,vscode,"
        "pytest_cache,winget_cache,npm_cache,pip_cache,vscode_cache,pycache,pytest_cache_default,launcher_logs,backups,env_op_runners"
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

    size_cap = int(args.max_size_gb * 2**30) if args.max_size_gb is not None else None
    backups_blocked = False
    if "backups" in targets:
        lock = env_lock.inspect(_SYS_DIR)
        if lock.get("state") == "held":
            backups_blocked = True
            print("[backups] skipped: an environment operation holds the environment lock")

    if "backups" in targets and not backups_blocked and _active_journal() is not None:
        backups_blocked = True
        print("[backups] skipped: an unfinished environment operation journal exists (recovery backups must be kept)")

    adopted_paths: tuple[Path, ...] = ()
    lock_handle = None
    if "backups" in targets and not backups_blocked and args.apply:
        # Hold the environment lock for the whole mutation (adopt + delete + orphan marks) so tidy
        # cannot race an update that is mid-swap (review: tidy checked the lock but never held it).
        try:
            lock_handle = env_lock.acquire(_SYS_DIR, "tidy-backups")
        except env_lock.EnvLockBusy:
            backups_blocked = True
            print("[backups] skipped: an environment operation holds the environment lock")
            targets.discard("backups")

    try:
        if "backups" in targets and not backups_blocked and args.adopt_legacy:
            candidates = backups.find_legacy_candidates(_SYS_DIR)
            verb = "adopted" if args.apply else "would adopt"
            if args.apply:
                adopted = backups.adopt_legacy(_SYS_DIR, now=_utc_iso(now))
                adopted_paths = tuple(ref.path for ref in adopted)
                count = len(adopted)
            else:
                count = len(candidates)
            print(f"[legacy_adopt] {verb} {count} legacy *_old dir(s)")
            for c in candidates[:10]:
                print(f"    {c}")

        if backups_blocked:
            targets.discard("backups")

        backups_plan = None
        if "backups" in targets:
            backups_plan = plan_backups_retention(now, args.keep, size_cap, adopted_paths)
        plan = build_plan(now=now, deep=args.deep, keep_override=args.keep, size_cap_bytes=size_cap,
                          protect=adopted_paths)
        if "vscode_cache" in targets and VSCODE_USER_DATA_DIR.exists() and _vscode_is_running():
            print("[vscode_cache] skipped: VSCode (Code.exe) is currently running")
        for label, key, items in plan:
            run_item(label, key, items)
        if backups_plan is not None and args.apply and backups_plan.orphan_marks:
            backups.apply_orphan_marks(backups_plan, now=_utc_iso(now))
            print(f"[backups] marked {len(backups_plan.orphan_marks)} abandoned pending backup(s) as orphaned")
    finally:
        if lock_handle is not None:
            lock_handle.release()

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
