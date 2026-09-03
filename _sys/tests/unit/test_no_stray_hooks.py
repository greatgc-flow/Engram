from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parents[2]


def test_hooks_directory_absent():
    """Ensure _sys/hooks directory does not exist."""
    hooks_dir = _SYS_DIR / "hooks"
    assert not hooks_dir.exists(), "The _sys/hooks directory must not exist (removed in Increment A)"
