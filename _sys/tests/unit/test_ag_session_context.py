"""Task 5 (2026-07-19/20 absent-audit A2, fable+cx dissent from cc's "ag CTX-
absence is structural" framing): ag's statusline log is overwrite-only (single
latest frame), so _session_context_measured had no ag branch and RECENT
SESSIONS always showed CTX=absent for ag even for a session that just ran.
This extends T75's last-good-frame pattern to a per-session_id map so a
session's real context/token data survives past the moment its statusline
frame gets overwritten by the next one.
"""
import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
if str(SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "core"))
import snapshot


def test_ag_session_context_round_trip(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_session_context.json"
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)

    assert snapshot._load_ag_session_context("sess-1") is None

    snapshot._save_ag_session_context("sess-1", 12345, 200000, "gemini-3-pro", "2026-07-20T09:00:00+09:00")

    cached = snapshot._load_ag_session_context("sess-1")
    assert cached["used_tokens"] == 12345
    assert cached["window_tokens"] == 200000
    assert cached["model"] == "gemini-3-pro"
    assert cached["observed_at"] == "2026-07-20T09:00:00+09:00"


def test_ag_session_context_missing_session_id_is_noop(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_session_context.json"
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)
    snapshot._save_ag_session_context(None, 1, 2, "m", "now")
    assert not cache_path.exists()


def test_ag_session_context_load_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", tmp_path / "does_not_exist.json")
    assert snapshot._load_ag_session_context("sess-1") is None


def test_ag_session_context_load_corrupt_file_returns_none(tmp_path, monkeypatch):
    bad = tmp_path / "corrupt.json"
    bad.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", bad)
    assert snapshot._load_ag_session_context("sess-1") is None


def test_ag_session_context_save_never_raises_on_write_failure(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", blocker / "sub" / "cache.json")
    snapshot._save_ag_session_context("sess-1", 1, 2, "m", "now")  # must not raise


def test_ag_session_context_evicts_oldest_past_max_entries(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_session_context.json"
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_MAX_ENTRIES", 3)

    for i in range(5):
        snapshot._save_ag_session_context(
            f"sess-{i}", i, 1000, "m", f"2026-07-20T0{i}:00:00+09:00")

    store = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(store) == 3
    assert set(store.keys()) == {"sess-2", "sess-3", "sess-4"}


def test_session_context_measured_ag_uses_persisted_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_session_context.json"
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)
    snapshot._save_ag_session_context("sess-ag-1", 5000, 200000, "gemini-3-pro", "2026-07-20T09:00:00+09:00")

    ctx = snapshot._session_context_measured(
        "ag", {"session_id": "sess-ag-1"}, None, "2026-07-20T09:05:00+09:00")

    assert ctx["used_tokens"] == 5000
    assert ctx["window_tokens"] == 200000
    assert ctx["utilization_pct"] == 2.5
    assert ctx["source_tag"] == "ag_session_cache"
    assert ctx["measured_model"] == "gemini-3-pro"


def test_session_context_measured_ag_falls_back_to_profile_window_when_uncached(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", tmp_path / "does_not_exist.json")

    ctx = snapshot._session_context_measured(
        "ag", {"session_id": "sess-ag-unknown"},
        {"context": {"window_tokens": 128000}}, "2026-07-20T09:05:00+09:00")

    assert ctx["used_tokens"] is None
    assert ctx["window_tokens"] == 128000
    assert ctx["source_tag"] == "absent"


def test_session_context_measured_ag_no_session_id_is_absent():
    ctx = snapshot._session_context_measured("ag", {}, None, "2026-07-20T09:05:00+09:00")
    assert ctx["source_tag"] == "absent"
    assert ctx["used_tokens"] is None


def test_gather_peer_persists_ag_session_context(tmp_path, monkeypatch):
    cache_path = tmp_path / "ag_session_context.json"
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)

    live_file = tmp_path / "data" / "temp" / "ag_statusline_stdin.log"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_text(json.dumps({
        "session_id": "sess-live-1",
        "model": "gemini-3-pro",
        "context_window": {
            "context_window_size": 200000,
            "total_input_tokens": 3000,
            "total_output_tokens": 1000,
        },
    }), encoding="utf-8")

    peer_dir = tmp_path / "ag"
    peer_dir.mkdir()
    monkeypatch.setattr(snapshot, "SYS_DIR", tmp_path)
    monkeypatch.setattr(snapshot, "_AG_SESSION_CONTEXT_PATH", cache_path)

    def fake_capture_profile(peer, peer_dir_arg, session_id):
        return None
    monkeypatch.setattr(snapshot, "_capture_profile_from_active_session", fake_capture_profile)

    info = snapshot.gather_peer("ag", {"ag": peer_dir})
    assert info["capture_session_id"] == "sess-live-1"

    cached = snapshot._load_ag_session_context("sess-live-1")
    assert cached is not None
    assert cached["used_tokens"] == 4000
    assert cached["window_tokens"] == 200000
    assert cached["model"] == "gemini-3-pro"
