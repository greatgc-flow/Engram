"""Tests for hub.py session reuse (session_state.json management)."""
import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
import hub
import hub_peer


def _configured_node(node_id):
    normalized = hub_peer.normalize_orchestration()
    return next(
        node
        for node in normalized["hub_nodes"]
        if node.get("node_id") == node_id
    )


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
    node = _configured_node("cx")
    adapter = hub_peer.get_adapter(node)
    assert adapter.extract_session_id(raw, node, None) == "019ec163-b2fd-7452-b9cb-5538b7b5e83c"


def test_extract_thread_id_not_found():
    raw = '{"type":"turn.started"}\n{"type":"item.completed","item":{"text":"hello"}}\n'
    node = _configured_node("cx")
    adapter = hub_peer.get_adapter(node)
    assert adapter.extract_session_id(raw, node, None) is None


def test_extract_thread_id_malformed_json():
    raw = "not json\n{broken\n"
    node = _configured_node("cx")
    adapter = hub_peer.get_adapter(node)
    assert adapter.extract_session_id(raw, node, None) is None


# ── compute_scope_key ─────────────────────────────────────────

def test_compute_scope_key_explicit(ai_dir):
    assert hub._compute_scope_key(ai_dir, "debate-T2") == "debate-T2"


def test_compute_scope_key_from_room(ai_dir):
    assert hub._compute_scope_key(ai_dir) == "room-test"


def test_compute_scope_key_no_root():
    assert hub._compute_scope_key(None) == "default"


# ── build_session_cmd ─────────────────────────────────────────

def test_build_session_cmd_cx_fresh():
    node = _configured_node("cx")
    args, use_stdin = hub_peer.get_adapter(node).build_cmd(node, "test")
    assert args[0] == "codex"
    assert "--ephemeral" in args
    assert "-s" in args
    assert "workspace-write" in args
    assert "resume" not in args
    assert use_stdin is True


def test_build_session_cmd_cx_resume():
    node = _configured_node("cx")
    args, use_stdin = hub_peer.get_adapter(node).build_cmd(
        node, "test", "uuid-001"
    )
    assert args[0] == "codex"
    assert "--ephemeral" in args
    assert "resume" not in args
    assert "uuid-001" not in args
    assert use_stdin is True


def test_build_session_cmd_gc_fresh():
    node = _configured_node("gc")
    with patch("hub_peer.uuid.uuid4", return_value="generated-uuid"):
        invocation = hub_peer.get_adapter(node).build_session_cmd(
            node, "test"
        )
    assert invocation.cmd[0] == "gemini"
    assert "--session-id" in invocation.cmd
    assert "generated-uuid" in invocation.cmd
    assert "--approval-mode" in invocation.cmd
    assert "auto_edit" in invocation.cmd
    assert "yolo" not in invocation.cmd
    assert "--skip-trust" in invocation.cmd
    for arg in node["profile_args"]:
        assert arg in invocation.cmd
    assert invocation.use_stdin is True
    assert invocation.session_id == "generated-uuid"


def test_build_session_cmd_gc_resume():
    node = _configured_node("gc")
    invocation = hub_peer.get_adapter(node).build_session_cmd(
        node, "test", "uuid-gc-1"
    )
    assert invocation.cmd[:3] == ["gemini", "--resume", "uuid-gc-1"]
    assert "-p" in invocation.cmd
    assert "-" in invocation.cmd
    for arg in node["profile_args"]:
        assert arg in invocation.cmd
    assert invocation.use_stdin is True
    assert invocation.session_id == "uuid-gc-1"


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


def test_ask_cx_explicit_reuse_is_rejected(ai_dir):
    """cx has no configured session-reuse capability."""
    with pytest.raises(SystemExit) as exc:
        hub.action_ask(
            "cx", "hello", None, 120, ai_dir, session_policy="reuse"
        )
    assert exc.value.code == 1


