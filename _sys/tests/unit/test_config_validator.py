import json
import pytest
from pathlib import Path
from _sys.core.config import load_strict
from _sys.checks.check_config import validate_config

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
            "profiles": {
                "standard": {
                    "model_id": "real-model-id"
                }
            }
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
                "standard": {
                    "model_id": "claude-opus-4-8"
                }
            }
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
