"""_console_helpers.py — small shared helpers for the peer entry-point scripts.

Extracted from claude_entry.py/codex_entry.py/agy_entry.py, which each
carried a byte-for-byte duplicate of _set_title(). Kept separate from
console_runner.py deliberately: title-setting is entry-point/UI setup,
not session lifecycle/lease/spawn/health bookkeeping.
"""
from pathlib import Path


def set_console_title(portable_root: Path, peer: str) -> None:
    """Set the console window title to "[room_id] peer", best-effort."""
    try:
        import json
        import ctypes
        state_file = portable_root / ".ai" / "state.json"
        room_id = ""
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            room_id = data.get("room_id", "")
        title = f"[{room_id}] {peer}" if room_id else peer
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        pass
