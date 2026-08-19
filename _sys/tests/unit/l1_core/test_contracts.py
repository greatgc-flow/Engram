"""Engram product-boundary contracts (L1 core gate).

This is the fast, deterministic gate run by `check_contracts.py` on every
`_sys/` write. It replaced the previous hub.py API-signature contracts when
Engram and peerhub were separated: Engram is a portable Windows AI
development environment, and all peer/profile communication and
coordination belongs to the separately-installed `peerhub` package.

These contracts fail closed if the legacy coordination layer starts
creeping back into Engram's tracked source.
"""
from __future__ import annotations

import re
from pathlib import Path

# .../_sys/tests/unit/l1_core/test_contracts.py -> parents[3] == _sys
_SYS_DIR = Path(__file__).resolve().parents[3]
_PORTABLE_ROOT = _SYS_DIR.parent

# Modules deleted in the Engram/peerhub separation. None may come back into
# Engram: peerhub owns dispatch, sessions, health, quota, and consensus.
_REMOVED_MODULES = (
    "hub.py", "hub_peer.py", "hub_context.py", "hub_error.py",
    "hub_health.py", "hub_logging.py", "hub_interceptor.py",
    "hub_profile_router.py", "operational_guard_matrix.py",
    "snapshot.py", "quota.py", "quota_capabilities.py",
)

_SOURCE_DIRS = ("core", "cli", "checks", "hooks")

# Vendor/user data and generated caches are not Engram source: peer CLIs keep
# their own conversation/scratch state under _sys/antigravity, _sys/codex,
# etc., which legitimately contains copied text about the old system.
_EXCLUDED_PARTS = (
    "__pycache__", "antigravity", "codex", "claude", "gemini",
    "data", "env", "tools", "docs", "tests",
)


def _engram_source_files() -> list[Path]:
    files: list[Path] = []
    for sub in _SOURCE_DIRS:
        root = _SYS_DIR / sub
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in _EXCLUDED_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


def test_removed_coordination_modules_are_absent() -> None:
    """The legacy hub/diag coordination cluster must not exist in _sys/core."""
    present = [n for n in _REMOVED_MODULES if (_SYS_DIR / "core" / n).exists()]
    assert present == [], (
        f"Legacy peer-coordination modules reappeared in _sys/core: {present}. "
        "peerhub owns coordination; Engram owns the environment."
    )


def test_no_engram_source_imports_a_removed_module() -> None:
    """No tracked Engram source may import the removed coordination modules."""
    removed_names = {n[:-3] for n in _REMOVED_MODULES}
    import_re = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)", re.M)

    violations: list[str] = []
    for path in _engram_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for module in import_re.findall(text):
            parts = module.split(".")
            if parts[0] in removed_names or parts[-1] in removed_names:
                violations.append(f"{path.relative_to(_PORTABLE_ROOT)}: imports '{module}'")
    assert violations == [], (
        "Engram source imports a removed coordination module:\n  " + "\n  ".join(violations)
    )


def test_no_engram_source_shells_out_to_hub_py() -> None:
    """No tracked Engram source may invoke the deleted hub.py / msg.bat."""
    violations: list[str] = []
    for path in _engram_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "hub.py" in stripped or "msg.bat" in stripped:
                violations.append(f"{path.relative_to(_PORTABLE_ROOT)}:{lineno}: {stripped}")
    assert violations == [], (
        "Engram source still invokes the deleted hub CLI:\n  " + "\n  ".join(violations)
    )


def test_interactive_console_launchers_still_exist() -> None:
    """Launching a vendor AI CLI interactively stays an Engram feature."""
    cli = _SYS_DIR / "cli"
    for name in ("console_runner.py", "peer_console.py",
                 "claude_entry.py", "codex_entry.py", "agy_entry.py"):
        assert (cli / name).exists(), f"missing interactive launcher component: {name}"


def test_console_runner_is_a_pure_process_wrapper() -> None:
    """console_runner must not carry peer session/health/lease lifecycle."""
    text = (_SYS_DIR / "cli" / "console_runner.py").read_text(encoding="utf-8")
    for forbidden in ("init-session", "health-update", "terminal-handoff",
                      "terminal-heartbeat", "terminal-close", "context-fill"):
        assert forbidden not in text, (
            f"console_runner.py still performs peer lifecycle action '{forbidden}'; "
            "that belongs to peerhub."
        )


def test_environment_lifecycle_core_is_intact() -> None:
    """The portable-environment lifecycle modules Engram owns must remain."""
    core = _SYS_DIR / "core"
    for name in ("provisioner.py", "dispatcher.py", "virtualizer.py",
                 "registrar.py", "updater.py", "doctor.py", "scrubber.py"):
        assert (core / name).exists(), f"missing Engram lifecycle module: {name}"


def test_runtime_catalog_is_present() -> None:
    """Engram's installed-runtime catalog is environment scope and must stay."""
    assert (_SYS_DIR / "runtimes.json").exists(), "missing runtime catalog: runtimes.json"
