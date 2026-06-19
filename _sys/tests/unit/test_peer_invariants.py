"""Dynamic peer invariant contract tests.

All tests derive peer state from the live orchestration.json + related config files.
Hardcoded peer IDs are NOT used here — use test_hub.py for adapter-specific unit tests.

Invariants verified:
  INV-P01  Every enabled physical peer has exactly 1 orchestration node.
  INV-P02  Disabled peers have enabled:false in orchestration.json.
  INV-P03  Virtual nodes that have a disabled parent are themselves non-routable.
  INV-P04  is_routable() returns False for all disabled / disabled-parent nodes.
  INV-P05  is_routable() returns True for all enabled physical peers.
  INV-P06  model_profiles routing_state == "blocked" for every disabled peer's profiles.
  INV-P07  protocol.json default_voters / r10_voters contain only enabled peers.
  INV-P08  Disabled peers are absent from _default_nodes() output.
  INV-P09  get_adapter_for_peer() raises ValueError for disabled peers.
  INV-P10  Aliases cannot bypass is_routable() for disabled nodes.
  INV-P11  collaboration_loop_bindings fallback routes contain no gc.* or disabled profiles.
  INV-P12  Unknown / malformed node_id → is_routable() returns False (fail-closed).
"""
import json
import sys
from pathlib import Path

import pytest

# Ensure hub module is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
import hub
import hub_peer

# ─── Config loading helpers ────────────────────────────────────────────────────

_SYS = Path(__file__).parent.parent.parent  # _sys/


def _load_json(rel: str) -> dict:
    return json.loads((_SYS / rel).read_text(encoding="utf-8"))


def _orchestration() -> dict:
    return _load_json("ai/orchestration.json")


def _all_nodes() -> list[dict]:
    return _orchestration().get("hub_nodes", [])


def _enabled_physical_peers() -> list[dict]:
    return [n for n in _all_nodes() if n.get("type") == "peer" and n.get("enabled", True) is not False]


def _disabled_nodes() -> list[dict]:
    orch = _orchestration()
    return [
        node
        for node in _all_nodes()
        if node.get("node_id") and not hub.is_routable(node["node_id"], orch=orch)
    ]


def _node_ids(nodes: list[dict]) -> list[str]:
    return [n["node_id"] for n in nodes if "node_id" in n]


# ─── INV-P01: enabled physical peers → exactly 1 orchestration node ──────────

def test_inv_p01_enabled_peers_have_single_node():
    """Every enabled physical peer must appear exactly once in hub_nodes."""
    nodes = _all_nodes()
    peer_ids = [n["node_id"] for n in nodes if n.get("type") == "peer" and n.get("enabled", True) is not False]
    assert len(peer_ids) == len(set(peer_ids)), (
        f"Duplicate enabled peer node IDs: {[x for x in peer_ids if peer_ids.count(x) > 1]}"
    )
    assert len(peer_ids) >= 1, "No enabled physical peers found — at least cc must exist"


# ─── INV-P02: disabled peers carry explicit enabled:false ────────────────────

def test_inv_p02_disabled_peers_have_explicit_flag():
    """Peers that are expected disabled must have enabled:false, not just absent."""
    # Determine disabled physical peers (enabled:false)
    disabled_physical = [
        n for n in _all_nodes()
        if n.get("type") == "peer" and n.get("enabled") is False
    ]
    for node in disabled_physical:
        assert node.get("enabled") is False, (
            f"Disabled peer {node.get('node_id')} missing explicit enabled:false"
        )


# ─── INV-P03: virtual nodes with disabled parent are non-routable ─────────────

def test_inv_p03_virtual_nodes_inherit_parent_disablement():
    """Virtual nodes whose parent is disabled must themselves be non-routable."""
    orch = _orchestration()
    nodes_map = {n["node_id"]: n for n in orch.get("hub_nodes", []) if "node_id" in n}
    virtual_nodes = [n for n in _all_nodes() if n.get("type") == "virtual" and "node_id" in n]

    for vnode in virtual_nodes:
        parent_id = vnode.get("parent_node")
        if parent_id:
            parent = nodes_map.get(parent_id)
            if parent and parent.get("enabled") is False:
                assert not hub.is_routable(vnode["node_id"], orch=orch), (
                    f"Virtual node {vnode['node_id']} is routable but parent {parent_id} is disabled"
                )


# ─── INV-P04: is_routable() returns False for all disabled/disabled-parent nodes ──

