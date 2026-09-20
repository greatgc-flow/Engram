"""_sys/core/root.py -- Canonical root self-location and package bootstrap for Engram.

Reference: docs/design/engram-sys-folder-rename-feasibility-2026-09-17.md
(ratified under DIR-006, 2026-09-19).

Provides:
  - bootstrap_root_package: Registers an arbitrary on-disk directory under the
    stable '_sys' namespace in sys.modules (Addendum 2).
  - find_root / find_sys_root: Resolves the physical path of the _sys directory (Addendum 1).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

# Canonical reference locations derived from this file (_sys/core/root.py)
_CORE_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CORE_DIR.parent


def bootstrap_root_package(actual_root: Path, stable_name: str = "_sys") -> None:
    """Register actual_root in sys.modules under stable_name (PEP 420 namespace package).

    Reference: Addendum 2 of docs/design/engram-sys-folder-rename-feasibility-2026-09-17.md.
    _sys has no __init__.py (implicit namespace package) -- a plain spec_from_file_location()
    would raise FileNotFoundError looking for one. Build the ModuleSpec directly instead,
    exactly like Python's own PEP 420 namespace-package machinery does internally.
    """
    if stable_name in sys.modules:
        return
    spec = importlib.machinery.ModuleSpec(stable_name, None, is_package=True)
    spec.submodule_search_locations = [str(actual_root)]
    module = importlib.util.module_from_spec(spec)
    sys.modules[stable_name] = module


def find_root(start_file: str | Path | None = None) -> Path:
    """Find and return the physical _sys directory Path.

    Reference: docs/design/engram-sys-folder-rename-feasibility-2026-09-17.md (Addendum 1 & 2).
    If start_file is provided, locates the containing _sys root by searching upward
    from start_file until the directory containing 'core/root.py' or named '_sys' is found.
    If omitted, returns the canonical _sys directory containing this module.
    """
    if start_file is None:
        return _SYS_DIR
    p = Path(start_file).resolve()
    curr = p.parent if p.is_file() else p
    for parent in [curr] + list(curr.parents):
        if (parent / "core" / "root.py").is_file():
            return parent
        if parent.name == "_sys":
            return parent
    return _SYS_DIR


find_sys_root = find_root
