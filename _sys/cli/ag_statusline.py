import json
import subprocess
import sys
from pathlib import Path


CLI_DIR = Path(__file__).resolve().parent
SYS_DIR = CLI_DIR.parent
STATUSLINE_SCRIPT = SYS_DIR / "antigravity" / "config" / "statusline-command.sh"
STDIN_LOG = SYS_DIR / "data" / "temp" / "ag_statusline_stdin.log"
STATUSLINE_TIMEOUT_SEC = 8


def main():
    # Read stdin data passed by Antigravity CLI
    stdin_data = ""
    if not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read()
        except Exception:
            pass

    try:
        STDIN_LOG.parent.mkdir(parents=True, exist_ok=True)
        STDIN_LOG.write_text(stdin_data, encoding="utf-8")
    except OSError:
        pass

    # Pass stdin_data to the portable statusline adapter.
    try:
        result = subprocess.run(
            ["bash", STATUSLINE_SCRIPT.as_posix()],
            input=stdin_data,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
            timeout=STATUSLINE_TIMEOUT_SEC,
        )
        if result.stdout:
            print(result.stdout, end="")
        else:
            # Fallback if bash script fails
            data = json.loads(stdin_data) if stdin_data else {}
            model = data.get("model", "Unknown Model")
            print(f"ag:{model} | (unified script err)")
    except subprocess.TimeoutExpired:
        print("ag:timeout | statusline unavailable", end="")
    except Exception as e:
        print(f"ag:error | {str(e)[:30]}", end="")


if __name__ == "__main__":
    main()