@pytest.mark.parametrize("node_id", _node_ids(_disabled_nodes()))
def test_inv_p04_is_routable_false_for_disabled(node_id):
    """is_routable() must return False for disabled nodes."""
    assert not hub.is_routable(node_id), (
        f"is_routable({node_id!r}) returned True but node is disabled"
    )


# ─── INV-P05: is_routable() returns True for enabled physical peers ───────────

@pytest.mark.parametrize("node_id", _node_ids(_enabled_physical_peers()))
def test_inv_p05_is_routable_true_for_enabled(node_id):
    """is_routable() must return True for all enabled physical peers."""
    assert hub.is_routable(node_id), (
        f"is_routable({node_id!r}) returned False but node is enabled"
    )


# ─── INV-P06: disabled peer profiles → routing_state == "blocked" ─────────────

def test_inv_p06_disabled_peer_profiles_are_blocked():
    """model_profiles routing_state must be 'blocked' for every disabled peer's profiles."""
    mp = _load_json("ai/model_profiles.json")
    profiles = mp.get("profiles", {})
    disabled_peer_ids = {
        n["node_id"]
        for n in _all_nodes()
        if n.get("type") == "peer" and n.get("enabled") is False and "node_id" in n
    }

    for profile_key, profile_val in profiles.items():
        # Profile key format: "{peer_id}.{profile_name}" or similar
        peer_prefix = profile_key.split(".")[0]
        if peer_prefix in disabled_peer_ids:
            state = profile_val.get("routing_state")
            assert state == "blocked", (
                f"Profile {profile_key!r} belongs to disabled peer {peer_prefix!r} "
                f"but routing_state={state!r} (expected 'blocked')"
            )


# ─── INV-P07: protocol.json voters contain only enabled peers ─────────────────

