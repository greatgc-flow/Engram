"""Regression coverage for 3 bookkeeping gaps found 2026-08-05 (cx.deepthink
diagnosis, ag.deepthink R:10 review): plain "timeout" wasn't profile-scoped,
composite-peer expired leases silently dropped, and cli_version had no writer.
"""
from pathlib import Path
import json
import sys

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "core"))

import hub  # noqa: E402


def test_provider_timeout_text_is_classified_transient_and_profile_scoped():
    """'Error: timeout waiting for response' (the real ag CLI text) must
    classify as the transient 'timeout' reason, not fall through to the
    peer-wide default."""
    reason, _extra = hub._classify_ask_failure(
        "Error: timeout waiting for response"
    )
    assert reason == "timeout"
    assert reason in hub._TRANSIENT_REASONS


def test_print_timeout_flag_help_is_not_classified_as_timeout():
    """A bare 'timeout' substring match previously misclassified unrelated
    CLI help text (e.g. an invalid --print-timeout flag error) as a real
    timeout, polluting the quarantine failure count."""
    reason, _extra = hub._classify_ask_failure(
        "unrecognized argument: --print-timeout\nusage: agy [--help] ..."
    )
    assert reason != "timeout"


def test_record_ask_failure_routes_timeout_to_profile_not_root(tmp_path, monkeypatch):
    health_dir = tmp_path / "health"
    monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: health_dir)

    orchestration = {
        "hub_nodes": [{"node_id": "ag", "type": "peer", "enabled": True}]
    }
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orchestration)

    hub._record_ask_failure(
        "ag", "timeout", "Error: timeout waiting for response",
        32, ai_root=tmp_path, profile_key="effort",
    )

    _, data = hub._read_peer_health("ag", health_dir)
    profile = data["availability"]["profiles"]["effort"]
    assert profile["last_failure_reason"] == "timeout"
    # Root-level failure bookkeeping must stay untouched by a profile-scoped
    # failure -- this is the exact gap that let stale July data hide a real
    # August failure.
    assert data["session_health"].get("last_failure_reason") is None


def test_lease_sweep_resolves_composite_peer_id_and_backfills_history(
    tmp_path, monkeypatch
):
    """Before the fix: _lease_sweep passed the composite lease peer_id
    ("ag.deepthink") straight to _record_ask_failure, which only recognizes
    enabled ROOT peers and silently no-ops for anything else -- the failure
    reached neither availability.profiles.* nor ask_history."""
    ai_root = tmp_path / ".ai"
    (ai_root / ".lock").mkdir(parents=True)
    (ai_root / "state.json").write_text(json.dumps({"room_id": "r"}), encoding="utf-8")
    (ai_root / "leases.json").write_text("{}", encoding="utf-8")

    health_dir = tmp_path / "health"
    monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: health_dir)

    orchestration = {
        "hub_nodes": [{"node_id": "ag", "type": "peer", "enabled": True}]
    }
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orchestration)
    monkeypatch.setattr(hub.hub_peer, "root_peer_id", lambda node_id, orch=None: "ag")
    monkeypatch.setattr(hub, "_kill_process_tree", lambda pid: None)

    lease_id = hub._lease_open(
        ai_root, "ag.deepthink", 999999, 1, ask_id="ask-x", ask_query_file="q.txt",
    )
    # Force it into the past so the sweep treats it as expired.
    leases = json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))
    leases[lease_id]["expires_at"] = "2020-01-01T00:00:00"
    (ai_root / "leases.json").write_text(json.dumps(leases), encoding="utf-8")

    history_calls = []
    monkeypatch.setattr(
        hub,
        "_append_ask_history",
        lambda ai_root, peer_id, query_file, out_file, elapsed, success, reason:
            history_calls.append((peer_id, query_file, success, reason)),
    )

    hub._lease_sweep(ai_root)

    _, data = hub._read_peer_health("ag", health_dir)
    assert data["availability"]["profiles"]["deepthink"]["last_failure_reason"] == "lease_expired"
    assert len(history_calls) == 1
    peer_id, query_file, success, reason = history_calls[0]
    assert peer_id == "ag.deepthink"
    assert query_file == "q.txt"
    assert success is False
    assert reason == "lease_expired"


