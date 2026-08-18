import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
SYS_DIR = CLI_DIR.parent
STDIN_LOG = SYS_DIR / "data" / "temp" / "ag_statusline_stdin.log"


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

    try:
        from peerhub.telemetry.statusline import format_statusline_ag
        print(format_statusline_ag(stdin_data), end="")
    except Exception:
        print("ag:Gemini | ctx:ok | hub:idle [room-efde]", end="")

    sys.exit(0)


if __name__ == "__main__":
    main()
