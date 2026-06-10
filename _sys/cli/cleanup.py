"""
cleanup.py - Portable Dev Environment Space Optimizer
Tiered cleanup. AI peer cleanup driven by _sys/ai/peers.json — no code change needed to add peers.
"""
import os
import json
import shutil
import subprocess
from pathlib import Path


def get_dir_size(path: Path) -> int:
    total = 0
    try:
        for entry in Path(path).rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def format_size(b: int) -> str:
    if b >= 1024**3: return f"{b/(1024**3):.2f} GB"
    if b >= 1024**2: return f"{b/(1024**2):.2f} MB"
    if b >= 1024: return f"{b/1024:.2f} KB"
    return f"{b} B"


def load_peers(sys_dir: Path) -> dict:
    """Load AI peer definitions from _sys/ai/peers.json."""
    peers_path = sys_dir / "ai" / "peers.json"
    if peers_path.exists():
        try:
            return json.loads(peers_path.read_text(encoding="utf-8")).get("peers", {})
        except Exception:
            pass
    return {}


def remove_junction_safe(path: Path, label: str, dry_run: bool = False) -> None:
    path = Path(path)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return
    is_junction = os.path.islink(path) or getattr(st, "st_reparse_tag", 0) == 0xA0000003
    if not is_junction:
        return
    if dry_run:
        print(f"  [Wait] {label} — Junction 해제 예정")
        return
    try:
        subprocess.run(["cmd", "/c", f"rmdir \"{path}\""], check=True, capture_output=True)
        print(f"  [OK] {label} — Junction 해제됨")
    except Exception as e:
        print(f"  [Fail] Could not remove junction {label}: {e}")


def remove_path_safe(path: Path, label: str, dry_run: bool = False) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    size = get_dir_size(path)
    if dry_run:
        print(f"  [Wait] {label} — {format_size(size)} 삭제 예정")
        return size
    try:
        if path.is_dir(): shutil.rmtree(path)
        else: path.unlink()
        print(f"  [OK] {label} — {format_size(size)} 삭제됨")
        return size
    except Exception as e:
        print(f"  [Fail] Could not remove {label}: {e}")
        return 0


