"""
scrubber.py - Tiered cleanup for Portable Dev Environment.
Tier definitions are hardcoded below (_tier1 through _tier5) - there is no
cleanup_tiers.json config file or JSON-driven fallback mechanism.
AI peer items driven by peers.json. State-aware for register artifacts.

Tier 1  Light     — 캐시·임시파일·로그 (안전, 재설치 불필요)
Tier 2  Soft      — Tier 1 + 설치 아카이브·venv·로컬 설정
Tier 3  Reset     — Tier 2 + 런타임·도구·AI 인증·Junction
Tier 4  ZeroBase  — Tier 3 + 워크스페이스·아카이브·AI Peer 시스템
Tier 5  Purge     — Tier 4 + Python (완전 초기화)
"""
import os
import json
import shutil
import stat
import subprocess
from pathlib import Path


# ── Utilities ────────────────────────────────────────────────────────────────

def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in Path(path).rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def _fmt(b: int) -> str:
    if b >= 1024**3: return f"{b/(1024**3):.2f} GB"
    if b >= 1024**2: return f"{b/(1024**2):.2f} MB"
    if b >= 1024:    return f"{b/1024:.2f} KB"
    return f"{b} B"


def _load_peers(sys_dir: Path) -> dict:
    p = sys_dir / "ai" / "peers.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass
    return {}


def _is_junction(path: Path) -> bool:
    try:
        st = path.lstat()
        return os.path.islink(path) or getattr(st, "st_reparse_tag", 0) == 0xA0000003
    except Exception:
        return False


def _remove_junction(path: Path, label: str, dry_run: bool) -> None:
    if not _is_junction(path):
        return
    if dry_run:
        print(f"  [Wait] {label} — Junction 해제 예정")
        return
    try:
        subprocess.run(f'rmdir "{path}"', shell=True, check=True, capture_output=True)
        print(f"  [OK] {label} — Junction 해제됨")
    except Exception as e:
        print(f"  [Fail] {label}: {e}")


def _remove_path(path: Path, label: str, dry_run: bool) -> int:
    if not path.exists():
        return 0
    size = _dir_size(path)
    if dry_run:
        print(f"  [Wait] {label} — {_fmt(size)} 삭제 예정")
        return size
    try:
        if path.is_dir():
            shutil.rmtree(path, onerror=_on_rm_error)
        else:
            try:
                path.unlink()
            except OSError:
                os.chmod(path, stat.S_IWRITE)
                path.unlink()
        print(f"  [OK] {label} — {_fmt(size)} 삭제됨")
        return size
    except Exception as e:
        print(f"  [Fail] {label}: {e}")
        return 0


def _confirm(msg: str, all_yes: bool, dry_run: bool) -> bool:
    if all_yes or dry_run:
        return True
    return input(msg).lower().startswith("y")


# ── Tier implementations ──────────────────────────────────────────────────────

def _tier1(base_dir: Path, sys_dir: Path, peers: dict, dry_run: bool) -> int:
    env_dir  = sys_dir / "env"
    data_dir = sys_dir / "data"
    freed    = 0

    freed += _remove_path(env_dir / "python" / "pip-cache",  "pip 캐시",  dry_run)
    freed += _remove_path(env_dir / "nodejs"  / "npm-cache",  "npm 캐시",  dry_run)
    freed += _remove_path(data_dir / "temp",    "임시 파일 (_sys/data/temp)", dry_run)
    freed += _remove_path(base_dir / ".ai",     "AI IPC 통신 로그 (.ai)",    dry_run)
    freed += _remove_path(base_dir / ".vscode", "VS Code 임시 설정",          dry_run)
    freed += _remove_path(base_dir / "_state",  "AI 임시 상태 (_state)",      dry_run)
    freed += _remove_path(base_dir / "WORKLOG.md", "임시 작업 로그",           dry_run)

    # Keep last 5 launcher logs
    for log_glob, label in [
        (base_dir / "_archive" / "logs", "런처 로그"),
        (data_dir / "logs",              "시스템 로그"),
    ]:
        if log_glob.exists():
            logs = sorted(log_glob.glob("*.log"), key=os.path.getmtime, reverse=True)
            to_del = list(logs)[5:]
            if to_del:
                sz = sum(l.stat().st_size for l in to_del)
                if not dry_run:
                    for l in to_del:
                        l.unlink()
                print(f"  [OK] {label} — {len(to_del)}개 삭제 ({_fmt(sz)})")
                freed += sz

    # pytest caches
    for pth, lbl in [
        (base_dir / ".pytest_cache",                             "pytest 캐시 (root)"),
        (sys_dir  / "tests" / ".pytest_cache",                   "pytest 캐시 (tests)"),
        (sys_dir  / "tests" / "unit" / ".pytest_cache",          "pytest 캐시 (unit)"),
        (sys_dir  / "tests" / "results",                         "테스트 결과물"),
        (sys_dir  / "tests" / "local_test_tmp",                  "로컬 테스트 임시"),
        (sys_dir  / "tests" / "integration" / "parallel_test_tmp", "병렬 테스트 임시"),
    ]:
        freed += _remove_path(pth, lbl, dry_run)

    # __pycache__
    count, psize = 0, 0
    for p in base_dir.rglob("__pycache__"):
        if p.is_dir():
            psize += _dir_size(p)
            if not dry_run:
                shutil.rmtree(p)
            count += 1
    if count:
        print(f"  [OK] __pycache__ — {count}개 삭제 ({_fmt(psize)})")
        freed += psize

    # Per-peer light cleanup (driven by peers.json cleanup field)
    for peer_id, cfg in peers.items():
        peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
        cfg_dir  = peer_dir / "config"
        cleanup  = cfg.get("cleanup", {})
        freed   += _remove_path(peer_dir / "status.json", f"{peer_id} 상태 파일", dry_run)
        for rel in cleanup.get("peer_paths", []):
            freed += _remove_path(peer_dir / rel, f"{peer_id} {rel}", dry_run)
        for pattern in cleanup.get("peer_globs", []):
            for f in peer_dir.glob(pattern):
                freed += _remove_path(f, f"{peer_id} {f.name}", dry_run)
        for rel in cleanup.get("config_paths", []):
            freed += _remove_path(cfg_dir / rel, f"{peer_id} config/{rel}", dry_run)

    return freed


