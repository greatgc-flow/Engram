"""_console_helpers.py — small shared helpers for the peer entry-point scripts.

Extracted from claude_entry.py/codex_entry.py/agy_entry.py, which each
carried a byte-for-byte duplicate of _set_title(). Kept separate from
console_runner.py deliberately: title-setting and env-var resolution are
entry-point/UI/config setup, not session lifecycle/lease/spawn/health
bookkeeping.
"""
import json
from pathlib import Path


def load_peer_env_vars(sys_dir: Path, peer_key: str) -> dict[str, str]:
    """Resolve a peer's declared peers.json env_vars to real paths.

    Each declared value is a subdirectory name under _sys/<peer_key>/,
    e.g. {"CODEX_HOME": "config"} -> {"CODEX_HOME": "<sys_dir>/codex/config"}.
    Missing/malformed peers.json or an unknown peer_key yields {} rather
    than raising -- entry points should keep working with just PATH/UTF8
    env if config resolution fails for any reason.
    """
    peers_path = sys_dir / "ai" / "peers.json"
    try:
        peers = json.loads(peers_path.read_text(encoding="utf-8"))
        cfg = peers.get("peers", peers).get(peer_key, {})
        result = {}
        for key, subdir in cfg.get("env_vars", {}).items():
            resolved = sys_dir / peer_key / str(subdir)
            if resolved.exists():
                result[key] = str(resolved)
        return result
    except Exception:
        return {}


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
