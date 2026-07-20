import sys
import os
import pytest
from pathlib import Path

# Add _sys/core to path so we can import virtualizer
core_dir = Path(__file__).resolve().parent.parent.parent / "core"
sys.path.insert(0, str(core_dir))

import virtualizer

def test_set_peer_junctions_handles_missing_host_env(tmp_path, monkeypatch):

    """
    Test that virtualizer._set_peer_junctions gracefully handles a peer
    whose host_junction dict lacks a "host_env" key or specifies it as None.
    Prior to the fix, this would raise a TypeError: str expected, not NoneType
    when attempting `None in os.environ`.
    """
    # Setup mock paths
    base_dir = tmp_path / "base"
    sys_dir = tmp_path / "sys"
    base_dir.mkdir()
    sys_dir.mkdir()
    
    # Mock OS environ to ensure it doesn't actually affect the host
    # We will provide a fake USERPROFILE using setenv so os.environ retains its type (os._Environ)
    # which is strictly string-keyed and raises TypeError for None in os.environ
    fake_userprofile = str(tmp_path / "fake_userprofile")
    monkeypatch.setenv("USERPROFILE", fake_userprofile)
    
    # Create the fake userprofile dir
    Path(fake_userprofile).mkdir(parents=True, exist_ok=True)
    
    # Peer config with missing host_env (defaults to None when getting)
    peer_config_missing_env = {
        "host_junction": {
            "host_dirname": ".fake_peer"
            # "host_env" is intentionally missing
        }
    }
    
    peer_config_null_env = {
        "host_junction": {
            "host_dirname": ".fake_peer_null",
            "host_env": None
        }
    }
    
    # Prior to the fix, this call would crash with a TypeError
    try:
        records_1 = virtualizer._set_peer_junctions(base_dir, "fake1", peer_config_missing_env, sys_dir)
        records_2 = virtualizer._set_peer_junctions(base_dir, "fake2", peer_config_null_env, sys_dir)
    except TypeError as e:
        pytest.fail(f"TypeError raised: {e}. The code probably tried `None in os.environ`.")
    
    # If we get here, it didn't crash. 
    # With the fix, they default to USERPROFILE or gracefully skip if None
    # If missing -> defaults to USERPROFILE -> creates junction if host exists (we didn't create host, so it might just fail to create junction but not crash).
    # Wait, the code creates the host_path automatically in _set_peer_junctions if it's missing!
    # Ah, it does: portable_path.mkdir() and _ensure_junction(host_path, portable_path). 
    # Actually, _ensure_junction handles host_path.exists().
    pass