def _tier2(base_dir: Path, sys_dir: Path, peers: dict, dry_run: bool) -> int:
    env_dir  = sys_dir / "env"
    data_dir = sys_dir / "data"
    tools_dir = sys_dir / "tools"
    freed    = 0
    freed += _remove_path(data_dir / "setup-files", "설치 아카이브 (zip/exe)", dry_run)
    freed += _remove_path(env_dir  / "venv",         "Python 가상환경 (venv)",  dry_run)
    # State files (host-specific)
    freed += _remove_path(data_dir / "state" / "register.state.json", "등록 상태 (register.state.json)", dry_run)
    freed += _remove_path(data_dir / "state" / "install.state.json",  "설치 상태 (install.state.json)",  dry_run)
    freed += _remove_path(sys_dir  / "config.json",                   "시스템 로컬 설정 (config.json)",  dry_run)
    for peer_id, cfg in peers.items():
        peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
        freed += _remove_path(
            peer_dir / "project" / "settings.local.json",
            f"{peer_id} 로컬 설정 (settings.local.json)", dry_run
        )
    # D10 atomic-swap rollback dirs (tool_v{X}_old left behind by ensure_tool)
    if tools_dir.exists():
        for item in tools_dir.iterdir():
            if item.is_dir() and item.name.endswith("_old"):
                freed += _remove_path(item, f"도구 롤백 ({item.name})", dry_run)
    return freed


def _tier3(base_dir: Path, sys_dir: Path, peers: dict, dry_run: bool) -> int:
    env_dir = sys_dir / "env"
    freed   = 0
    if env_dir.exists():
        for item in env_dir.iterdir():
            if item.name not in ("python", "python.purge", "venv"):
                freed += _remove_path(item, f"Runtime ({item.name})", dry_run)
    tools_dir = sys_dir / "tools"
    if tools_dir.exists():
        for item in tools_dir.iterdir():
            if item.name != "apps":
                freed += _remove_path(item, f"Tool ({item.name})", dry_run)
    for peer_id, cfg in peers.items():
        if not cfg.get("enabled"):
            continue
        peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
        cfg_dir  = peer_dir / "config"
        if cfg_dir.exists() and not cfg_dir.is_symlink():
            freed += _remove_path(cfg_dir, f"{peer_id} 인증 데이터", dry_run)
        if cfg.get("project_junction"):
            root_dir = cfg.get("root_dir", f".{peer_id}")
            _remove_junction(base_dir / root_dir, f"{peer_id} 프로젝트 Junction", dry_run)
        if cfg.get("host_junction"):
            hj = cfg["host_junction"]
            host_path = Path(os.environ.get(hj.get("host_env", "USERPROFILE"), "")) / hj.get("host_dirname", f".{peer_id}")
            _remove_junction(host_path, f"{peer_id} 호스트 Junction", dry_run)
    return freed


def _tier4(base_dir: Path, sys_dir: Path, peers: dict, dry_run: bool) -> int:
    freed = 0
    freed += _remove_path(base_dir / "workspace", "워크스페이스 데이터", dry_run)
    freed += _remove_path(base_dir / "_archive",  "아카이브/로그 전체",  dry_run)
    for f in base_dir.glob("*.md"):
        sz = f.stat().st_size
        if not dry_run:
            f.unlink()
            print(f"  [OK] 문서 삭제 — {f.name}")
        else:
            print(f"  [Wait] 문서 — {f.name} 삭제 예정")
        freed += sz
    for peer_id, cfg in peers.items():
        if not cfg.get("enabled"):
            continue
        peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
        if peer_dir.exists():
            freed += _remove_path(peer_dir, f"{peer_id} 시스템 전체", dry_run)
    return freed