def test_ask_cx_auto_uses_fresh_ephemeral_command(ai_dir):
    """Default policy remains fresh even if legacy cx session state exists."""
    hub._set_active_session("cx", "room-test", "stored-uuid-001", "ask-prev", ai_dir)
    mock_proc = _make_mock_proc(stdout=THREAD_STARTED_JSONL)
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        hub.action_ask("cx", "hello again", None, 120, ai_dir)

    call_args = mock_popen.call_args[0][0]
    assert "--ephemeral" in call_args
    assert "-s" in call_args
    assert "workspace-write" in call_args
    assert "resume" not in call_args
    assert "stored-uuid-001" not in call_args


def test_ask_cx_session_policy_fresh_skips_session(ai_dir):
    """session_policy=fresh bypasses session reuse entirely."""
    hub._set_active_session("cx", "room-test", "stored-uuid-001", "ask-prev", ai_dir)
    mock_proc = _make_mock_proc(stdout=b"ok")
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        hub.action_ask("cx", "fresh call", None, 120, ai_dir, session_policy="fresh")

    call_args = mock_popen.call_args[0][0]
    assert "--ephemeral" in call_args
    assert "-s" in call_args
    assert "workspace-write" in call_args
    assert "resume" not in call_args


def test_session_capability_is_config_driven():
    node = {
        "node_id": "custom.worker",
        "session_mode": "reuse",
        "requires_pty": False,
    }
    assert hub._session_reuse_enabled(node, "auto") is True


def test_session_none_disables_reuse():
    assert hub._session_reuse_enabled(
        {"node_id": "cx", "session_mode": "none"}, "auto"
    ) is False


def test_explicit_reuse_fails_without_capability():
    with pytest.raises(ValueError, match="no configured session-reuse capability"):
        hub._session_reuse_enabled(
            {"node_id": "custom", "session_mode": "none"}, "reuse"
        )


def test_cx_session_reuse_is_disabled():
    assert _configured_node("cx")["session_mode"] == "none"


def test_no_node_uses_auto_session_mode():
    normalized = hub_peer.normalize_orchestration()
    assert all(
        node.get("session_mode", "none") != "auto"
        for node in normalized["hub_nodes"]
    )


def test_session_fingerprint_gc_stable_across_calls():
    """gc fingerprint excludes the generated session UUID."""
    node = _configured_node("gc")
    adapter = hub_peer.get_adapter(node)
    fp1 = adapter.session_fingerprint(node)
    fp2 = adapter.session_fingerprint(node)
    assert fp1 == fp2
    assert len(fp1) == 8


def test_ask_uses_project_root_as_cwd(ai_dir):
    """action_ask sets Popen cwd to ai_root.parent (project root), not caller's cwd."""
    ok_proc = _make_mock_proc(stdout=b"response", returncode=0)
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.Popen", return_value=ok_proc) as mock_popen:
        hub.action_ask("cx", "test", None, 120, ai_dir, session_policy="none")

    call_kwargs = mock_popen.call_args.kwargs
    assert call_kwargs.get("cwd") == str(ai_dir.parent)


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


# ── adapter session_fingerprint (stability / flag-hashing) ─────

