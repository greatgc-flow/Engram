"""check_deps.py — Axis-F: Map CALL/INVOKE relationships in _sys/ scripts via Gemini."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, _SYS_DIR, ai_available, archive_file, gemini_call, is_refusal,
    log_collab, save_raw, update_status_error,
)


def _merge_target_files(portable_root: Path) -> str:
    """Merge specific target scripts into one string for Gemini analysis."""
    targets = [
        portable_root / "start.bat",
        _SYS_DIR / "hooks" / "ctx-save.bat",
        _SYS_DIR / "hooks" / "ctx-end.bat",
        _SYS_DIR / "hooks" / "ctx_save.py",
        _SYS_DIR / "hooks" / "ctx_end.py",
        _SYS_DIR / "cli" / "msg.bat",
        portable_root / "manage.bat",
        portable_root / "manage.py",
        portable_root / "launch.bat",
        _SYS_DIR / "core" / "setup.py",
        _SYS_DIR / "core" / "cleanup.py",
    ]
    parts = []
    count = 0
    for t in targets:
        if t.exists():
            parts.append(f"=== {t.name} ===\n{t.read_text(encoding='utf-8', errors='replace')}")
            count += 1
    print(f"[script-deps] Merged {count} script files.")
    return "\n".join(parts)


def main() -> None:
    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "script-deps.json"
    dt = datetime.now().strftime("%Y%m%d%H%M%S")

    if not ai_available():
        print("[script-deps] ERROR: Gemini not available.")
        print("              Run start.bat first, or check _sys\\gemini\\status.json")
        sys.exit(1)

    merged = _merge_target_files(_PORTABLE_ROOT)
    if not merged:
        print("[script-deps] ERROR: Failed to merge script files.")
        sys.exit(1)

    schema = (
        f'{{"scan_ts":"{dt}",'
        '"nodes":[{"file":"","type":"bat or py"}],'
        '"edges":[{"caller":"","callee":"","method":"call or invoke or import"}]}}'
    )
    prompt = (
        "Analyze the provided scripts and map all CALL/INVOKE relationships. "
        f"Return ONLY valid JSON: {schema}"
    )

    print("[script-deps] Analyzing CALL/INVOKE relationships via Gemini...")
    result = gemini_call(prompt, stdin=merged)

    if result.returncode != 0:
        print("[script-deps] ERROR: gemini returned non-zero. Check auth or network.")
        out_file.unlink(missing_ok=True)
        log_collab("Axis-F", "check-deps.py", "FAIL", "Error: api_error")
        update_status_error(dt, "script_deps_failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-F", "check-deps.py", "REFUSED", "Gemini refused request")
        out_file.unlink(missing_ok=True)
        sys.exit(1)

    out_file.write_text(result.stdout, encoding="utf-8")
    save_raw("Axis-F", out_file)
    print(f"[script-deps] Done: {out_file}")
    print("[script-deps] Review edges for unexpected or missing call chains.")
    log_collab("Axis-F", "check-deps.py", "OK", f"Output: {out_file}")
    archive_file("scan-deps", out_file)


if __name__ == "__main__":
    main()
