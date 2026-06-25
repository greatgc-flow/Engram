"""Phase A guard — no stray per-node health.json mirrors.

A peer's health lives at `_sys/<sys_subdir>/health.json` (the canonical dir from
peers.json). A file at `_sys/<node_id>/health.json` where `node_id != sys_subdir`
is a stale mirror — the exact hallucination trap that made a terminal read a
suspended peer as alive (see ops/terminal-health-misread-consensus-2026-06-25.md).
This locks the cleaned state: such strays must not exist. The naming-split writer
bug that recreates them is fixed in Phase B.
"""
import json
from pathlib import Path

import pytest

_SYS_DIR = Path(__file__).resolve().parents[2]
_PEERS = _SYS_DIR / "ai" / "peers.json"


def _node_to_sys_subdir() -> dict[str, str]:
    data = json.loads(_PEERS.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for peer in data.get("peers", {}).values():
        if not isinstance(peer, dict):
            continue
        sub = peer.get("sys_subdir")
        for node_id in peer.get("node_ids", []):
            if sub:
                mapping[node_id] = sub
    return mapping


def test_no_stray_node_id_health_files():
    """No `_sys/<node_id>/health.json` may exist when node_id != its sys_subdir."""
    strays = [
        node_id
        for node_id, sub in _node_to_sys_subdir().items()
        if node_id != sub and (_SYS_DIR / node_id / "health.json").exists()
    ]
    assert not strays, (
        f"Stale per-node health mirrors found: {sorted(strays)} "
        f"(canonical health lives at _sys/<sys_subdir>/health.json — run hub.py peer-status, "
        f"not raw reads). Delete these mirrors."
    )