@pytest.mark.skipif(sys.platform != "win32", reason="pywinpty is Windows-only")
def test_ask_with_pty_threads_query_file_into_lease_open(tmp_path, monkeypatch):
    """Before the fix, _ask_with_pty never passed ask_query_file to
    _lease_open at all, so every PTY (ag) lease was permanently
    ask_query_file=None -- losing provenance needed for ask-history
    backfill on the lease-sweep path."""
    pytest.importorskip("winpty")
    monkeypatch.setattr(hub, "_lease_renew", lambda *a, **kw: None)
    monkeypatch.setattr(hub, "_lease_cfg", lambda node_id: (1.0, 5.0, 5.0))
    monkeypatch.setattr(hub, "_silent_startup_warning_sec", lambda: 0)

    captured = {}
    real_lease_open = hub._lease_open

    def _spy_lease_open(ai_root, node_id, pid, lease, ask_id=None, ask_query_file=None):
        captured["ask_query_file"] = ask_query_file
        return real_lease_open(
            ai_root, node_id, pid, lease, ask_id=ask_id, ask_query_file=ask_query_file,
        )

    monkeypatch.setattr(hub, "_lease_open", _spy_lease_open)

    ai_root = tmp_path / ".ai"
    (ai_root / ".lock").mkdir(parents=True)
    (ai_root / "state.json").write_text(json.dumps({"room_id": "r"}), encoding="utf-8")
    (ai_root / "leases.json").write_text("{}", encoding="utf-8")

    cmd = [sys.executable, "-c", "print('hi')"]
    hub._ask_with_pty(
        cmd, "test-node", 10, {**__import__("os").environ}, quiet=True,
        ai_root=ai_root, ask_query_file="ag-query.txt",
    )

    assert captured["ask_query_file"] == "ag-query.txt"


def test_peer_status_persists_live_cli_version(tmp_path, monkeypatch):
    health_dir = tmp_path / "health"

    def _read(hd, peer_id):
        path = hd / "health.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        data.setdefault("availability", {})
        return path, data

    def _write(hd, peer_id, data):
        hd.mkdir(parents=True, exist_ok=True)
        (hd / "health.json").write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(hub, "_read_peer_health", lambda peer_id, hd=None: _read(health_dir, peer_id))
    monkeypatch.setattr(hub, "_write_peer_health", lambda peer_id, data, ai_root, hd=None: _write(health_dir, peer_id, data))

    orchestration = {
        "hub_nodes": [{"node_id": "ag", "type": "peer", "enabled": True}]
    }
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orchestration)
    monkeypatch.setattr(hub, "_load_peers", lambda: {"peers": {"ag": {"sys_subdir": "antigravity"}}})
    monkeypatch.setattr(hub, "find_ai_root", lambda: tmp_path / ".ai")
    monkeypatch.setattr(
        hub, "_read_json",
        lambda path: {"peers": {"ag": {"safe_checks": [{"class": "version_only"}]}}}
        if str(path).endswith("status_checks.json") else {},
    )
    monkeypatch.setattr(hub, "_run_status_check", lambda check: (True, "agy 1.1.10\n"))
    monkeypatch.setattr(hub, "_refresh_peer_health_live", lambda *a, **k: None)
    monkeypatch.setattr(hub.hub_peer, "resolve_node_id", lambda node_id, orch=None: node_id)
    monkeypatch.setattr(hub.hub_peer, "normalize_orchestration", lambda orch: orch)
    monkeypatch.setattr(hub.hub_peer, "resolve_peer_sys_dir", lambda peer_id: "antigravity")

    hub.action_peer_status(node_id="ag")

    _, data = _read(health_dir, "ag")
    avail = data["availability"]
    assert avail["cli_version"] == "agy 1.1.10"
    assert avail["cli_version_source"] == "cli_live"
    assert avail.get("cli_version_checked_at")
