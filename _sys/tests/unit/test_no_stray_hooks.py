import json
from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parents[2]

def test_no_pretooluse_hook_registration():
    """Ensure _sys/claude/project/settings.json has no PreToolUse hook registration."""
    settings_path = _SYS_DIR / "claude" / "project" / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        if "customCommands" in data:
            for cmd in data["customCommands"]:
                assert "PreToolUse" not in cmd.get("name", ""), "PreToolUse hook registration found in settings.json"

def test_hooks_directory_absent():
    """Ensure _sys/hooks directory does not exist."""
    hooks_dir = _SYS_DIR / "hooks"
    assert not hooks_dir.exists(), "The _sys/hooks directory must not exist (removed in Increment A)"