class TestSessionFingerprint:
    """Adapter fingerprints must be stable and flag-sensitive."""

    def setup_method(self):
        self.node = _configured_node("gc")
        self.adapter = hub_peer.get_adapter(self.node)

    def test_gc_stable_across_calls(self):
        # gc normally receives a fresh --session-id UUID per invocation; fingerprint
        # must NOT include that UUID — only the static permission flags.
        fp1 = self.adapter.session_fingerprint(self.node)
        fp2 = self.adapter.session_fingerprint(self.node)
        assert fp1 == fp2

    def test_returns_8_hex_chars(self):
        fp = self.adapter.session_fingerprint(self.node)
        assert len(fp) == 8
        assert all(c in "0123456789abcdef" for c in fp)

    def test_different_exe_name_differs(self):
        """Fingerprint changes when the executable name changes (e.g., upgrade)."""
        fp_a = self.adapter.session_fingerprint(self.node)
        changed = {**self.node, "invoke": "gemini2"}
        fp_b = self.adapter.session_fingerprint(changed)
        assert fp_a != fp_b

    def test_cx_has_no_session_fingerprint(self):
        """cx inherits the unsupported-session fingerprint contract."""
        node = _configured_node("cx")
        with pytest.raises(RuntimeError, match="does not implement session reuse"):
            hub_peer.get_adapter(node).session_fingerprint(node)

    def test_ignores_path_prefix(self):
        """Only the base exe name matters, not any leading path component."""
        # Callers strip the path before calling — verify the function is consistent
        # when given just a bare name vs a name that looks like a basename.
        fp_bare = self.adapter.session_fingerprint(self.node)
        # Simulate a caller that accidentally passes the full path:
        # the function itself does not strip — that's the caller's job.
        # This test documents the expected *stable* contract for the bare name.
        with_path = {
            **self.node,
            "invoke": str(Path("portable") / "bin" / "gemini"),
        }
        assert self.adapter.session_fingerprint(with_path) == fp_bare

    def test_profile_args_are_encoded(self):
        fp_a = self.adapter.session_fingerprint(self.node)
        changed = {
            **self.node,
            "profile_args": [*self.node["profile_args"], "--extra-profile-flag"],
        }
        assert self.adapter.session_fingerprint(changed) != fp_a

    def test_matches_normalized_static_args(self):
        static_args = [
            "-" if arg == "{query}" else arg
            for arg in self.node["invoke_args"]
        ] + self.node["profile_args"]
        expected = hashlib.sha1(
            ("gemini|" + ",".join(static_args)).encode()
        ).hexdigest()[:8]
        assert self.adapter.session_fingerprint(self.node) == expected


# ── _classify_resume_failure ───────────────────────────────────

class TestClassifyResumeFailure:
    """_classify_resume_failure(stderr) → 'transient' | 'permanent'

    Transient: worth retrying with resume (network / quota / rate issues).
    Permanent: retire the session and go fresh (session gone / auth / context).
    """

    # --- permanent: session-identity errors ---

    def test_session_not_found_is_permanent(self):
        assert hub._classify_resume_failure("Error: session not found") == "permanent"

    def test_invalid_session_is_permanent(self):
        assert hub._classify_resume_failure("invalid session id provided") == "permanent"

    def test_session_expired_is_permanent(self):
        assert hub._classify_resume_failure("session expired, please start a new one") == "permanent"

    def test_unknown_session_is_permanent(self):
        assert hub._classify_resume_failure("unknown session: abc-123") == "permanent"

    def test_no_such_session_is_permanent(self):
        assert hub._classify_resume_failure("no such session exists") == "permanent"

    def test_context_too_long_is_permanent(self):
        assert hub._classify_resume_failure("context length exceeded maximum") == "permanent"

    # --- transient: infra / rate errors ---

    def test_timeout_is_transient(self):
        assert hub._classify_resume_failure("connection timed out") == "transient"

    def test_rate_limit_is_transient(self):
        assert hub._classify_resume_failure("rate limit exceeded, retry after 60s") == "transient"

    def test_quota_exceeded_is_transient(self):
        assert hub._classify_resume_failure("quota exceeded for this minute") == "transient"

    def test_connection_refused_is_transient(self):
        assert hub._classify_resume_failure("connection refused") == "transient"

    def test_503_is_transient(self):
        assert hub._classify_resume_failure("503 Service Unavailable") == "transient"

    def test_429_is_transient(self):
        assert hub._classify_resume_failure("429 Too Many Requests") == "transient"

    def test_network_error_is_transient(self):
        assert hub._classify_resume_failure("network error: unable to reach endpoint") == "transient"

    # --- case-insensitivity ---

    def test_uppercase_session_not_found_is_permanent(self):
        assert hub._classify_resume_failure("SESSION NOT FOUND") == "permanent"

    def test_uppercase_timeout_is_transient(self):
        assert hub._classify_resume_failure("TIMED OUT") == "transient"

    # --- empty / unrecognised stderr ---

    def test_empty_stderr_is_permanent(self):
        """Unknown error: safer to retire the session than to retry blindly."""
        assert hub._classify_resume_failure("") == "permanent"

    def test_generic_error_is_permanent(self):
        """Unrecognised error message defaults to permanent (safe fallback)."""
        assert hub._classify_resume_failure("something completely unexpected happened") == "permanent"
