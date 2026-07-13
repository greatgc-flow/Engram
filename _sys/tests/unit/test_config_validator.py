import json
import pytest
from pathlib import Path
from _sys.core.config import load_strict
from _sys.checks.check_config import validate_config


def _valid_profiles():
    return {
        "standard": {
            "model_id": "small",
            "routing_state": "eligible",
            "profile_class": "tier",
            "quota_families": ["X"],
        },
        "effort": {
            "model_id": "medium",
            "routing_state": "eligible",
            "profile_class": "tier",
            "quota_families": ["X"],
        },
        "deepthink": {
            "model_id": "large",
            "routing_state": "eligible",
            "profile_class": "tier",
            "quota_families": ["X"],
        },
    }


def _write_config_set(path, *, node, routing=None):
    path.mkdir()
    (path / "protocol.json").write_text("{}")
    (path / "peers.json").write_text('{"peers": {}}')
    (path / "lifecycle_policy.json").write_text("{}")
    (path / "orchestration.json").write_text(json.dumps({"hub_nodes": [node]}))
    (path / "routing-config.json").write_text(json.dumps(routing or {}))

def test_strict_load_raises_on_malformed(tmp_path):
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{ this is not valid json }")
    with pytest.raises(Exception) as excinfo:
        load_strict(malformed)
    assert "strict" in str(excinfo.value).lower() or "malformed" in str(excinfo.value).lower() or "json" in str(excinfo.value).lower()

def test_config_validator_flags_duplicate_keys(tmp_path):
    d = tmp_path / "ai"
    d.mkdir()
    (d / "orchestration.json").write_text("{}")
    (d / "peers.json").write_text('{"peers": {}}')
    (d / "routing-config.json").write_text("{}")
    (d / "lifecycle_policy.json").write_text("{}")
    protocol = d / "protocol.json"
    protocol.write_text('{"test_key": 1, "test_key": 2}')
    
    assert not validate_config(d)

def test_config_validator_flags_invalid_profile_ref(tmp_path):
    d = tmp_path / "ai"
    d.mkdir()
    (d / "protocol.json").write_text("{}")
    (d / "peers.json").write_text('{"peers": {}}')
    (d / "lifecycle_policy.json").write_text("{}")
    
    (d / "orchestration.json").write_text(json.dumps({
        "hub_nodes": [{
            "node_id": "xx",
            "type": "peer",
            "profiles": _valid_profiles(),
        }]
    }))
    
    (d / "routing-config.json").write_text(json.dumps({
        "routing_weights": {
            "R01": {
                "primary": "xx::nonexistent::a::b"
            }
        }
    }))
    
    assert not validate_config(d)

    # Make it NON-VACUOUS: a VALID target must not be flagged
    (d / "routing-config.json").write_text(json.dumps({
        "routing_weights": {
            "R01": {
                "primary": "xx::standard::a::b"
            }
        }
    }))
    
    assert validate_config(d)

def test_config_validator_accepts_model_id_targets(tmp_path):
    d = tmp_path / "ai"
    d.mkdir()
    (d / "protocol.json").write_text("{}")
    (d / "peers.json").write_text('{"peers": {}}')
    (d / "lifecycle_policy.json").write_text("{}")
    
    (d / "orchestration.json").write_text(json.dumps({
        "hub_nodes": [{
            "node_id": "cc",
            "type": "peer",
            "profiles": {
                **_valid_profiles(),
                "standard": {
                    **_valid_profiles()["standard"],
                    "model_id": "claude-opus-4-8",
                },
            },
        }]
    }))
    
    (d / "routing-config.json").write_text(json.dumps({
        "routing_weights": {
            "R01": {
                "primary": "cc::claude-opus-4-8::max::none"
            }
        }
    }))
    
    assert validate_config(d)

