"""check_agents.py — Axis-E: Analyze agent consistency via Gemini."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    _PORTABLE_ROOT, ai_available, archive_file, extract_json_block, gemini_call,
    is_refusal, log_collab, save_raw, update_status_error,
)


def _merge_agent_files(agents_dir: Path) -> str:
    """Merge all agent .md files into a single string."""
    files = sorted(agents_dir.glob("*.md"))
    if not files:
        return ""
    parts = [f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}" for f in files]
    print(f"[agent-audit] Merged {len(files)} agent files.")
    return "\n".join(parts)


def main() -> None:
    archive_dir = _PORTABLE_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_file = archive_dir / "agent-audit.json"
    agents_dir = _PORTABLE_ROOT / ".claude" / "agents"
    dt = datetime.now().strftime("%Y%m%d%H%M%S")

    if not ai_available():
        print("[agent-audit] ERROR: Gemini not available.")
        print("              Run start.bat first, or check _sys\\gemini\\status.json")
        sys.exit(1)

    if not agents_dir.exists():
        print(f"[agent-audit] ERROR: Agents directory not found: {agents_dir}")
        sys.exit(1)

    merged = _merge_agent_files(agents_dir)
    if not merged:
        print(f"[agent-audit] ERROR: No agent .md files found in {agents_dir}")
        sys.exit(1)

    schema = (
        f'{{"scan_ts":"{dt}",'
        '"overlaps":[{"agents":[],"issue":""}],'
        '"gaps":[{"task":"","suggested_owner":""}],'
        '"inconsistencies":[{"agent":"","issue":"","severity":"High or Medium or Low"}],'
        '"ok_count":0}'
    )
    prompt = (
        "Analyze ALL agent markdown files provided. Find: "
        "1) Role overlaps (two agents doing the same thing), "
        "2) Coverage gaps (tasks no agent handles), "
        "3) Inconsistencies with CONVENTION.md. "
        f"Return ONLY valid JSON: {schema}"
    )

    print("[agent-audit] Analyzing agent definitions via Gemini...")
    result = gemini_call(prompt, stdin=merged)

    if result.returncode != 0:
        print("[agent-audit] ERROR: gemini returned non-zero. Check auth or network.")
        out_file.unlink(missing_ok=True)
        log_collab("Axis-E", "check-agents.py", "FAIL", "Error: api_error")
        update_status_error(dt, "agent_audit_failed")
        sys.exit(1)

    if is_refusal(result.stdout):
        log_collab("Axis-E", "check-agents.py", "REFUSED", "Gemini refused request")
        out_file.unlink(missing_ok=True)
        sys.exit(1)

    # Extract clean JSON block (strip YOLO messages, routing errors, code fences)
    clean = extract_json_block(result.stdout)
    if clean.startswith("{"):
        out_file.write_text(clean, encoding="utf-8")
        print("[agent-audit] JSON extracted cleanly.")
    else:
        out_file.write_text(result.stdout, encoding="utf-8")
        print("[agent-audit] WARNING: No JSON found in output.")

    save_raw("Axis-E", out_file)
    print(f"[agent-audit] Done: {out_file}")
    print("[agent-audit] Review overlaps and gaps before adding new agents.")
    log_collab("Axis-E", "check-agents.py", "OK", f"Output: {out_file}")
    archive_file("scan-audit", out_file)


if __name__ == "__main__":
    main()
