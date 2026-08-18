import json
import os
import subprocess
import sys
from pathlib import Path


CLI_DIR = Path(__file__).resolve().parent
SYS_DIR = CLI_DIR.parent
STDIN_LOG = SYS_DIR / "data" / "temp" / "ag_statusline_stdin.log"


def _format_statusline(data: dict) -> str:
    """Format unified statusline string from Antigravity JSON input."""
    # 1. Model & Effort
    m = data.get("model")
    if isinstance(m, dict):
        model_name = m.get("display_name") or m.get("id") or "Unknown"
        effort = m.get("effort") or ""
    elif isinstance(m, str):
        model_name = m
        effort = ""
    else:
        model_name = data.get("model_name", "Unknown")
        effort = ""

    if not effort:
        mre = data.get("model_reasoning_effort") or data.get("effort", "")
        if isinstance(mre, dict):
            effort = mre.get("level", "")
        elif isinstance(mre, str):
            effort = mre

    if effort and effort.lower() not in model_name.lower():
        model_name = f"{model_name} ({effort.capitalize()})"

    # 2. Context Window
    ctx = data.get("context_window", {})
    if ctx:
        used_tokens = ctx.get("total_input_tokens", 0) + ctx.get("total_output_tokens", 0)
        if used_tokens == 0 and "current_usage" in ctx:
            cur = ctx["current_usage"]
            used_tokens = cur.get("input_tokens", 0) + cur.get("output_tokens", 0)
        total_tokens = ctx.get("context_window_size", 1048576)
        pct = ctx.get("used_percentage", 0.0)
        ctx_str = f"ctx:{int(used_tokens / 1000)}k/{int(total_tokens / 1000)}k ({pct:.0f}%)"
    elif "context_used_tokens" in data:
        used_tokens = data["context_used_tokens"]
        total_tokens = data.get("context_total_tokens", 1048576)
        pct = data.get("context_used_pct", 0.0)
        ctx_str = f"ctx:{int(used_tokens / 1000)}k/{int(total_tokens / 1000)}k ({pct:.0f}%)"
    else:
        ctx_str = "ctx:ok"

    # 3. Location & Git Branch
    cwd = data.get("cwd") or data.get("workspace", {}).get("current_dir", "")
    short_cwd = Path(cwd).name if cwd else ""
    git_branch = ""
    if cwd and Path(cwd).is_dir():
        try:
            git_branch = subprocess.run(
                ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1,
            ).stdout.strip()
        except Exception:
            pass
    loc_str = f"{short_cwd} ({git_branch})" if git_branch else short_cwd

    # 4. Quotas (G-5H G-7D 3P-5H 3P-7D)
    q = data.get("quota", {})
    buckets = []
    bucket_map = [
        ("gemini-5h", "G-5H"),
        ("gemini-weekly", "G-7D"),
        ("3p-5h", "3P-5H"),
        ("3p-weekly", "3P-7D"),
    ]
    for key, label in bucket_map:
        if key in q and isinstance(q[key], dict):
            rem = q[key].get("remaining_fraction")
            if rem is not None:
                used_pct = round((1.0 - float(rem)) * 100.0)
                buckets.append(f"{label}:{used_pct}%")
    q_str = " ".join(buckets) if buckets else "quota:N/A"

    # 5. Hub / Room Status
    room_id = "room-efde"
    return f"ag:{model_name} | {ctx_str} | {loc_str} | {q_str} | hub:idle [{room_id}]"


def main():
    stdin_data = ""
    if not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read()
        except Exception:
            pass

    # Save live status log for telemetry collectors
    if stdin_data:
        try:
            STDIN_LOG.parent.mkdir(parents=True, exist_ok=True)
            STDIN_LOG.write_text(stdin_data, encoding="utf-8")
        except OSError:
            pass

    # Format statusline
    try:
        if stdin_data:
            data = json.loads(stdin_data)
            print(_format_statusline(data), end="")
        else:
            print("ag:Gemini | ctx:ok | hub:idle [room-efde]", end="")
    except Exception:
        print("ag:Gemini | ctx:ok | hub:idle [room-efde]", end="")

    sys.exit(0)


if __name__ == "__main__":
    main()