def _tier5(base_dir: Path, sys_dir: Path, dry_run: bool) -> int:
    freed  = 0
    py_dir = sys_dir / "env" / "python"
    if not py_dir.exists():
        return 0
    py_size = _dir_size(py_dir)
    if dry_run:
        print(f"  [Wait] Python 런타임 — {_fmt(py_size)} 삭제 예정 (백그라운드)")
        return py_size
    purge_dir = sys_dir / "env" / "python.purge"
    try:
        if purge_dir.exists():
            shutil.rmtree(purge_dir, onerror=_on_rm_error)
        py_dir.rename(purge_dir)
        bat = (
            "@echo off\r\n"
            f"timeout /T 5 /NOBREAK >nul\r\n"
            f"rmdir /s /q \"{purge_dir}\"\r\n"
            f"del \"%~f0\"\r\n"
        )
        bat_path = Path(os.environ.get("TEMP", str(sys_dir / "env"))) / "_purge_python.bat"
        bat_path.write_text(bat, encoding="mbcs")
        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        print(f"  [OK] Python 런타임 — {_fmt(py_size)} 백그라운드 삭제 예약됨")
        freed += py_size
    except Exception as e:
        print(f"  [Fail] Python 삭제 실패: {e}\n         수동 삭제: {py_dir}")
    return freed


# ── Public entry point ────────────────────────────────────────────────────────

def run(ctx: dict) -> None:
    """Run tiered cleanup. Reads --tier, --all, --dry-run from ctx['args']."""
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tier",    type=int,  default=None)
    parser.add_argument("--all",  "-y", action="store_true")
    parser.add_argument("--dry-run",  action="store_true")
    parsed, _ = parser.parse_known_args(ctx.get("args", []))

    tier    = parsed.tier
    all_yes = parsed.all
    dry_run = parsed.dry_run

    base_dir = ctx["base_dir"]
    sys_dir  = ctx["sys_dir"]
    peers    = _load_peers(sys_dir)

    if tier is None:
        print("=" * 54)
        print("  Portable Dev - Cleanup Utility")
        print("=" * 54)
        print("  1. Light    — 캐시·임시파일·로그 (안전)")
        print("  2. Soft     — Tier 1 + 설치 아카이브·venv·로컬 설정")
        print("  3. Reset    — Tier 2 + 런타임·도구·AI 인증·Junction")
        print("  4. ZeroBase — Tier 3 + 워크스페이스·AI Peer 시스템")
        print("  5. Purge    — Tier 4 + Python (완전 초기화)")
        print("=" * 54)
        try:
            choice = input("  선택 (1-5, 기본값=1): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
        tier = int(choice) if choice in ("1", "2", "3", "4", "5") else 1

    freed = 0
    print(f"\n{'='*54}")
    print(f"  Portable Dev Cleanup — Tier {tier}")
    if dry_run:
        print("  ※ 미리보기 모드 — 실제 삭제 안 함")
    print(f"{'='*54}")

    print("\n[Tier 1] 가벼운 정리 (안전)")
    freed += _tier1(base_dir, sys_dir, peers, dry_run)

    if tier >= 2:
        print("\n[Tier 2] Soft 정리 (재다운로드/재생성 필요)")
        freed += _tier2(base_dir, sys_dir, peers, dry_run)

    if tier >= 3:
        if not _confirm("\n  [?] 런타임·도구·AI 인증 삭제 계속할까요? [y/N]: ", all_yes, dry_run):
            _print_summary(freed, dry_run)
            return
        print("\n[Tier 3] Runtime Reset (전체 재설치 필요)")
        freed += _tier3(base_dir, sys_dir, peers, dry_run)

    if tier >= 4:
        if not _confirm("\n  [!] 경고: 워크스페이스·AI Peer 시스템 전체 삭제 계속할까요? [y/N]: ", all_yes, dry_run):
            _print_summary(freed, dry_run)
            return
        print("\n[Tier 4] ZeroBase")
        freed += _tier4(base_dir, sys_dir, peers, dry_run)

    if tier >= 5:
        if not _confirm("\n  [!!!] 최종 경고: Python 삭제 (INSTALL.bat 재실행 필수) 계속할까요? [y/N]: ", all_yes, dry_run):
            _print_summary(freed, dry_run)
            return
        print("\n[Tier 5] Purge — Python 런타임 삭제")
        freed += _tier5(base_dir, sys_dir, dry_run)

    _print_summary(freed, dry_run)


def _print_summary(freed: int, dry_run: bool) -> None:
    print(f"\n{'='*54}")
    if dry_run:
        print(f"  미리보기: 총 {_fmt(freed)} 확보 예정")
    else:
        print(f"  정리 완료: 총 {_fmt(freed)} 확보됨")
    print(f"{'='*54}")
