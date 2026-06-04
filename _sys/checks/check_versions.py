"""check_versions.py — Axis-B: Check latest tool versions via Gemini."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, archive_file, build_env,
    gemini_call, is_refusal, log_collab, save_raw, update_status_error,
)

_PROMPT = (
    "Search for the latest stable release versions of these tools as of today. "
    "Return ONLY valid JSON, no markdown, no explanation. "
    'Format: {"ripgrep":"V","fd":"V","jq":"V","bat":"V","delta":"V",'
    '"fzf":"V","oh-my-posh":"V","nodejs-lts":"V"} '
    "where V is the version string like 1.2.3. "
    "Sources: GitHub releases for BurntSushi/ripgrep, sharkdp/fd, stedolan/jq, "
    "sharkdp/bat, dandavison/delta, junegunn/fzf, JanDeDobbeleer/oh-my-posh, nodejs.org LTS."
)


def main() -> None:
    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "version-check.json"
    dt = datetime.now().strftime("%Y%m%d%H%M%S")

    if not ai_available():
        print("[version-check] ERROR: Gemini not available.")
        print("                Run start.bat first, or check _sys\\gemini\\status.json")
        sys.exit(1)

    print(f"[version-check] Querying latest tool versions via Gemini...")
    print(f"[version-check] Date: {dt[:8]}")

    result = gemini_call(_PROMPT)

    if result.returncode != 0:
        print("[version-check] ERROR: gemini returned non-zero. Check auth or network.")
        print("                Run 'gemini' interactively to re-authenticate.")
        out_file.unlink(missing_ok=True)
        log_collab("Axis-B", "check-versions.py", "FAIL", "Error: api_error")
        update_status_error(dt, "version_check_failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-B", "check-versions.py", "REFUSED", "Gemini refused request")
        out_file.unlink(missing_ok=True)
        sys.exit(1)

    out_file.write_text(result.stdout, encoding="utf-8")
    save_raw("Axis-B", out_file)
    print(f"[version-check] Done: {out_file}")
    print("[version-check] Compare with setup.ps1 version section to find updates.")
    log_collab("Axis-B", "check-versions.py", "OK", f"Output: {out_file}")
    archive_file("scan-env", out_file)


if __name__ == "__main__":
    main()
