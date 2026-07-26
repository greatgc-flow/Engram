"""Explicit, root-peer quota capability lookup.

Capabilities are configuration facts, not telemetry inferences.  A missing
field therefore means "unsupported/undeclared", even when a transient frame
happens to contain similarly named data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import hub_peer
except ImportError:
    import hub_peer


_ORCHESTRATION_PATH = Path(__file__).resolve().parent.parent / "ai" / "orchestration.json"


def _load_orchestration() -> dict[str, Any]:
    try:
        return json.loads(_ORCHESTRATION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def root_quota_capability(
    peer_id: str,
    capability: str,
    *,
    orchestration: dict[str, Any] | None = None,
) -> bool:
    """Return one explicitly declared capability from the canonical root peer."""
    orch = orchestration if orchestration is not None else _load_orchestration()
    canonical = hub_peer.resolve_node_id(str(peer_id or ""), orch=orch)
    if canonical is None:
        return False
    root_id = hub_peer.root_peer_id(canonical, orch=orch)
    if root_id is None:
        return False
    nodes = {
        node.get("node_id"): node
        for node in orch.get("hub_nodes", [])
        if isinstance(node, dict) and node.get("node_id")
    }
    root = nodes.get(root_id)
    if not isinstance(root, dict) or root.get("type") != "peer":
        return False
    capabilities = root.get("quota_capabilities")
    return (
        isinstance(capabilities, dict)
        and capabilities.get(capability) is True
    )


def supports_reset_credits(
    peer_id: str,
    *,
    orchestration: dict[str, Any] | None = None,
) -> bool:
    return root_quota_capability(
        peer_id,
        "reset_credits",
        orchestration=orchestration,
    )
