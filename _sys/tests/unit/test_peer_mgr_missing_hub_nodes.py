import sys
from pathlib import Path
from unittest.mock import patch

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS / "cli"))
import peer_mgr


def _load_returning(orch):
    def load(path):
        if path == peer_mgr._ORCH:
            return orch
        return {}
    return load


def test_suspend_reports_error_when_hub_nodes_missing(capsys):
    with patch.object(peer_mgr, "_load", side_effect=_load_returning({})), \
         patch.object(peer_mgr, "_save") as save:
        result = peer_mgr.cmd_suspend("some-peer", "", False)

    assert result == 1
    assert "hub_nodes" in capsys.readouterr().err
    save.assert_not_called()


def test_status_reports_error_when_hub_nodes_missing(capsys):
    with patch.object(peer_mgr, "_load", side_effect=_load_returning({})):
        result = peer_mgr.cmd_status()

    assert result == 1
    assert "hub_nodes" in capsys.readouterr().err
