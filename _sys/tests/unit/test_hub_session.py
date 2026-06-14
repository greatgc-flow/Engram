"""Tests for hub.py session reuse (session_state.json management)."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
import hub


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def peer_dir(tmp_path):
    d = tmp_path / "codex"
    d.mkdir()
    return d


@pytest.fixture
def ai_dir(tmp_path):
    ai = tmp_path / ".ai"
    hub.ensure_ai_dir(ai)
    hub._write_state(ai, {
        "room_id": "room-test",
        "members": {},
        "mission": None, "blocked": None, "phase": None,
        "active_coordinator": None, "human_interface_peer": None,
        "role_assignments": {}, "updated_at": None,
    })
    return ai


@pytest.fixture(autouse=True)
def patch_peer_dir(tmp_path, peer_dir):
    """Redirect _peer_sys_dir to tmp_path/<peer>."""
    def _fake_dir(peer_id):
        d = tmp_path / peer_id
        d.mkdir(exist_ok=True)
        return d
    with patch.object(hub, "_peer_sys_dir", side_effect=_fake_dir):
        yield


# ── Session state helpers ──────────────────────────────────────

def test_load_session_state_missing_returns_empty(tmp_path):
    state = hub._load_session_state("cx")
    assert state["peer_id"] == "cx"
    assert state["active"] == {}
    assert state["history"] == []


def test_set_and_get_active_session(ai_dir):
    hub._set_active_session("cx", "room-abc", "uuid-001", "ask-1", ai_dir)
    entry = hub._get_active_session("cx", "room-abc")
    assert entry is not None
    assert entry["session_id"] == "uuid-001"
    assert entry["status"] == "active"


def test_get_active_session_missing_scope_returns_none(ai_dir):
    assert hub._get_active_session("cx", "room-missing") is None


def test_retire_session_moves_to_history(ai_dir):
    hub._set_active_session("cx", "room-abc", "uuid-001", "ask-1", ai_dir)
    hub._retire_session("cx", "room-abc", "test_reason", ai_dir)
    assert hub._get_active_session("cx", "room-abc") is None
    state = hub._load_session_state("cx")
    assert len(state["history"]) == 1
    assert state["history"][0]["retire_reason"] == "test_reason"
    assert state["history"][0]["status"] == "retired"


def test_clear_peer_sessions_retires_all(ai_dir):
    hub._set_active_session("cx", "room-a", "uuid-1", "ask-1", ai_dir)
    hub._set_active_session("cx", "room-b", "uuid-2", "ask-2", ai_dir)
    hub._clear_peer_sessions("cx", "new-topic", ai_dir)
    assert hub._get_active_session("cx", "room-a") is None
    assert hub._get_active_session("cx", "room-b") is None
    state = hub._load_session_state("cx")
    assert len(state["history"]) == 2


def test_set_session_updates_last_used(ai_dir):
    hub._set_active_session("cx", "scope", "uuid-001", "ask-1", ai_dir)
    first_created = hub._get_active_session("cx", "scope")["created_at"]
    hub._set_active_session("cx", "scope", "uuid-001", "ask-2", ai_dir)
    entry = hub._get_active_session("cx", "scope")
    assert entry["last_ask_id"] == "ask-2"
    assert entry["created_at"] == first_created  # created_at preserved


# ── extract_jsonl_thread_id ────────────────────────────────────

def test_extract_thread_id_found():
    raw = '{"type":"thread.started","thread_id":"019ec163-b2fd-7452-b9cb-5538b7b5e83c"}\n{"type":"turn.started"}\n'
    assert hub._extract_jsonl_thread_id(raw) == "019ec163-b2fd-7452-b9cb-5538b7b5e83c"


def test_extract_thread_id_not_found():
    raw = '{"type":"turn.started"}\n{"type":"item.completed","item":{"text":"hello"}}\n'
    assert hub._extract_jsonl_thread_id(raw) is None


def test_extract_thread_id_malformed_json():
    raw = "not json\n{broken\n"
    assert hub._extract_jsonl_thread_id(raw) is None


# ── compute_scope_key ─────────────────────────────────────────

def test_compute_scope_key_explicit(ai_dir):
    assert hub._compute_scope_key(ai_dir, "debate-T2") == "debate-T2"


def test_compute_scope_key_from_room(ai_dir):
    assert hub._compute_scope_key(ai_dir) == "room-test"


def test_compute_scope_key_no_root():
    assert hub._compute_scope_key(None) == "default"


# ── build_session_cmd ─────────────────────────────────────────

def test_build_session_cmd_cx_fresh():
    args, use_stdin, gc_id = hub._build_session_cmd("cx", None, "codex")
    assert args == ["exec", "-", "-s", "workspace-write", "--json", "--ignore-rules"]
    assert use_stdin is True
    assert gc_id is None


def test_build_session_cmd_cx_resume():
    args, use_stdin, gc_id = hub._build_session_cmd("cx", "uuid-001", "codex")
    assert args == ["exec", "resume", "uuid-001", "-", "-s", "workspace-write", "--json", "--ignore-rules"]
    assert use_stdin is True
    assert gc_id is None


def test_build_session_cmd_gc_fresh():
    with patch("hub.uuid") as mock_uuid:
        mock_uuid.uuid4.return_value = MagicMock(__str__=lambda self: "generated-uuid")
        args, use_stdin, gc_id = hub._build_session_cmd("gc", None, "gemini")
    assert "--session-id" in args
    assert "--approval-mode" in args
    assert "auto_edit" in args
    assert "yolo" not in args
    assert "--skip-trust" in args
    assert use_stdin is True
    assert gc_id is not None


def test_build_session_cmd_gc_resume():
    args, use_stdin, gc_id = hub._build_session_cmd("gc", "uuid-gc-1", "gemini")
    assert args == [
        "--resume", "uuid-gc-1", "-p", "-", "-o", "text",
        "--approval-mode", "auto_edit", "--skip-trust",
    ]
    assert use_stdin is True
    assert gc_id is None


# ── action_ask session integration ────────────────────────────

def _make_mock_proc(stdout=b"", stderr=b"", returncode=0):
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = returncode
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.poll.return_value = None
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    return mock_proc


THREAD_STARTED_JSONL = b'{"type":"thread.started","thread_id":"019ec163-test-uuid"}\n{"type":"item.completed","item":{"text":"hello"}}\n'


def test_ask_cx_stores_thread_id_on_first_success(ai_dir):
    """First cx ask stores thread_id in session_state.json."""
    mock_proc = _make_mock_proc(stdout=THREAD_STARTED_JSONL)
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=mock_proc):
        hub.action_ask("cx", "hello", None, 120, ai_dir, session_policy="reuse")

    entry = hub._get_active_session("cx", "room-test")
    assert entry is not None
    assert entry["session_id"] == "019ec163-test-uuid"


def test_ask_cx_uses_resume_on_second_call(ai_dir):
    """Second cx ask uses 'codex exec resume <id>'."""
    hub._set_active_session("cx", "room-test", "stored-uuid-001", "ask-prev", ai_dir)
    mock_proc = _make_mock_proc(stdout=THREAD_STARTED_JSONL)
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        hub.action_ask("cx", "hello again", None, 120, ai_dir, session_policy="reuse")

    call_args = mock_popen.call_args[0][0]
    assert "resume" in call_args
    assert "stored-uuid-001" in call_args


def test_ask_cx_session_policy_fresh_skips_session(ai_dir):
    """session_policy=fresh bypasses session reuse entirely."""
    hub._set_active_session("cx", "room-test", "stored-uuid-001", "ask-prev", ai_dir)
    mock_proc = _make_mock_proc(stdout=b"ok")
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        hub.action_ask("cx", "fresh call", None, 120, ai_dir, session_policy="fresh")

    call_args = mock_popen.call_args[0][0]
    # Should NOT use resume — ephemeral path (original invoke_args)
    assert "resume" not in call_args


def test_ask_cx_resume_failure_retries_fresh(ai_dir):
    """Resume failure triggers fresh retry; old session retired."""
    hub._set_active_session("cx", "room-test", "stale-uuid", "ask-old", ai_dir)
    fail_proc = _make_mock_proc(returncode=1, stderr=b"session not found")
    ok_proc = _make_mock_proc(stdout=THREAD_STARTED_JSONL, returncode=0)
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", side_effect=[fail_proc, ok_proc]):
        hub.action_ask("cx", "after stale", None, 120, ai_dir, session_policy="reuse")

    # Old session retired
    assert hub._get_active_session("cx", "room-test") is not None  # new session created
    entry = hub._get_active_session("cx", "room-test")
    assert entry["session_id"] == "019ec163-test-uuid"  # new thread_id stored


def test_new_topic_clears_sessions(ai_dir):
    """new-topic clears active sessions for all peers."""
    hub._set_active_session("cx", "room-test", "uuid-cx", "ask-1", ai_dir)
    hub._set_active_session("gc", "room-test", "uuid-gc", "ask-2", ai_dir)
    hub.action_new_topic(ai_dir, "new subject")
    assert hub._get_active_session("cx", "room-test") is None
    assert hub._get_active_session("gc", "room-test") is None


def test_clear_room_clears_sessions(ai_dir):
    """clear-room clears active sessions for all peers."""
    hub._set_active_session("cx", "room-test", "uuid-cx", "ask-1", ai_dir)
    hub.action_clear_room(ai_dir, "clean slate")
    assert hub._get_active_session("cx", "room-test") is None
