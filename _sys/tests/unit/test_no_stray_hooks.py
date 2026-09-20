from pathlib import Path
from _sys.core.root import find_root

_SYS_DIR = find_root(__file__)


def test_hooks_directory_absent():
    """Ensure _sys/hooks directory does not exist."""
    hooks_dir = _SYS_DIR / "hooks"
    assert not hooks_dir.exists(), "The _sys/hooks directory must not exist (removed in Increment A)"