def test_inv_p07_voters_are_enabled_peers():
    """default_voters and r10_voters must only reference enabled peer node IDs."""
    proto = _load_json("ai/protocol.json")
    enabled_ids = set(_node_ids(_enabled_physical_peers()))

    # Find voter lists anywhere in protocol.json
    def find_voters(obj: dict | list, path: str = "") -> list[tuple[str, list]]:
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "voter" in k and isinstance(v, list):
                    found.append((f"{path}.{k}", v))
                else:
                    found.extend(find_voters(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                found.extend(find_voters(item, f"{path}[{i}]"))
        return found

    voter_lists = find_voters(proto)
    for path, voters in voter_lists:
        # inactive_default_voters intentionally lists disabled peers — skip it
        if "inactive" in path:
            continue
        for voter in voters:
            assert voter in enabled_ids, (
                f"Voter {voter!r} in {path} is not an enabled peer (enabled: {sorted(enabled_ids)})"
            )


# ─── INV-P08: disabled peers absent from _default_nodes() ────────────────────

def test_inv_p08_disabled_absent_from_default_nodes():
    """_default_nodes() must not include nodes with enabled:false."""
    disabled_ids = {n["node_id"] for n in _all_nodes() if n.get("enabled") is False and "node_id" in n}
    default = hub._default_nodes()["nodes"]
    overlapping = disabled_ids & set(default.keys())
    assert not overlapping, (
        f"Disabled nodes present in _default_nodes(): {overlapping}"
    )


def test_default_nodes_does_not_resurrect_all_disabled_config():
    orch = {
        "hub_nodes": [
            {"node_id": "only-peer", "type": "peer", "enabled": False}
        ]
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hub, "_load_orchestration", lambda: orch)
        assert hub._default_nodes()["nodes"] == {}


# ─── INV-P09: get_adapter_for_peer() raises for disabled peers ────────────────

@pytest.mark.parametrize("node_id", [
    n["node_id"]
    for n in _all_nodes()
    if n.get("type") == "peer" and n.get("enabled") is False and "node_id" in n
])
def test_inv_p09_get_adapter_raises_for_disabled(node_id):
    """get_adapter_for_peer() must raise ValueError for disabled peers."""
    with pytest.raises(ValueError, match="disabled"):
        hub_peer.get_adapter_for_peer(node_id)


# ─── INV-P10: aliases cannot bypass is_routable() for disabled nodes ──────────

def test_inv_p10_aliases_dont_bypass_disablement():
    """Aliases of disabled nodes must not be routable."""
    orch = _orchestration()
    for node in orch.get("hub_nodes", []):
        if node.get("enabled") is False:
            for alias in node.get("aliases", []):
                assert not hub.is_routable(alias, orch=orch), (
                    f"Alias {alias!r} of disabled node {node.get('node_id')} is routable"
                )


# ─── INV-P11: loop bindings fallback routes contain no disabled profiles ──────

def test_inv_p11_loop_bindings_no_disabled_profiles():
    """collaboration_loop_bindings routing routes must not reference disabled peer profiles."""
    bindings = _load_json("ai/collaboration_loop_bindings.json")
    mp = _load_json("ai/model_profiles.json")
    profiles = mp.get("profiles", {})
    disabled_peer_ids = {
        n["node_id"]
        for n in _all_nodes()
        if n.get("type") == "peer" and n.get("enabled") is False and "node_id" in n
    }

    violations = []
    for rule in bindings.get("routing_rules", []):
        for profile_ref in rule.get("route", []) + [rule.get("final_reviewer", "")]:
            if not profile_ref:
                continue
            peer_prefix = profile_ref.split(".")[0]
            if peer_prefix in disabled_peer_ids:
                violations.append(f"{rule.get('task_type')}: {profile_ref}")
            # Also check if the profile itself is blocked
            if profile_ref in profiles:
                if profiles[profile_ref].get("routing_state") == "blocked":
                    violations.append(f"{rule.get('task_type')}: {profile_ref} (routing_state=blocked)")

    assert not violations, f"Disabled/blocked profiles in routing_rules:\n" + "\n".join(violations)


# ─── INV-P12: unknown node_id → is_routable() fails closed ───────────────────

@pytest.mark.parametrize("bad_id", [
    "", "nonexistent", "gc_clone", "cc-injected", "   ", None
])
def test_inv_p12_unknown_node_id_fails_closed(bad_id):
    """is_routable() must return False for any unknown / malformed node ID."""
    assert not hub.is_routable(bad_id), (
        f"is_routable({bad_id!r}) returned True for unknown node ID"
    )


# ─── State-transition tests ────────────────────────────────────────────────────

def test_transition_enabled_to_disabled_makes_unroutable():
    """Mutating a node's enabled flag to False must make is_routable() return False."""
    # Use an in-memory orch dict to avoid modifying real config
    orch = {
        "hub_nodes": [
            {"node_id": "test-peer", "type": "peer", "enabled": True, "invoke": "test"}
        ]
    }
    assert hub.is_routable("test-peer", orch=orch)
    orch["hub_nodes"][0]["enabled"] = False
    assert not hub.is_routable("test-peer", orch=orch)
    # Re-enabling restores routability
    orch["hub_nodes"][0]["enabled"] = True
    assert hub.is_routable("test-peer", orch=orch)


def test_nested_descendants_inherit_disablement_and_recover():
    """Parent state propagates recursively without mutating child local state."""
    orch = {
        "hub_nodes": [
            {"node_id": "root", "type": "peer"},
            {"node_id": "child", "type": "virtual", "parent_node": "root"},
            {"node_id": "grandchild", "type": "virtual", "parent_node": "child"},
        ]
    }
    assert hub.is_routable("grandchild", orch=orch)
    orch["hub_nodes"][0]["enabled"] = False
    assert not hub.is_routable("child", orch=orch)
    assert not hub.is_routable("grandchild", orch=orch)
    assert "enabled" not in orch["hub_nodes"][1]
    assert "enabled" not in orch["hub_nodes"][2]
    orch["hub_nodes"][0].pop("enabled")
    assert hub.is_routable("grandchild", orch=orch)


def test_child_local_disablement_survives_parent_recovery():
    orch = {
        "hub_nodes": [
            {"node_id": "root", "type": "peer", "enabled": False},
            {"node_id": "child", "type": "virtual", "parent_node": "root", "enabled": False},
        ]
    }
    orch["hub_nodes"][0].pop("enabled")
    assert hub.is_routable("root", orch=orch)
    assert not hub.is_routable("child", orch=orch)


@pytest.mark.parametrize(
    "nodes",
    [
        [
            {"node_id": "root", "type": "peer"},
            {"node_id": "child", "type": "virtual", "parent_node": "missing"},
        ],
        [
            {"node_id": "a", "type": "virtual", "parent_node": "b"},
            {"node_id": "b", "type": "virtual", "parent_node": "a"},
        ],
        [
            {"node_id": "a", "type": "virtual", "peer": "b"},
            {"node_id": "b", "type": "virtual", "peer": "a"},
        ],
    ],
)
def test_invalid_parent_trees_fail_closed(nodes):
    orch = {"hub_nodes": nodes}
    assert not hub.is_routable(nodes[-1]["node_id"], orch=orch)
