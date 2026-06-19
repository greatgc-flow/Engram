"""Tests for active-peer routing used by legacy AI-assisted checks."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "checks"))
import _common


def _write_peer_config(sys_dir: Path, *, ag_enabled: bool = True) -> None:
    (sys_dir / "ai").mkdir(parents=True)
    (sys_dir / "antigravity").mkdir()
    (sys_dir / "ai" / "orchestration.json").write_text(
        json.dumps(
            {
                "hub_nodes": [
                    {"node_id": "ag", "type": "peer", "enabled": ag_enabled}
                ]
            }
        ),
        encoding="utf-8",
    )
    (sys_dir / "ai" / "peers.json").write_text(
        json.dumps(
            {
                "peers": {
                    "antigravity": {
                        "enabled": True,
                        "node_ids": ["ag"],
                        "sys_subdir": "antigravity",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (sys_dir / "antigravity" / "health.json").write_text(
        json.dumps(
            {
                "context_health": {"status": "GREEN"},
                "availability": {"gate_open": True, "authenticated": True},
            }
        ),
        encoding="utf-8",
    )


def test_active_ai_peer_uses_enabled_healthy_orchestration_node(tmp_path, monkeypatch):
    _write_peer_config(tmp_path)
    monkeypatch.setattr(_common, "_SYS_DIR", tmp_path)
    assert _common._active_ai_peer() == "ag"
    assert _common.ai_available()


def test_active_ai_peer_rejects_disabled_node(tmp_path, monkeypatch):
    _write_peer_config(tmp_path, ag_enabled=False)
    monkeypatch.setattr(_common, "_SYS_DIR", tmp_path)
    assert _common._active_ai_peer() is None
    assert not _common.ai_available()


def test_legacy_gemini_call_routes_through_hub(tmp_path, monkeypatch):
    (tmp_path / "core").mkdir(parents=True)
    monkeypatch.setattr(_common, "_SYS_DIR", tmp_path)
    monkeypatch.setattr(_common, "_active_ai_peer", lambda: "ag")
    completed = subprocess.CompletedProcess(
        args=["hub.py", "ask"], returncode=0, stdout="{}", stderr=""
    )
    with patch("_common.subprocess.run", return_value=completed) as run:
        result = _common.gemini_call("review", stdin="payload", timeout=30)
    assert result.returncode == 0
    command = run.call_args.args[0]
    assert command[2:5] == ["ask", "--to", "ag"]
    assert "--quiet" in command
    assert "--session-policy" in command


def test_legacy_gemini_call_converts_timeout_to_completed_process(tmp_path, monkeypatch):
    (tmp_path / "core").mkdir(parents=True)
    monkeypatch.setattr(_common, "_SYS_DIR", tmp_path)
    monkeypatch.setattr(_common, "_active_ai_peer", lambda: "ag")
    with patch(
        "_common.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["hub.py"], timeout=60),
    ):
        result = _common.gemini_call("review", timeout=30)
    assert result.returncode == 124
    assert "timed out" in result.stderr