def run_cleanup(tier: int = 1, all_yes: bool = False, dry_run: bool = False, base_dir=None) -> None:
    if base_dir is None:
        sys_dir = Path(__file__).parent.parent.resolve()
        base_dir = sys_dir.parent
    else:
        base_dir = Path(base_dir)
        sys_dir = base_dir / "_sys"
    env_dir = sys_dir / "env"
    data_dir = sys_dir / "data"

    total_freed = 0

    print(f"\n{'='*50}")
    print(f"  Portable Dev Cleanup — Tier {tier}")
    if dry_run: print("  ※ 미리보기 모드 — 실제 삭제 안 함")
    print(f"{'='*50}")

    # ── Tier 1: Light ───────────────────────────────────────
    print("\n[Tier 1] 가벼운 정리 (안전)")
    total_freed += remove_path_safe(data_dir / "temp", r"임시 파일 (_sys\data\temp)", dry_run)
    total_freed += remove_path_safe(env_dir / "python" / "pip-cache", "pip 캐시", dry_run)
    total_freed += remove_path_safe(env_dir / "nodejs" / "npm-cache", "npm 캐시", dry_run)

    # IPC & editor state
    total_freed += remove_path_safe(base_dir / ".ai", r"AI IPC 통신 로그 (.ai)", dry_run)
    total_freed += remove_path_safe(base_dir / ".vscode", r"VS Code 임시 설정 (.vscode)", dry_run)
    total_freed += remove_path_safe(base_dir / "_state", r"AI 임시 상태 (_state)", dry_run)
    total_freed += remove_path_safe(base_dir / "WORKLOG.md", r"임시 작업 로그 (WORKLOG.md)", dry_run)

    # Test caches
    total_freed += remove_path_safe(base_dir / ".pytest_cache", r"최상위 pytest 캐시", dry_run)
    total_freed += remove_path_safe(sys_dir / "tests" / ".pytest_cache", r"단위 테스트 캐시", dry_run)
    total_freed += remove_path_safe(sys_dir / "tests" / "unit" / ".pytest_cache", r"단위 테스트 캐시(unit)", dry_run)
    total_freed += remove_path_safe(sys_dir / "tests" / "results", r"이전 테스트 결과물", dry_run)
    total_freed += remove_path_safe(sys_dir / "tests" / "local_test_tmp", r"로컬 통합 테스트 임시파일", dry_run)
    total_freed += remove_path_safe(sys_dir / "tests" / "integration" / "parallel_test_tmp", r"병렬 통합 테스트 임시파일", dry_run)

    # Per-peer runtime cleanup (driven by peers.json)
    peers = load_peers(sys_dir)
    for peer_id, cfg in peers.items():
        peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
        cfg_dir = peer_dir / "config"
        cleanup = cfg.get("cleanup", {})

        # Generic: status.json for every peer
        total_freed += remove_path_safe(peer_dir / "status.json", f"{peer_id} 상태 파일", dry_run)

        # Peer-dir exact paths (e.g. usage.json, session-map.json)
        for rel in cleanup.get("peer_paths", []):
            total_freed += remove_path_safe(peer_dir / rel, f"{peer_id} {rel}", dry_run)

        # Peer-dir globs (e.g. cq-*.txt)
        for pattern in cleanup.get("peer_globs", []):
            for f in peer_dir.glob(pattern):
                total_freed += remove_path_safe(f, f"{peer_id} {f.name}", dry_run)

        # Config-relative paths (e.g. daemon.log, tmp/)
        for rel in cleanup.get("config_paths", []):
            total_freed += remove_path_safe(cfg_dir / rel, f"{peer_id} config/{rel}", dry_run)

    # Global Python caches
    pycache_count = 0
    pycache_size = 0
    for p in base_dir.rglob("__pycache__"):
        if p.is_dir():
            sz = get_dir_size(p)
            pycache_size += sz
            if not dry_run: shutil.rmtree(p)
            pycache_count += 1
    if pycache_count > 0:
        print(f"  [OK] __pycache__ — {pycache_count}개 디렉토리 삭제됨 ({format_size(pycache_size)})")
        total_freed += pycache_size

    # Logs (keep latest 5)
    log_path = data_dir / "logs"
    if log_path.exists():
        logs = sorted(list(log_path.glob("*.log")), key=os.path.getmtime, reverse=True)
        to_del = logs[5:]
        if to_del:
            del_sz = sum(l.stat().st_size for l in to_del)
            if not dry_run:
                for l in to_del: l.unlink()
            print(f"  [OK] 오래된 로그 — {len(to_del)}개 삭제 ({format_size(del_sz)})")
            total_freed += del_sz

    # ── Tier 2: Hard ────────────────────────────────────────
    if tier >= 2:
        print("\n[Tier 2] 환경 정리 (재설치 필요 항목)")
        total_freed += remove_path_safe(data_dir / "setup-files", "설치 아카이브 (zip/exe)", dry_run)
        total_freed += remove_path_safe(env_dir / "venv", "Python 가상환경 (venv)", dry_run)

    # ── Tier 3: Reset ───────────────────────────────────────
    if tier >= 3:
        confirm = all_yes or input("\n  [?] 환경 리셋 (런타임 및 인증 삭제) 계속할까요? [y/N]: ").lower().startswith("y")
        if confirm:
            print("\n[Tier 3] 런타임 리셋 (전체 재설치 필요)")

            # Remove env/ runtimes except python (includes nodejs/npm-global → AI CLI binaries)
            if env_dir.exists():
                for item in env_dir.iterdir():
                    if item.name == "python":
                        continue
                    total_freed += remove_path_safe(item, f"Runtime ({item.name})", dry_run)

            # Per-peer: remove auth/config data and junctions (driven by peers.json)
            for peer_id, cfg in peers.items():
                if not cfg.get("enabled"):
                    continue
                peer_dir = sys_dir / cfg.get("sys_subdir", peer_id)
                cfg_dir = peer_dir / "config"

                # Remove auth config (NOT the whole peer dir — scripts/project stay)
                if cfg_dir.exists() and not cfg_dir.is_symlink():
                    total_freed += remove_path_safe(cfg_dir, f"{peer_id} 인증 데이터", dry_run)

                # Remove project junction (root .~~ dir)
                if cfg.get("project_junction"):
                    root_dir = cfg.get("root_dir", f".{peer_id}")
                    remove_junction_safe(base_dir / root_dir, f"{peer_id} 프로젝트 Junction ({root_dir})", dry_run)

                # Remove host junction (%USERPROFILE%\.{peer})
                if cfg.get("host_junction"):
                    hj = cfg["host_junction"]
                    host_path = Path(os.environ.get(hj.get("host_env", "USERPROFILE"), "")) / hj.get("host_dirname", f".{peer_id}")
                    remove_junction_safe(host_path, f"{peer_id} 호스트 Junction ({host_path.name})", dry_run)

    # ── Tier 4: ZeroBase ────────────────────────────────────
    if tier >= 4:
        confirm = all_yes or input("\n  [!] 최종 경고: ZeroBase (워크스페이스 포함 전체 삭제) 계속할까요? [y/N]: ").lower().startswith("y")
        if confirm:
            print("\n[Tier 4] 제로베이스 초기화 (데이터 포함 전체 삭제)")
            total_freed += remove_path_safe(base_dir / "workspace", "워크스페이스 데이터", dry_run)
            total_freed += remove_path_safe(base_dir / "_archive", "전체 아카이브/로그", dry_run)

            for f in base_dir.glob("*.md"):
                total_freed += f.stat().st_size
                if not dry_run: f.unlink()
                print(f"  [OK] 문서 삭제 — {f.name}")

            local_config = sys_dir / "local.config.bat"
            if local_config.exists():
                total_freed += local_config.stat().st_size
                if not dry_run: local_config.unlink()

    print(f"\n{'='*50}")
    if dry_run:
        print(f"  미리보기 결과: 총 {format_size(total_freed)} 확보 예정")
    else:
        print(f"  정리 완료: 총 {format_size(total_freed)} 확보됨")
    print(f"{'='*50}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", type=int, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tier = args.tier
    if tier is None:
        print("=====================================================")
        print(" Portable Dev - Cleanup Utility")
        print("=====================================================")
        print(" 1. Light (Safe)  - Temp files, caches, old logs")
        print(" 2. Hard          - Tier 1 + Setup archives + venv")
        print(" 3. Reset         - Tier 2 + Runtimes + AI CLIs + Junctions")
        print(" 4. ZeroBase      - Tier 3 + Workspace + All data (WIPE)")
        print("=====================================================")
        try:
            choice = input("Choose cleanup level (1-4, Default=1): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
        tier = int(choice) if choice in ("1", "2", "3", "4") else 1

    run_cleanup(tier=tier, all_yes=args.all, dry_run=args.dry_run)
