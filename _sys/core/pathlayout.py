"""Path layout — a frozen, additive view of where things live.

Engram refactor blueprint (_sys/docs-v2/ops/engram-refactor-blueprint-2026-07-20.md),
section 1 item 4: the one reversible architectural beachhead kept from the
shelved design. Deliberately minimal — wraps hub.find_ai_root()'s result
rather than reimplementing its (fragile, well-tested) discovery algorithm.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathLayout:
    install_root: Path
    sys_root: Path
    project_root: Path
    ai_root: Path


def resolve_path_layout(ai_root_override: Path | None = None) -> PathLayout:
    """Resolve install_root/sys_root/project_root from this file's own
    location (mirrors hub.find_ai_root()'s canonical_root computation), and
    ai_root either from ai_root_override or by delegating to
    hub.find_ai_root() — never reimplemented here."""
    install_root = Path(__file__).resolve().parents[2]
    sys_root = install_root / "_sys"
    project_root = install_root

    if ai_root_override is not None:
        ai_root = Path(ai_root_override).resolve()
    else:
        import sys as _sys
        core_dir = str(Path(__file__).resolve().parent)
        if core_dir not in _sys.path:
            _sys.path.insert(0, core_dir)
        import hub
        ai_root = hub.find_ai_root()

    return PathLayout(
        install_root=install_root,
        sys_root=sys_root,
        project_root=project_root,
        ai_root=ai_root,
    )
