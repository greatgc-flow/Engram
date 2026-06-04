"""
cleanup.py - Portable Dev Environment Space Optimizer (Python Refactored)
Handles tiered cleanup of temporary files, caches, runtimes, and workspaces.
"""
import os
import shutil
import re
from pathlib import Path

def get_dir_size(path):
    total = 0
    try:
        for entry in Path(path).rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total

def format_size(bytes):
    if bytes >= 1024**3: return f"{bytes/(1024**3):.2f} GB"
    if bytes >= 1024**2: return f"{bytes/(1024**2):.2f} MB"
    if bytes >= 1024: return f"{bytes/1024:.2f} KB"
    return f"{bytes} B"

def remove_path_safe(path, label, dry_run=False):
    path = Path(path)
    if not path.exists(): return 0
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

def run_cleanup(tier=1, all_yes=False, dry_run=False, base_dir=None):
    if base_dir is None:
        sys_dir = Path(__file__).parent.parent.resolve()
        base_dir = sys_dir.parent
    else:
        base_dir = Path(base_dir)
        sys_dir = base_dir / "_sys"
    env_dir = sys_dir / "env"
    data_dir = sys_dir / "data"
    tools_dir = sys_dir / "tools"
    
    total_freed = 0
    
    print(f"\n{'='*50}")
    print(f"  Portable Dev Cleanup — Tier {tier}")
    if dry_run: print("  ※ 미리보기 모드 — 실제 삭제 안 함")
    print(f"{'='*50}")

    # Tier 1: Light
    print("\n[Tier 1] 가벼운 정리 (안전)")
    total_freed += remove_path_safe(data_dir / "temp", r"임시 파일 (_sys\data\temp)", dry_run)
    total_freed += remove_path_safe(env_dir / "python" / "pip-cache", "pip 캐시", dry_run)
    total_freed += remove_path_safe(env_dir / "nodejs" / "npm-cache", "npm 캐시", dry_run)
    
    # Logs
    log_path = data_dir / "logs"
    if log_path.exists():
        logs = sorted(list(log_path.glob("*.log")), key=os.path.getmtime, reverse=True)
        to_del = logs[5:] # Keep latest 5
        if to_del:
            del_sz = sum(l.stat().st_size for l in to_del)
            if not dry_run:
                for l in to_del: l.unlink()
            print(f"  [OK] 오래된 로그 — {len(to_del)}개 삭제 ({format_size(del_sz)})")
            total_freed += del_sz

    # Tier 2: Hard
    if tier >= 2:
        print("\n[Tier 2] 환경 정리 (재설치 필요 항목)")
        total_freed += remove_path_safe(data_dir / "setup-files", "설치 아카이브 (zip/exe)", dry_run)
        total_freed += remove_path_safe(env_dir / "venv", "Python 가상환경 (venv)", dry_run)

    # Tier 3: Reset
    if tier >= 3:
        confirm = all_yes or input("\n  [?] 환경 리셋 (런타임 및 설정 삭제) 계속할까요? [y/N]: ").lower().startswith('y')
        if confirm:
            print("\n[Tier 3] 런타임 리셋 (전체 재설치 필요)")
            total_freed += remove_path_safe(env_dir, r"Portable Runtimes (_sys\env)", dry_run)
            total_freed += remove_path_safe(tools_dir, r"Portable Tools (_sys\tools)", dry_run)
            total_freed += remove_path_safe(sys_dir / "claude", r"Claude Config (_sys\claude)", dry_run)
            total_freed += remove_path_safe(sys_dir / "gemini" / "config", r"Gemini Config (_sys\gemini\config)", dry_run)
            status_json = sys_dir / "gemini" / "status.json"
            if status_json.exists():
                total_freed += status_json.stat().st_size
                if not dry_run: status_json.unlink()

    # Tier 4: ZeroBase
    if tier >= 4:
        confirm = all_yes or input("\n  [!] 최종 경고: ZeroBase (워크스페이스 포함 전체 삭제) 계속할까요? [y/N]: ").lower().startswith('y')
        if confirm:
            print("\n[Tier 4] 제로베이스 초기화 (데이터 포함 전체 삭제)")
            total_freed += remove_path_safe(base_dir / "workspace", "워크스페이스 데이터", dry_run)
            total_freed += remove_path_safe(base_dir / "_archive", "전체 아카이브/로그", dry_run)
            
            # Root docs
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
    import sys as _sys
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
        print(" 1. Light (Safe) - Temp files, caches, old logs")
        print(" 2. Hard        - Tier 1 + Setup archives + venv")
        print(" 3. Reset       - Tier 2 + Portable Runtimes/Tools")
        print(" 4. ZeroBase    - Tier 3 + Workspace + All data (WIPE)")
        print("=====================================================")
        try:
            choice = input("Choose cleanup level (1-4, Default=1): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
        tier = int(choice) if choice in ("1", "2", "3", "4") else 1

    run_cleanup(tier=tier, all_yes=args.all, dry_run=args.dry_run)
