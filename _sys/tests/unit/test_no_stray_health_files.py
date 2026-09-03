"""Phase A guard — no stray per-node health.json mirrors.

A peer's health lives at `_sys/<sys_subdir>/health.json` (the canonical dir from
peers.json). A file at `_sys/<node_id>/health.json` where `node_id != sys_subdir`
is a stale mirror — the exact hallucination trap that made a terminal read a
suspended peer as alive (see ops/terminal-health-misread-consensus-2026-06-25.md).

As of Increment D of the Engram Diet Plan, the provider directories themselves
(_sys/claude, _sys/codex, _sys/antigravity) have been entirely removed in favor
of the unified peerhub repo. This test now verifies that these top-level provider
directories do not exist, ensuring no stray health files (or anything else) can
accidentally respawn in them.
"""
from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parents[2]


def test_provider_directories_absent():
    """Ensure _sys/claude, _sys/codex, _sys/antigravity are completely gone."""
    for provider in ["claude", "codex", "antigravity"]:
        provider_dir = _SYS_DIR / provider
        assert not provider_dir.exists(), (
            f"Provider directory {provider_dir} should not exist. "
            f"All AI governance is now handled by the peerhub repository."
        )
