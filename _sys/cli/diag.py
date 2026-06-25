import os
import json
import subprocess
from pathlib import Path
import sys

CLI_DIR = Path(__file__).parent
SYS_DIR = CLI_DIR.parent
PORTABLE_ROOT = SYS_DIR.parent

sys.path.insert(0, str(SYS_DIR / "core"))
from hub_peer import resolve_peer_sys_dir

def main():
    print("="*60)
    print(" 🛠️  Antigravity Collaboration Environment Diagnostics ")
    print("="*60)
    
    print("\n[ROOM & HUB STATUS]")
    hub_py = SYS_DIR / "core" / "hub.py"
    if hub_py.exists():
        subprocess.run(["python", str(hub_py), "status"])
    else:
        print("hub.py not found.")

    print("\n" + "="*60)
    print(" 📊 PEER DETAILED METRICS")
    print("="*60)

    peers = []
    peer_dirs = {}
    orch_file = SYS_DIR / "ai" / "orchestration.json"
    if orch_file.exists():
        try:
            orch_data = json.loads(orch_file.read_text(encoding="utf-8"))
            for node in orch_data.get("hub_nodes", []):
                if node.get("type") == "peer" and node.get("enabled", True):
                    pid = node.get("node_id")
                    if pid:
                        peers.append(pid)
                        subdir = resolve_peer_sys_dir(pid)
                        if subdir:
                            peer_dirs[pid] = SYS_DIR / subdir
                        else:
                            peer_dirs[pid] = SYS_DIR / pid
        except Exception:
            pass
    if not peers:
        peers = ["ag", "cc", "cx"]
        peer_dirs = {
            "ag": SYS_DIR / "antigravity",
            "cc": SYS_DIR / "claude",
            "cx": SYS_DIR / "codex"
        }

    for peer in peers:
        print(f"\n[{peer.upper()} PEER INFO]")
        
        # Check live state log first
        live_file = None
        if peer == "ag":
            live_file = CLI_DIR / "ag_stdin.log"
        elif peer == "cc":
            live_file = SYS_DIR / "claude" / "config" / "status_input.log"

        data = {}
        health_file = peer_dirs[peer] / "health.json"
        
        if live_file and live_file.exists():
            try:
                data = json.loads(live_file.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        # Fallback to health.json if live_file is missing or empty
        health_data = {}
        if health_file.exists():
            try:
                health_data = json.loads(health_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        if not data and not health_data:
            print("  (No data found)")
            continue

        # General Health
        avail = health_data.get("availability", {})
        print(f"  - Gate: {avail.get('gate_open')} | Quarantined: {avail.get('quarantined')}")
        
        # Context & Tokens (Live preferred)
        ctx_window = "Unknown"
        session_tokens = 0
        if "context_window" in data:
            ctx = data["context_window"]
            ctx_window = ctx.get("context_window_size", "Unknown")
            session_tokens = ctx.get("total_input_tokens", 0) + ctx.get("total_output_tokens", 0)
            if session_tokens == 0 and "current_usage" in ctx:
                session_tokens = ctx["current_usage"].get("input_tokens", 0) + ctx["current_usage"].get("output_tokens", 0)
        elif "context_used_tokens" in data:
            session_tokens = data["context_used_tokens"]
            ctx_window = data.get("context_total_tokens", "Unknown")
        else:
            ctx = health_data.get("context_health", {})
            profile = health_data.get("profile", {})
            ctx_window = profile.get("context_window", "Unknown")
            session_tokens = ctx.get("session_token_count", 0)
            
        # Cost, Model, Effort
        model_name = "Unknown"
        effort_val = ""
        
        # Codex (cx) native extraction from SQLite
        if peer == "cx":
            db_path = SYS_DIR / "codex" / "config" / "state_5.sqlite"
            if db_path.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                    cur = conn.cursor()
                    cur.execute("SELECT model, tokens_used, reasoning_effort FROM threads WHERE tokens_used > 0 ORDER BY updated_at DESC LIMIT 1;")
                    row = cur.fetchone()
                    if row:
                        if row[0]: model_name = str(row[0])
                        if row[1]: session_tokens = int(row[1])
                        if row[2]: effort_val = str(row[2])
                    cur.execute("SELECT SUM(tokens_used) FROM threads;")
                    row_sum = cur.fetchone()
                    if row_sum and row_sum[0]:
                        total_cx_tokens = int(row_sum[0])
                    else:
                        total_cx_tokens = 0
                    conn.close()
                except Exception:
                    total_cx_tokens = 0
                    
        # CC / AG native extraction
        if "model" in data:
            if isinstance(data["model"], dict):
                model_name = data["model"].get("display_name") or data["model"].get("id", "Unknown")
            else:
                model_name = str(data["model"])
        elif "model_name" in data:
            model_name = str(data["model_name"])
            
        if "model_reasoning_effort" in data:
            if isinstance(data["model_reasoning_effort"], dict):
                effort_val = data["model_reasoning_effort"].get("level", "")
            else:
                effort_val = str(data["model_reasoning_effort"])
        elif "effort" in data:
            if isinstance(data["effort"], dict):
                effort_val = data["effort"].get("level", "")
            else:
                effort_val = str(data["effort"])

        if effort_val and effort_val.lower() not in model_name.lower() and effort_val != "null":
            model_name = f"{model_name} ({effort_val})"

        print(f"  - Active Model: {model_name}")
        print(f"  - Context: {session_tokens} / {ctx_window} tokens")
        if peer == "cx" and 'total_cx_tokens' in locals() and total_cx_tokens > 0:
            print(f"  - Total Historical Tokens: {total_cx_tokens:,}")
            
        # Quota
        def format_reset(val, fmt="%Y-%m-%d %H:%M:%S"):
            if not val: return ""
            try:
                if str(val).isdigit():
                    return subprocess.check_output(f'bash -c "date -d \\"@{val}\\" +\\"{fmt}\\""', shell=True).decode().strip()
                else:
                    return subprocess.check_output(f'bash -c "date -d \\"{val}\\" +\\"{fmt}\\""', shell=True).decode().strip()
            except:
                return str(val)

        if "quota" in data:
            q = data["quota"]
            if "gemini-5h" in q:
                rst = format_reset(q['gemini-5h'].get('reset_time'), "%H:%M")
                print(f"  - Gemini 5H Quota: {q['gemini-5h'].get('remaining_fraction', 0)*100:.1f}% Remaining (Resets at {rst})")
            if "gemini-weekly" in q:
                rst = format_reset(q['gemini-weekly'].get('reset_time'), "%m/%d")
                print(f"  - Gemini 7D Quota: {q['gemini-weekly'].get('remaining_fraction', 0)*100:.1f}% Remaining (Resets on {rst})")
            if "3p-5h" in q:
                rst = format_reset(q['3p-5h'].get('reset_time'), "%H:%M")
                print(f"  - Claude(3P) 5H Quota: {q['3p-5h'].get('remaining_fraction', 0)*100:.1f}% Remaining (Resets at {rst})")
            if "3p-weekly" in q:
                rst = format_reset(q['3p-weekly'].get('reset_time'), "%m/%d")
                print(f"  - Claude(3P) 7D Quota: {q['3p-weekly'].get('remaining_fraction', 0)*100:.1f}% Remaining (Resets on {rst})")
                
        if "rate_limits" in data:
            rl = data["rate_limits"]
            if "five_hour" in rl:
                rst = format_reset(rl['five_hour'].get('reset_at') or rl['five_hour'].get('resets_at'), "%H:%M")
                print(f"  - 5H Quota: {rl['five_hour'].get('used_percentage', 0)}% Used (Resets at {rst})")
            if "seven_day" in rl:
                rst = format_reset(rl['seven_day'].get('reset_at') or rl['seven_day'].get('resets_at'), "%m/%d")
                print(f"  - 7D Quota: {rl['seven_day'].get('used_percentage', 0)}% Used (Resets on {rst})")
                
        if "cost" in data:
            print(f"  - Cost USD: ${data['cost'].get('total_cost_usd', 0):.4f}")
            
        # Sessions
        session_h = health_data.get("session_health", {})
        if "session_count_today" in session_h:
            print(f"  - Sessions Today: {session_h.get('session_count_today')}")

    print("\n" + "="*60)
    print("💡 Note: Run '_sys\\cli\\diag.bat' anytime to view this screen.")
    print("="*60)

if __name__ == "__main__":
    main()
