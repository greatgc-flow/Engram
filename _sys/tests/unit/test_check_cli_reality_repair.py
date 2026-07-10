"""Tests for check_cli_reality.py's D10 --repair-missing pre-flight check.

reconcile_peer()'s "drift" list never contains ABSENT verdicts (DIR-004:
unmeasured != drift), and a genuinely missing binary makes real_binary()
raise rather than appear in a report. _repair_missing_peers() does its own
existence pre-flight instead of trusting the drift report for this.
"""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "checks"))
sys.path.insert(0, str(SYS_DIR / "core"))
import check_cli_reality as ccr  # noqa: E402
import provisioner  # noqa: E402


def test_repair_missing_peers_installs_absent_binary(monkeypatch, tmp_path):
    missing_path = tmp_path / "nonexistent_dir" / "codex.cmd"
    orch = {"hub_nodes": [
        {"type": "peer", "node_id": "cx", "invoke": str(missing_path), "enabled": True},
    ]}

    calls = []
    monkeypatch.setattr(provisioner, "ensure_peer_cli", lambda peer, **kw: calls.append(peer) or {"status": "success"})

    result = ccr._repair_missing_peers(orch)

    assert calls == ["codex"]
    assert result == {"cx": {"status": "success"}}


def test_repair_missing_peers_skips_existing_binary(monkeypatch, tmp_path):
    existing = tmp_path / "claude.cmd"
    existing.write_text("", encoding="utf-8")
    orch = {"hub_nodes": [
        {"type": "peer", "node_id": "cc", "invoke": str(existing), "enabled": True},
    ]}

    calls = []
    monkeypatch.setattr(provisioner, "ensure_peer_cli", lambda peer, **kw: calls.append(peer) or {"status": "success"})

    result = ccr._repair_missing_peers(orch)

    assert calls == []
    assert result == {}


def test_repair_missing_peers_maps_node_id_to_peers_json_key(monkeypatch):
    orch = {"hub_nodes": [
        {"type": "peer", "node_id": "ag", "invoke": "definitely-not-a-real-command-xyz", "enabled": True},
    ]}

    calls = []
    monkeypatch.setattr(provisioner, "ensure_peer_cli", lambda peer, **kw: calls.append(peer) or {"status": "success"})

    ccr._repair_missing_peers(orch)

    assert calls == ["antigravity"]


def test_repair_missing_peers_ignores_disabled_peers(monkeypatch, tmp_path):
    orch = {"hub_nodes": [
        {"type": "peer", "node_id": "cc", "invoke": str(tmp_path / "missing.cmd"), "enabled": False},
    ]}

    calls = []
    monkeypatch.setattr(provisioner, "ensure_peer_cli", lambda peer, **kw: calls.append(peer) or {"status": "success"})

    result = ccr._repair_missing_peers(orch)

    assert calls == []
    assert result == {}