def test_config_validator_flags_malformed_peers_node_ids(tmp_path):
    d = tmp_path / "ai"
    d.mkdir()
    (d / "protocol.json").write_text("{}")
    (d / "lifecycle_policy.json").write_text("{}")
    (d / "orchestration.json").write_text("{}")
    (d / "routing-config.json").write_text("{}")
    
    (d / "peers.json").write_text(json.dumps({
        "peers": {
            "p1": {
                "node_ids": "not-a-list"
            }
        }
    }))
    
    assert not validate_config(d)

def test_config_validator_flags_voter_overlap(tmp_path):
    d = tmp_path / "ai"
    d.mkdir()
    (d / "protocol.json").write_text("{}")
    (d / "peers.json").write_text('{"peers": {"cc": {}, "ag": {}, "cx": {}}}')
    (d / "lifecycle_policy.json").write_text("{}")
    (d / "routing-config.json").write_text('{}')
    
    (d / "orchestration.json").write_text(json.dumps({
        "consensus": {
            "r10_voters": ["cc", "ag"],
            "inactive_default_voters": ["ag", "cx"]
        }
    }))
    assert not validate_config(d)

def test_config_validator_passes_current_tree():
    sys_dir = Path(__file__).parent.parent.parent
    ai_dir = sys_dir / "ai"
    assert validate_config(ai_dir)


@pytest.mark.parametrize(
    ("mutate", "enabled"),
    [
        (lambda p: p["standard"].pop("profile_class"), True),
        (lambda p: p["standard"].update(profile_class="invalid"), True),
        (lambda p: p["standard"].update(profile_class="specialty"), True),
        (lambda p: p.update(foo={
            "profile_class": "tier", "quota_families": ["X"], "routing_state": "eligible"
        }), True),
        (lambda p: p["standard"].pop("quota_families"), True),
        (lambda p: p["standard"].update(quota_families=["BAD"]), True),
        (lambda p: p.pop("deepthink"), True),
        (lambda p: p["standard"].pop("profile_class"), False),
    ],
)
def test_profile_policy_validator_rejects_invalid_contracts(tmp_path, mutate, enabled):
    profiles = _valid_profiles()
    mutate(profiles)
    node = {"node_id": "xx", "type": "peer", "enabled": enabled, "profiles": profiles}
    _write_config_set(tmp_path / "ai", node=node)
    assert not validate_config(tmp_path / "ai")


def test_profile_policy_validator_allows_disabled_empty_quota_families(tmp_path):
    profiles = _valid_profiles()
    for profile in profiles.values():
        profile.pop("quota_families")
        profile["routing_state"] = "blocked"
    node = {"node_id": "xx", "type": "peer", "enabled": False, "profiles": profiles}
    _write_config_set(tmp_path / "ai", node=node)
    assert validate_config(tmp_path / "ai")


def test_shared_family_reserve_invariant_rejects_unreserved_protected_profile(tmp_path):
    profiles = _valid_profiles()
    profiles["special"] = {
        "profile_class": "specialty",
        "quota_families": ["X"],
        "routing_state": "manual_only",
    }
    node = {"node_id": "xx", "type": "peer", "enabled": True, "profiles": profiles}
    routing = {
        "token_load_balancing": {
            "arbiter_models": [],
            "bulk_exclude_profiles": [],
            "shared_quota_reserve": {"enabled": True, "families": {}},
        }
    }
    _write_config_set(tmp_path / "ai", node=node, routing=routing)
    assert not validate_config(tmp_path / "ai")

    routing["token_load_balancing"]["shared_quota_reserve"]["families"] = {
        "X": {"reserve_for": ["xx.special"], "reserve_fraction": 0.2}
    }
    (tmp_path / "ai" / "routing-config.json").write_text(json.dumps(routing))
    assert validate_config(tmp_path / "ai")


def test_specialty_bulk_profile_does_not_require_reserve_by_class_alone(tmp_path):
    profiles = _valid_profiles()
    profiles["bulk"] = {
        "profile_class": "specialty",
        "quota_families": ["X"],
        "routing_state": "eligible",
    }
    node = {"node_id": "xx", "type": "peer", "enabled": True, "profiles": profiles}
    _write_config_set(tmp_path / "ai", node=node)
    assert validate_config(tmp_path / "ai")
