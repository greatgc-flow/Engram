import sys
from pathlib import Path
from unittest.mock import patch

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS / "cli"))
import peer_mgr


def test_add_without_safe_template_fails_before_writes(capsys):
    orch = {"hub_nodes": []}
    peers = {"peers": {"vendor": {"enabled": False, "node_ids": []}}}

    def load(path):
        if path == peer_mgr._ORCH:
            return orch
        if path == peer_mgr._PEERS:
            return peers
        return {}

    with patch.object(peer_mgr, "_load", side_effect=load), \
         patch.object(peer_mgr, "_save") as save:
        result = peer_mgr.cmd_add(
            "new-peer", "vendor-cli", None, False, provider="vendor"
        )

    assert result == 1
    assert "no safe orchestration template" in capsys.readouterr().err
    save.assert_not_called()
