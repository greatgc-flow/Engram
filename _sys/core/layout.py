"""
_sys/core/layout.py - Layout constants for Engram installs.
"""
from pathlib import Path
import sys

_CORE_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CORE_DIR.parent
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from root import bootstrap_root_package, find_root  # noqa: E402
bootstrap_root_package(_SYS_DIR)

INSTALL_ROOT_ENTRIES = {
    "Engram.exe",
    "engram.cmd",
    "README.md",
    "LICENSE",
    find_root().name,
    "workspace",
    ".engram",
}
