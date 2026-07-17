import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub
import pytest

def test_session_policy_auto_matches_node_capability():
    # 'auto' means use whatever the node natively supports
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    node_without = {"node_id": "test", "session_mode": "none"}
    
    assert hub._session_reuse_enabled(node_with_reuse, "auto") is True
    assert hub._session_reuse_enabled(node_without, "auto") is False

def test_session_policy_fresh_or_none_always_disables():
    # 'fresh' or 'none' overrides a capable node
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    
    assert hub._session_reuse_enabled(node_with_reuse, "fresh") is False
    assert hub._session_reuse_enabled(node_with_reuse, "none") is False

def test_session_policy_reuse_enforces_capability():
    # 'reuse' works if the node has it
    node_with_reuse = {"node_id": "test", "session_mode": "reuse"}
    assert hub._session_reuse_enabled(node_with_reuse, "reuse") is True
    
    # 'reuse' raises if the node lacks capability
    node_without = {"node_id": "test", "session_mode": "none"}
    with pytest.raises(ValueError, match="no configured session-reuse capability"):
        hub._session_reuse_enabled(node_without, "reuse")

