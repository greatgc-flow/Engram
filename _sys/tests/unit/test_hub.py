"""hub.py 11개 액션 단위 테스트 (ask 포함, --format llm 제거됨)."""
import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import hub


def _make_mock_proc(stdout=b"", stderr=b"", returncode=0):
    """Create a mock subprocess.Popen object for action_ask tests."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = returncode
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.poll.return_value = returncode
    mock_proc.stdout.read.return_value = stdout
    mock_proc.stderr.read.return_value = stderr
    return mock_proc


def test_ask_coordinator_falls_back_from_unroutable_stale_leader(ai_dir):
    (ai_dir / "state.json").write_text(
        json.dumps({"room_id": "room-test", "leader": "gc", "members": {}}),
        encoding="utf-8",
    )
    orch = {
        "hub_nodes": [
            {"node_id": "gc", "type": "peer", "enabled": False},
            {"node_id": "cc", "type": "peer"},
        ],
        "consensus": {"default_voters": ["cc"]},
    }
    with patch("hub._load_orchestration", return_value=orch), \
         patch("hub.is_routable", side_effect=lambda peer, orch=None: peer == "cc"), \
         patch("hub._healthy_peer", side_effect=lambda peer, ai_root=None: peer == "cc"), \
         patch("hub._thin_forward_envelope", return_value="forwarded"), \
         patch("hub._record_routing_metric"), \
         patch("hub.action_ask") as ask:
        hub.action_ask_coordinator(ai_dir, "review", None, 30, "cx")
    assert ask.call_args.args[0] == "cc"


# ─── init-session ───────────────────────────────────────────
class TestInitSession:
    def test_cc_creates_sid(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "cc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["members"]["cc"] is not None
        assert state["members"]["cc"].startswith("c")

    def test_gc_creates_sid(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "gc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["members"]["gc"] is not None
        assert state["members"]["gc"].startswith("g")

    def test_room_id_format(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "cc")
        hub.action_init_session(ai_dir, "gc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        room_id = state["room_id"]
        assert room_id is not None
        assert "cc" in state["members"]

    def test_output_is_sid_only(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "cc")
        out = capsys.readouterr().out.strip()
        # SID만 출력 (단 1줄, 5자: prefix + 4 hex)
        assert len(out) == 5
        assert out.startswith("c")

    def test_session_dir_created(self, ai_dir):
        hub.action_init_session(ai_dir, "cc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert (ai_dir / "sessions" / state["room_id"]).exists()


# ─── send + check ────────────────────────────────────────────
class TestSendCheck:
    def test_send_creates_message(self, ai_dir):
        hub.action_send(ai_dir, "cc", "gc", "hello")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert len(mb["messages"]) == 1
        assert mb["messages"][0]["content"] == "hello"
        assert mb["messages"][0]["status"] == "unread"
        assert mb["unread_count"] == 1

    def test_check_pretty_print(self, ai_dir, capsys):
        hub.action_send(ai_dir, "cc", "gc", "full message content")
        hub.action_check(ai_dir, "gc")
        out = capsys.readouterr().out
        assert "1 messages for gc" in out   # 3TCP v1 [HUB] READ 형식
        assert "full message content" in out  # 전문 출력 확인

    def test_check_empty(self, ai_dir, capsys):
        hub.action_check(ai_dir, "cc")
        out = capsys.readouterr().out
        assert "inbox empty" in out

    def test_check_shows_all_messages(self, ai_dir, capsys):
        for i in range(3):
            hub.action_send(ai_dir, "gc", "cc", f"msg content {i}")
        hub.action_check(ai_dir, "cc")
        out = capsys.readouterr().out
        assert "3 messages for cc" in out  # 3TCP v1 [HUB] READ 형식
        for i in range(3):
            assert f"msg content {i}" in out  # 전문 모두 출력


# ─── mark-read ───────────────────────────────────────────────
class TestMarkRead:
    def test_mark_all(self, ai_dir):
        hub.action_send(ai_dir, "cc", "gc", "m1")
        hub.action_send(ai_dir, "cc", "gc", "m2")
        hub.action_mark_read(ai_dir, "gc", all_=True, msg_id=None)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 0

    def test_mark_by_id(self, ai_dir):
        hub.action_send(ai_dir, "cc", "gc", "m1")
        hub.action_send(ai_dir, "cc", "gc", "m2")
        hub.action_mark_read(ai_dir, "gc", all_=False, msg_id=1)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 1


# ─── update-status + status ──────────────────────────────────
class TestStatus:
    def test_update_and_status(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "cc")
        capsys.readouterr()  # SID 출력 flush
        hub.action_update_status(ai_dir, "test mission", None, "2")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "ROOM STATUS" in out
        assert "test mission" in out
        assert "Phase" in out

    def test_status_shows_mailbox_counts(self, ai_dir, capsys):
        hub.action_send(ai_dir, "gc", "cc", "hi cc")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "1 unread" in out

    def test_status_shows_handoff(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "cc")
        capsys.readouterr()
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        sd = ai_dir / "sessions" / state["room_id"]
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "handoff.md").write_text("## [GOAL]\n- 테스트 목표\n", encoding="utf-8")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "HANDOFF" in out
        assert "테스트 목표" in out  # handoff 원문 전체 출력


# ─── end-session ─────────────────────────────────────────────
class TestEndSession:
    def test_end_cleans_read_messages(self, ai_dir):
        hub.action_init_session(ai_dir, "cc")
        hub.action_send(ai_dir, "gc", "cc", "done")
        hub.action_mark_read(ai_dir, "cc", all_=True, msg_id=None)
        hub.action_end_session(ai_dir, "cc")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert len(mb["messages"]) == 0

    def test_end_updates_handoff(self, ai_dir):
        hub.action_init_session(ai_dir, "cc")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        hub.action_end_session(ai_dir, "cc")
        handoff = (ai_dir / "sessions" / state["room_id"] / "handoff.md").read_text("utf-8")
        assert "cc: 세션 종료" in handoff


# ─── ask (동기 subprocess) ───────────────────────────────────
class TestAsk:
    # subprocess는 bytes 캡처 (capture_output=True, text 없음) → mock.stdout = bytes
    def test_ask_cx_calls_subprocess(self, tmp_path):
        mock_proc = _make_mock_proc(stdout=b"Codex raw response")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            hub.action_ask("cx", "test query", None, 120, None)
            call_args = mock_popen.call_args[0][0]
            assert "codex" in call_args[0]
            assert "exec" in call_args

    def test_ask_cc_calls_subprocess(self, tmp_path):
        mock_proc = _make_mock_proc(stdout=b"Claude raw response")
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            hub.action_ask("cc", "test query", None, 120, None)
            call_args = mock_popen.call_args[0][0]
            assert "claude" in call_args[0]
            assert "-p" in call_args

    def test_ask_strips_ansi(self, capsys):
        mock_proc = _make_mock_proc(stdout=b"\x1b[32mcolored response\x1b[0m")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc):
            hub.action_ask("cx", "test", None, 120, None)
        out = capsys.readouterr().out
        assert "\x1b" not in out
        assert "colored response" in out

    def test_ask_timeout_exits(self):
        mock_proc = _make_mock_proc()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired("gemini", 120)
        mock_proc.poll.return_value = None
        # time.monotonic side_effect: t0, deadline_calc, loop1_remaining, loop2_remaining, elapsed_after_except
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("hub.time.monotonic", side_effect=[0.0, 0.0, 0.0, 200.0, 200.0]), \
             patch("hub._kill_process_tree"):
            with pytest.raises(SystemExit):
                hub.action_ask("gc", "test", None, 120, None)

    def test_ask_not_found_exits(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit):
                hub.action_ask("gc", "test", None, 120, None)

    def test_ask_query_file(self, tmp_path, capsys):
        ipc_dir = tmp_path / "ipc"
        ipc_dir.mkdir(parents=True, exist_ok=True)
        qf = ipc_dir / "cx-20260621223000-ab12.txt"
        qf.write_text("file query content", encoding="utf-8")
        mock_proc = _make_mock_proc(stdout=b"response")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc):
            hub.action_ask("cx", "", str(qf), 120, None)
        assert not qf.exists()

    def test_ask_nonzero_exit_propagates(self, capsys):
        mock_proc = _make_mock_proc(stdout=b"partial response", stderr=b"some error", returncode=1)
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             pytest.raises(SystemExit) as exc_info:
            hub.action_ask("cx", "test", None, 120, None)
        assert exc_info.value.code == 1
        _, err = capsys.readouterr()
        assert "[HUB:ERROR] cx exited 1" in err

    def test_ask_prepends_room_context_and_records_success(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "codex"
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        hub.action_init_session(ai_dir, "cx", "room-test")
        session_dir = ai_dir / "sessions" / "room-test"
        (session_dir / "handoff.md").write_text("## [GOAL]\n- keep context\n", encoding="utf-8")

        mock_proc = _make_mock_proc(stdout=b"ok")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc):
            hub.action_ask("cx", "hello", None, 120, ai_dir)

        sent = mock_proc.communicate.call_args.kwargs["input"].decode("utf-8")
        assert "Room ID: room-test" in sent
        assert "keep context" in sent
        assert "[USER QUERY]\nhello" in sent

        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["session_health"]["consecutive_failures"] == 0
        assert health["availability"]["gate_open"] is True
        assert health["availability"]["last_invocation_exit_code"] == 0

    def test_ask_success_recovers_yellow_peer(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "codex"
        peer_dir.mkdir()
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        (peer_dir / "health.json").write_text(json.dumps({
            "peer_id": "cx",
            "context_health": {"status": "YELLOW"},
            "session_health": {"consecutive_failures": 3, "last_failure_reason": "timeout"},
            "availability": {"gate_open": True, "workspace_not_trusted": True},
        }), encoding="utf-8")
        mock_proc = _make_mock_proc(stdout=b"ok")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc):
            hub.action_ask("cx", "hello", None, 120, ai_dir)
        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "GREEN"
        assert health["session_health"]["consecutive_failures"] == 0
        assert "workspace_not_trusted" not in health["availability"]

    def test_ask_eperm_marks_peer_red_and_blocks_next_call(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "codex"
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        mock_proc = _make_mock_proc(stderr=b"Fatal error\nError: spawn EPERM", returncode=1)
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             pytest.raises(SystemExit) as exc_first:
            hub.action_ask("cx", "hello", None, 120, ai_dir)
        assert exc_first.value.code in (1, 4)  # T4 fatal exit or legacy T1

        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "RED"
        assert health["session_health"]["last_failure_reason"] == "sandbox_spawn_eperm"
        assert health["availability"]["gate_open"] is False
        assert health["availability"]["sandbox_blocked"] is True

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen") as mock_popen:
            with pytest.raises(SystemExit) as exc:
                hub.action_ask("cx", "again", None, 120, ai_dir)
            assert exc.value.code == 2
            mock_popen.assert_not_called()

    def test_ask_supports_literal_peer_env_vars(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "codex"
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "identity": {"node_to_peer": {"cx": "codex"}}
        })
        monkeypatch.setattr(hub, "_load_peers", lambda: {
            "codex": {
                "sys_subdir": "codex",
                "env_vars": {
                    "CODEX_TRUST_WORKSPACE": True,
                    "SOME_FALSE_FLAG": "false",
                },
            }
        })
        mock_proc = _make_mock_proc(stdout=b"ok")
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            hub.action_ask("cx", "hello", None, 120, ai_dir)

        env = mock_popen.call_args.kwargs["env"]
        assert env["CODEX_TRUST_WORKSPACE"] == "true"
        assert env["SOME_FALSE_FLAG"] == "false"

    def _ag_node(self):
        return {
            "node_id": "ag", "invoke": "agy", "type": "peer",
            "adapter_class": "AgyAdapter",
            "invoke_args": ["--dangerously-skip-permissions", "-p", "{query}"],
            "requires_pty": True, "timeout": 300, "memory": "ephemeral",
        }

    def test_ask_ag_uses_pty_path(self, monkeypatch, capsys):
        """ag with requires_pty=true must go through _ask_with_pty, not Popen."""
        import subprocess as _sp
        node = self._ag_node()
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        mock_pty = MagicMock(return_value=("ANTIGRAVITY", 16))
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", mock_pty), \
             patch("subprocess.Popen") as mock_popen:
            hub.action_ask("ag", "test", None, 300, None)
        mock_pty.assert_called_once()
        mock_popen.assert_not_called()

    def test_ask_ag_pty_output_through_parse_output(self, monkeypatch, capsys):
        """PTY output must be passed through adapter.parse_output before printing."""
        node = self._ag_node()
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", return_value=("  clean response  ", 10)):
            hub.action_ask("ag", "test", None, 300, None)
        out, _ = capsys.readouterr()
        assert "clean response" in out

    def test_ask_ag_pty_writes_output_file(self, tmp_path, monkeypatch):
        """PTY path must write parsed output to output_file when specified."""
        node = self._ag_node()
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        out_file = ai_dir / "reply.txt"
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda _: tmp_path / "antigravity")
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", return_value=("PTY OUTPUT", 5)):
            hub.action_ask("ag", "test", None, 300, ai_dir, output_file=str(out_file))
        assert out_file.exists()
        assert "PTY OUTPUT" in out_file.read_text(encoding="utf-8")

    def test_ask_ag_pty_quiet_mode(self, monkeypatch, capsys):
        """PTY quiet mode must print only the response, no header."""
        node = self._ag_node()
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", return_value=("quiet reply", 3)):
            hub.action_ask("ag", "test", None, 300, None, quiet=True)
        out, _ = capsys.readouterr()
        assert "quiet reply" in out
        assert "[HUB]" not in out

    def test_ask_ag_pty_ansi_stripped(self, monkeypatch, capsys):
        """PTY output ANSI codes must be stripped before returning."""
        node = self._ag_node()
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        ansi_output = "\x1b[32mgreen text\x1b[0m"
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", return_value=(ansi_output, 5)):
            hub.action_ask("ag", "test", None, 300, None)
        out, _ = capsys.readouterr()
        assert "\x1b" not in out
        assert "green text" in out

    def test_ask_ag_empty_pty_response_is_failure(self, monkeypatch, capsys):
        node = self._ag_node()
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {"hub_nodes": [node]})
        with patch("shutil.which", return_value="/usr/bin/agy"), \
             patch("hub._ask_with_pty", return_value=("", 5)), \
             pytest.raises(SystemExit) as exc:
            hub.action_ask("ag", "test", None, 300, None)
        assert exc.value.code == 1
        assert "no usable response" in capsys.readouterr().err

    def test_ask_failure_classification_reads_lifecycle_policy(self, monkeypatch):
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "ask_failure_classification": {
                "default_reason": "fallback_reason",
                "patterns": [
                    {
                        "reason": "custom_limit",
                        "match_any": ["custom limit"],
                        "availability": {"rate_limit_state": "limited"}
                    }
                ]
            }
        })
        reason, extra = hub._classify_ask_failure("CUSTOM LIMIT reached")
        assert reason == "custom_limit"
        assert extra["rate_limit_state"] == "limited"

    def test_send_can_be_disabled_by_lifecycle_policy(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "messaging": {"send": {"mode": "disabled"}}
        })
        with pytest.raises(SystemExit) as exc:
            hub.action_send(ai_dir, "cc", "gc", "hello")
        assert exc.value.code == 1

    def test_send_rejects_disallowed_type_by_lifecycle_policy(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "messaging": {"send": {"mode": "retain_improve", "allowed_types": ["MSG"]}}
        })
        with pytest.raises(SystemExit) as exc:
            hub.action_send(ai_dir, "cc", "gc", "hello", msg_type="DIRECTIVE")
        assert exc.value.code == 1


# ─── handoff FIFO ────────────────────────────────────────────
class TestHandoffFIFO:
    def test_fifo_max_completed(self, ai_dir):
        session_dir = ai_dir / "sessions" / "c1234-g5678"
        session_dir.mkdir(parents=True)
        sections = {
            "GOAL": ["목표"],
            "RECENT_COMPLETED": [f"task-{i}" for i in range(10)],
            "PENDING_ISSUES": [],
            "KEY_DECISIONS": []
        }
        hub._write_handoff(session_dir, sections)
        result = hub._read_handoff(session_dir)
        assert len(result["RECENT_COMPLETED"]) <= hub.HANDOFF_MAX_COMPLETED

    def test_fifo_char_limit(self, ai_dir):
        session_dir = ai_dir / "sessions" / "c1234-g5678"
        session_dir.mkdir(parents=True)
        sections = {
            "GOAL": ["목표"],
            "RECENT_COMPLETED": ["x" * 2000] * 10,
            "PENDING_ISSUES": [],
            "KEY_DECISIONS": []
        }
        hub._write_handoff(session_dir, sections)
        content = (session_dir / "handoff.md").read_text("utf-8")
        assert len(content) <= hub.HANDOFF_MAX_CHARS


# ─── ANSI strip ──────────────────────────────────────────────
class TestAnsiStrip:
    def test_strip_color_codes(self):
        assert hub._strip_ansi("\x1b[32mgreen\x1b[0m") == "green"

    def test_strip_cursor_movement(self):
        assert hub._strip_ansi("\x1b[1Aup\x1b[2K") == "up"

    def test_no_ansi_unchanged(self):
        assert hub._strip_ansi("plain text") == "plain text"


# ─── §P-2 메시지 봉투 확장 ────────────────────────────────────
class TestMessageEnvelope:
    def test_send_with_type_and_thread(self, ai_dir, capsys):
        hub.action_send(ai_dir, "cc", "gc", "do this",
                        thread_id="t-test1", msg_type="DIRECTIVE")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        msg = mb["messages"][0]
        assert msg["type"] == "DIRECTIVE"
        assert msg["thread_id"] == "t-test1"
        assert msg["cc"] == []
        assert msg["ref"] is None

    def test_send_with_cc_and_ref(self, ai_dir, capsys):
        hub.action_send(ai_dir, "gc", "cc", "done",
                        thread_id="t-test1", msg_type="ARTIFACT",
                        cc_list=["ca"], ref_id=1)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        msg = mb["messages"][0]
        assert msg["cc"] == ["ca"]
        assert msg["ref"] == 1
        assert msg["type"] == "ARTIFACT"

    def test_check_includes_cc_messages(self, ai_dir):
        hub.action_send(ai_dir, "ca", "cc", "verify result",
                        msg_type="VERIFY", cc_list=["gc"])
        # gc should see this message (it's cc'd)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        msgs = mb["messages"]
        gc_visible = [m for m in msgs
                      if m.get("to") == "gc" or "gc" in m.get("cc", [])]
        assert len(gc_visible) == 1

    def test_check_cc_filter_in_action(self, ai_dir, capsys):
        hub.action_send(ai_dir, "ca", "cc", "verify result",
                        msg_type="VERIFY", cc_list=["gc"])
        hub.action_check(ai_dir, "gc")
        out = capsys.readouterr().out
        assert "verify result" in out

    def test_backward_compat_old_format(self, ai_dir):
        hub.action_send(ai_dir, "cc", "gc", "old style msg")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        msg = mb["messages"][0]
        assert msg["type"] == "MSG"
        assert msg["cc"] == []
        assert msg["ref"] is None
        assert msg["thread_id"].startswith("t-")

    def test_send_records_priority_from_policy_default(self, ai_dir):
        hub.action_send(ai_dir, "cc", "gc", "policy priority")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["messages"][0]["priority"] == "INFO"

    def test_send_prunes_expired_messages_by_priority(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "messaging": {
                "send": {
                    "default_priority": "INFO",
                    "ttl_hours_by_priority": {"INFO": 4},
                }
            }
        })
        (ai_dir / "mailbox.json").write_text(json.dumps({
            "messages": [{
                "id": 1,
                "thread_id": "t-old",
                "type": "MSG",
                "from": "cc",
                "to": "gc",
                "content": "old",
                "status": "unread",
                "timestamp": "2000-01-01T00:00:00",
                "priority": "INFO",
            }],
            "unread_count": 1,
        }), encoding="utf-8")
        hub.action_send(ai_dir, "cc", "gc", "fresh")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert [m["content"] for m in mb["messages"]] == ["fresh"]

    def test_broadcast_fans_out_to_room_members_except_sender(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "is_routable", lambda peer: True)
        hub.action_init_session(ai_dir, "cc", "room-broadcast")
        hub.action_init_session(ai_dir, "gc", "room-broadcast")
        hub.action_init_session(ai_dir, "ag", "room-broadcast")
        hub.action_broadcast(ai_dir, "cc", "notice")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert [m["to"] for m in mb["messages"]] == ["gc", "ag"]
        assert len({m["thread_id"] for m in mb["messages"]}) == 1

    def test_broadcast_large_payload_uses_single_shared_file(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "_LARGE_PAYLOAD_THRESHOLD", 10)
        monkeypatch.setattr(hub, "is_routable", lambda peer: True)
        hub.action_init_session(ai_dir, "cc", "room-broadcast")
        hub.action_init_session(ai_dir, "gc", "room-broadcast")
        hub.action_init_session(ai_dir, "ag", "room-broadcast")
        hub.action_broadcast(ai_dir, "cc", "x" * 50)
        payloads = list((ai_dir / "payloads").glob("*.json"))
        assert len(payloads) == 1
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert {m["content"] for m in mb["messages"]} == {f"payload://{payloads[0].stem}"}

    def test_broadcast_filters_unroutable_room_members(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "is_routable", lambda peer: peer != "gc")
        hub.action_init_session(ai_dir, "cc", "room-broadcast")
        hub.action_init_session(ai_dir, "gc", "room-broadcast")
        hub.action_init_session(ai_dir, "ag", "room-broadcast")
        hub.action_broadcast(ai_dir, "cc", "notice")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert [m["to"] for m in mb["messages"]] == ["ag"]

    def test_send_prunes_orphaned_payload_files(self, ai_dir, monkeypatch):
        monkeypatch.setattr(hub, "_load_lifecycle_policy", lambda: {
            "messaging": {
                "send": {
                    "default_priority": "INFO",
                    "ttl_hours_by_priority": {"INFO": 4},
                }
            }
        })
        payload_dir = ai_dir / "payloads"
        payload_dir.mkdir()
        (payload_dir / "p-old.json").write_text("{}", encoding="utf-8")
        (ai_dir / "mailbox.json").write_text(json.dumps({
            "messages": [{
                "id": 1,
                "thread_id": "t-old",
                "type": "PAYLOAD_REF",
                "from": "cc",
                "to": "gc",
                "content": "payload://p-old",
                "status": "unread",
                "timestamp": "2000-01-01T00:00:00",
                "priority": "INFO",
            }],
            "unread_count": 1,
        }), encoding="utf-8")
        hub.action_send(ai_dir, "cc", "gc", "fresh")
        assert not (payload_dir / "p-old.json").exists()


# ─── §P-3 만장일치 협의 프로토콜 ─────────────────────────────
class TestConsensusProtocol:
    def test_propose_creates_round(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Test subject", ["cc", "ca", "gc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        assert len(rounds) == 1
        r = json.loads(rounds[0].read_text("utf-8"))
        assert r["subject"] == "Test subject"
        assert r["status"] == "voting"
        assert set(r["voters"]) == {"cc", "ca", "gc"}
        assert all(v is None for v in r["votes"].values())

    def test_vote_unanimous_finalized(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Approve X", ["cc", "ca", "gc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree", "")
        hub.action_consensus_vote(ai_dir, rid, "ca", "agree", "")
        hub.action_consensus_vote(ai_dir, rid, "gc", "agree", "")

        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "finalized"
        assert r["outcome"] == "unanimous"

        out = capsys.readouterr().out
        assert "FINALIZED" in out
        assert "unanimous" in out

    def test_vote_disagree_escalated(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Risky change", ["cc", "ca", "gc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree", "")
        hub.action_consensus_vote(ai_dir, rid, "ca", "disagree", "too risky")
        hub.action_consensus_vote(ai_dir, rid, "gc", "agree", "")

        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "escalated"
        assert r["outcome"] == "human_gate"

    def test_vote_partial_still_voting(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Partial vote", ["cc", "ca", "gc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree", "")
        # Only 1/3 voted — should still be voting
        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "voting"

    def test_consensus_check_all_rounds(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Round 1", ["cc", "ca"], "cc")
        hub.action_consensus_propose(ai_dir, "Round 2", ["cc", "gc"], "cc")
        hub.action_consensus_check(ai_dir, None)
        out = capsys.readouterr().out
        assert "Round 1" in out
        assert "Round 2" in out

    def test_consensus_check_specific_round(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Specific", ["cc", "ca", "gc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        hub.action_consensus_check(ai_dir, rid)
        out = capsys.readouterr().out
        assert "Specific" in out

    def test_invalid_voter_rejected(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Closed vote", ["cc", "ca"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "unknown_node", "agree", "")

    def test_vote_on_closed_round_rejected(self, ai_dir):
        hub.action_consensus_propose(ai_dir, "Quick", ["cc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        hub.action_consensus_vote(ai_dir, rid, "cc", "agree", "")  # finalized
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "cc", "agree", "")  # already closed

    def test_vote_invalid_value_rejected(self, ai_dir):
        hub.action_consensus_propose(ai_dir, "Test", ["cc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "cc", "typo_value", "")

    def test_vote_empty_value_rejected(self, ai_dir):
        hub.action_consensus_propose(ai_dir, "Test2", ["cc"], "cc")
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[-1].read_text("utf-8"))["round_id"]
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "cc", "", "")


# ─── §P-7 N-Node 등록 ─────────────────────────────────────────
class TestNodeManagement:
    def test_list_nodes_shows_defaults(self, ai_dir, capsys):
        hub.action_list_nodes(ai_dir)
        out = capsys.readouterr().out
        assert "cc" in out
        assert "ag" in out
        assert "cx" in out
        assert "gc:" not in out
        assert "ca:" not in out

    def test_register_new_node(self, ai_dir, capsys):
        hub.action_register_node(ai_dir, "n1", 4, "sensor",
                                  "custom-cli", "-p,{query}", "session", 0)
        data = json.loads((ai_dir / "nodes.json").read_text("utf-8"))
        assert "n1" in data["nodes"]
        assert data["nodes"]["n1"]["tier"] == 4

    def test_register_node_console_output(self, ai_dir, capsys):
        hub.action_register_node(ai_dir, "n2", 4, "agent",
                                  "custom", "-p,{query}", "short-term", 0)
        out = capsys.readouterr().out
        assert "REGISTER" in out
        assert "n2" in out


class TestLifecycleActions:
    def test_health_update_closes_and_reopens_gate(self, tmp_path, monkeypatch):
        peer_dir = tmp_path / "_sys" / "gemini"
        peer_dir.mkdir(parents=True)
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)

        hub.action_health_update("gc", "RED", 0.0, 0)
        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "RED"
        assert health["availability"]["gate_open"] is False
        assert health["availability"]["entrypoint_ok"] is False

        hub.action_health_update("gc", "GREEN", 0.0, 0)
        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "GREEN"
        assert health["availability"]["gate_open"] is True
        assert health["availability"]["entrypoint_ok"] is True

    def test_health_precheck_fails_explicit_stale_peer(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "_sys" / "gemini"
        peer_dir.mkdir(parents=True)
        (peer_dir / "health.json").write_text(json.dumps({
            "peer_id": "gc",
            "context_health": {"status": "GREEN", "checked_at": "20000101T000000"},
            "availability": {"gate_open": True},
        }), encoding="utf-8")
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        monkeypatch.setattr(hub, "_load_orchestration", lambda: {
            "hub_nodes": [{"node_id": "gc"}]
        })
        monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {
            "leader_election": {"health_stale_minutes": 1}
        })

        with pytest.raises(SystemExit) as exc:
            hub.action_health_precheck(ai_dir, peers="gc")
        assert exc.value.code == 1

    def test_peer_quarantine_and_recover_update_health_and_handoff(self, ai_dir, tmp_path, monkeypatch):
        peer_dir = tmp_path / "gemini"
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        hub.action_init_session(ai_dir, "gc", "room-life")
        hub.action_peer_quarantine(ai_dir, "gc", "quota")

        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "RED"
        assert health["availability"]["gate_open"] is False
        assert health["availability"]["quarantined"] is True

        handoff = (ai_dir / "sessions" / "room-life" / "handoff.md").read_text("utf-8")
        assert "quarantined" in handoff

        hub.action_peer_recover(ai_dir, "gc", "manual")
        health = json.loads((peer_dir / "health.json").read_text("utf-8"))
        assert health["context_health"]["status"] == "GREEN"
        assert health["availability"]["gate_open"] is True
        assert health["availability"]["quarantined"] is False

    def test_new_topic_archives_and_carries_key_decisions(self, ai_dir):
        hub.action_init_session(ai_dir, "cc", "room-old")
        hub.action_init_session(ai_dir, "gc", "room-old")
        old_dir = ai_dir / "sessions" / "room-old"
        hub._write_handoff(old_dir, {
            "GOAL": ["old goal"],
            "RECENT_COMPLETED": ["done"],
            "PENDING_ISSUES": ["old issue"],
            "KEY_DECISIONS": ["keep this"],
            "CONSENSUS_HISTORY": [],
            "ACTIVE_THREADS": ["old active"],
        })

        hub.action_new_topic(ai_dir, "new mission")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["room_id"] != "room-old"
        assert set(state["members"].keys()) == {"cc", "gc"}
        assert state["mission"] == "new mission"

        handoff = (ai_dir / "sessions" / state["room_id"] / "handoff.md").read_text("utf-8")
        assert "new mission" in handoff
        assert "keep this" in handoff
        assert "old issue" not in handoff
        archives = list((ai_dir.parent / "_archive" / "rooms").glob("*room-old_handoff.md"))
        assert archives

    def test_clear_room_archives_mailbox_and_resets_state(self, ai_dir):
        hub.action_init_session(ai_dir, "cc", "room-clear")
        hub.action_init_session(ai_dir, "ag", "room-clear")
        hub.action_send(ai_dir, "cc", "ag", "queued")

        hub.action_clear_room(ai_dir, "fresh start")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["room_id"] != "room-clear"
        assert set(state["members"].keys()) == {"cc", "ag"}
        assert state["phase"] == "clear-room"
        mailbox = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mailbox == {"messages": [], "unread_count": 0}
        archives = list((ai_dir.parent / "_archive" / "mailbox").glob("*room-clear_mailbox.json"))
        assert archives


class TestOperationalGuard:
    def test_preflight_blocks_bash_heredoc_in_powershell(self):
        result = hub._classify_command("python <<'PY'\nprint('x')\nPY", "powershell")
        assert result["classification"] == "blocked_shell_mismatch"
        assert result["allowed"] is False
        assert result["matched_rule"] == "bash_heredoc"

    def test_preflight_unknown_requires_classification(self):
        result = hub._classify_command("custom-tool --maybe-write", "powershell")
        assert result["classification"] == "requires_classification"
        assert result["allowed"] is False

    def test_preflight_allows_read_only_rg(self):
        result = hub._classify_command("rg -n \"pattern\" _sys", "powershell")
        assert result["classification"] == "read_only"
        assert result["allowed"] is True

    def test_guard_blocks_mutating_action_in_no_code_phase(self, ai_dir):
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        state["phase"] = "discussion_no_code"
        (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            hub._guard_action(ai_dir, "send")
        assert exc.value.code == 3

    def test_guard_allows_tier0_force(self, ai_dir):
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        state["phase"] = "discussion_no_code"
        (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        hub._guard_action(ai_dir, "send", force_tier0=True)

    def test_guard_allows_recovery_action_in_no_code_phase(self, ai_dir):
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        state["phase"] = "discussion_no_code"
        (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        hub._guard_action(ai_dir, "peer-recover")

    def test_context_hash_normalizes_line_endings(self, ai_dir):
        hub.action_init_session(ai_dir, "cc", "room-hash")
        handoff = ai_dir / "sessions" / "room-hash" / "handoff.md"
        handoff.write_bytes(b"A\r\nB\r\n")
        first = hub._compute_context_hash(ai_dir)
        handoff.write_bytes(b"A\nB\n")
        second = hub._compute_context_hash(ai_dir)
        assert first == second

    def test_context_ack_writes_peer_hash(self, ai_dir):
        hub.action_init_session(ai_dir, "cc", "room-ack")
        hub.action_context_ack(ai_dir, "gc", "abc123")
        data = json.loads((ai_dir / "context_ack.json").read_text("utf-8"))
        assert data["gc"]["hash"] == "abc123"
        assert data["gc"]["room_id"] == "room-ack"

    def test_report_error_quarantines_after_threshold(self, ai_dir, monkeypatch):
        quarantined = []
        monkeypatch.setattr(hub, "_operational_guard_cfg", lambda: {
            "error_memory": {
                "path": "operational_errors.jsonl",
                "quarantine_after": 2,
                "manual_recovery_only": True,
            }
        })
        monkeypatch.setattr(hub, "_read_peer_health", lambda peer: (None, {}))
        monkeypatch.setattr(hub, "_write_peer_health", lambda peer, data, root: quarantined.append((peer, data)))
        hub.action_report_error(ai_dir, "gc", "bash_heredoc", "bad shell")
        hub.action_report_error(ai_dir, "gc", "bash_heredoc", "bad shell")
        assert quarantined[-1][0] == "gc"
        assert quarantined[-1][1]["availability"]["quarantined"] is True

    def test_collab_rate_guard_blocks_mutation_without_finalized_consensus(self, ai_dir):
        with pytest.raises(SystemExit) as exc:
            # register-node is a mutating action and is NOT in the exempt list in protocol.json
            hub._guard_action(ai_dir, "register-node")
        assert exc.value.code == 3

    def test_collab_rate_guard_allows_after_finalized_consensus(self, ai_dir):
        (ai_dir / "consensus" / "r-ok.json").write_text(json.dumps({
            "round_id": "r-ok",
            "status": "finalized",
            "subject": "approve mutation",
        }), encoding="utf-8")
        hub._guard_action(ai_dir, "update-status")


class TestEnhancedCollaboration:
    def test_ask_quiet_output_file_writes_response(self, ai_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(hub, "_runtime_cfg", lambda: {"ask_default_timeout_sec": 7})
        peer_dir = tmp_path / "_sys" / "codex"
        peer_dir.mkdir(parents=True)
        (peer_dir / "health.json").write_text(json.dumps({
            "peer_id": "cx",
            "context_health": {"status": "GREEN", "checked_at": "29990101T000000"},
            "availability": {"gate_open": True},
        }), encoding="utf-8")
        monkeypatch.setattr(hub, "_peer_sys_dir", lambda peer_id: peer_dir)
        mock_proc = _make_mock_proc(stdout=b"model response")
        out = tmp_path / "reply.md"
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=mock_proc):
            hub.action_ask("cx", "hello", None, 0, ai_dir, quiet=True, output_file=str(out))
        assert out.read_text("utf-8") == "model response"
        assert capsys.readouterr().out == ""
        # timeout_sec=0 means unlimited; communicate gets heartbeat_sec (30s) for process-death polling
        communicate_timeout = mock_proc.communicate.call_args.kwargs.get("timeout", 0)
        assert communicate_timeout == 30

    def test_feedback_add_list_resolve(self, ai_dir, capsys):
        hub.action_feedback_add(ai_dir, "cx", "runtime", "high", "Need quiet mode", "details")
        data = [json.loads(line) for line in (ai_dir / "feedback.jsonl").read_text("utf-8").splitlines()]
        fid = data[0]["id"]
        assert data[0]["status"] == "open"
        hub.action_feedback_list(ai_dir)
        assert "Need quiet mode" in capsys.readouterr().out
        hub.action_feedback_resolve(ai_dir, fid, "done", "cc")
        data = [json.loads(line) for line in (ai_dir / "feedback.jsonl").read_text("utf-8").splitlines()]
        assert data[0]["status"] == "done"
        assert data[0]["owner"] == "cc"

    def test_directive_add_list_clear(self, ai_dir, capsys, tmp_path):
        """directive-add, directive-list, directive-clear 사이클 검증."""
        rd_path = tmp_path / "runtime-directives.jsonl"
        with patch.object(hub, "_runtime_directives_path", return_value=rd_path):
            hub.action_directive_add(ai_dir, "Never do X", "cc", ttl_hours=6, clear_condition="manual")
            active = hub._get_active_runtime_directives(rd_path)
            assert len(active) == 1
            assert active[0]["rule"] == "Never do X"
            assert active[0]["status"] == "active"
            hub.action_directive_list(ai_dir)
            assert "Never do X" in capsys.readouterr().out
            hub.action_directive_clear(ai_dir, active[0]["id"])
            assert hub._get_active_runtime_directives(rd_path) == []

    def test_auto_promote_runtime_directive_on_repeated_failure(self, ai_dir, tmp_path):
        """동일 이유 실패 2회 연속 시 runtime directive 자동 생성."""
        rd_path = tmp_path / "runtime-directives.jsonl"
        health_dir = tmp_path / "gc_health"
        health_dir.mkdir()
        # Isolate HubError.report from sys.exit so the test can assert on directive state
        with patch.object(hub, "_runtime_directives_path", return_value=rd_path), \
             patch("hub_error.HubError.report", return_value=None):
            hub._record_ask_failure("gc", "rate_limit", "quota exceeded", 5, ai_dir, health_dir=health_dir)
            assert hub._get_active_runtime_directives(rd_path) == []
            hub._record_ask_failure("gc", "rate_limit", "quota exceeded", 5, ai_dir, health_dir=health_dir)
            active = hub._get_active_runtime_directives(rd_path)
            assert len(active) == 1
            assert "gc" in active[0]["rule"]
            assert active[0]["trigger_reason"] == "rate_limit"

    def test_first_success_clears_runtime_directive(self, ai_dir, tmp_path):
        """성공 시 first_success 조건 directive 자동 클리어."""
        rd_path = tmp_path / "runtime-directives.jsonl"
        health_dir = tmp_path / "gc_health"
        health_dir.mkdir()
        # health.json 없음 → last_failure_reason=None(기본값) → 클린 상태
        with patch.object(hub, "_runtime_directives_path", return_value=rd_path):
            hub._save_runtime_directive(rd_path, "caution gc", "gc", "timeout", "", 6, "first_success")
            assert len(hub._get_active_runtime_directives(rd_path)) == 1
            hub._record_ask_success("gc", 10, ai_dir, health_dir=health_dir)
            assert hub._get_active_runtime_directives(rd_path) == []

    def test_success_recovers_stale_health(self, ai_dir, tmp_path):
        health_dir = tmp_path / "cc_health"
        health_dir.mkdir()
        (health_dir / "health.json").write_text(
            json.dumps({
                "context_health": {"status": "STALE"},
                "session_health": {"last_failure_reason": None},
                "availability": {"gate_open": True},
            }),
            encoding="utf-8",
        )

        hub._record_ask_success("cc", 1, ai_dir, health_dir=health_dir)

        health = json.loads(
            (health_dir / "health.json").read_text(encoding="utf-8")
        )
        assert health["context_health"]["status"] == "GREEN"

    def test_success_clears_obsolete_stale_handoff_issue(self, ai_dir, tmp_path):
        health_dir = tmp_path / "cx_health"
        health_dir.mkdir()
        (health_dir / "health.json").write_text(
            json.dumps({
                "context_health": {"status": "STALE"},
                "session_health": {"last_failure_reason": None},
                "availability": {"gate_open": True},
            }),
            encoding="utf-8",
        )
        state = json.loads((ai_dir / "state.json").read_text(encoding="utf-8"))
        state["room_id"] = "room-health"
        (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        session_dir = ai_dir / "sessions" / "room-health"
        session_dir.mkdir()
        hub._write_handoff(
            session_dir,
            {
                "PENDING_ISSUES": [
                    "2026-06-20 cx: health marked STALE by health-sweep",
                    "keep this issue",
                ]
            },
        )

        hub._record_ask_success("cx", 1, ai_dir, health_dir=health_dir)

        handoff = hub._read_handoff(session_dir)
        assert handoff["PENDING_ISSUES"] == ["keep this issue"]

    def test_target_peers_filters_directive_injection(self, ai_dir, tmp_path):
        """target_peers 필드: cc-only directive는 gc ask에 주입되지 않음."""
        rd_path = tmp_path / "runtime-directives.jsonl"
        with patch.object(hub, "_runtime_directives_path", return_value=rd_path):
            # broadcast directive (no target_peers)
            hub._save_runtime_directive(rd_path, "global rule", "system", "manual", "", target_peers=None)
            # cc-only directive
            hub._save_runtime_directive(rd_path, "cc-only rule", "gc", "rate_limit", "", target_peers=["cc"])
            active = hub._get_active_runtime_directives(rd_path)
            assert len(active) == 2

        # Inject context for gc → only global rule visible
        state_path = ai_dir / "state.json"
        import json as _json
        state = _json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
        if not state.get("room_id"):
            state["room_id"] = "room-test"
            state["members"] = {"cc": {}, "gc": {}}
            state_path.write_text(_json.dumps(state), encoding="utf-8")
        room_dir = ai_dir / "sessions" / state["room_id"]
        room_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(hub, "_runtime_directives_path", return_value=rd_path):
            ctx_gc = hub._build_ask_query_with_context(ai_dir, "hello", to_peer="gc")
            ctx_cc = hub._build_ask_query_with_context(ai_dir, "hello", to_peer="cc")

        assert "global rule" in ctx_gc
        assert "cc-only rule" not in ctx_gc
        assert "global rule" in ctx_cc
        assert "cc-only rule" in ctx_cc

    def test_artifact_claim_register_and_finalize(self, ai_dir, tmp_path, capsys):
        result = tmp_path / "Result.md"
        result.write_text("final", encoding="utf-8")
        hub.action_artifact_claim(ai_dir, "Result.md", "gc")
        hub.action_artifact_status(ai_dir, "Result.md", "cc", ".ai/artifacts/Result.cc.md")
        hub.action_artifact_finalize(ai_dir, "Result.md", str(result))
        data = json.loads((ai_dir / "artifacts.json").read_text("utf-8"))
        item = data["Result.md"]
        assert item["owner"] == "gc"
        assert item["drafts"]["cc"] == ".ai/artifacts/Result.cc.md"
        assert item["status"] == "finalized"
        assert item["hash"].startswith("sha256:")


# ─── knowledge propagation ──────────────────────────────────
class TestKnowledgePropagation:
    """knowledge-propagation-spec.md 구현 테스트."""

    def _make_lessons_jsonl(self, path: Path, lessons: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(l) for l in lessons) + "\n", encoding="utf-8")

    def _seed_lesson(self, **kwargs) -> dict:
        base = {
            "id": "LL-TEST-001", "schema_version": 1, "status": "active",
            "severity": "high", "title": "Test lesson", "compact_rule": "Do X not Y.",
            "category": "shell-dialect", "scope": "global",
            "applies_to": {"peer_ids": None, "os": None, "shell": None, "task_types": None},
            "source_refs": [{"type": "debate", "id": "test", "peer": "cc", "ts": "20260614T000000"}],
            "approval": {"approved_by": "coordinator", "approved_at": "20260614T000000", "record_ref": None},
            "retirement": {"expires_at": None, "superseded_by": None, "review_after": None},
        }
        base.update(kwargs)
        return base

    def test_load_active_lessons_global_only(self, tmp_path):
        """글로벌 lessons 파일에서 active 항목만 로드."""
        lessons_dir = tmp_path / "general"
        lessons_path = lessons_dir / "active-lessons.jsonl"
        active = self._seed_lesson(id="LL-A", status="active")
        retired = self._seed_lesson(id="LL-R", status="retired")
        self._make_lessons_jsonl(lessons_path, [active, retired])

        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            result = hub._load_active_lessons(workspace_ai_root=None)

        assert len(result) == 1
        assert result[0]["id"] == "LL-A"

    def test_load_active_lessons_merges_workspace(self, tmp_path):
        """workspace-local lesson이 global에 추가됨 (중복 ID 제외)."""
        global_dir = tmp_path / "general"
        global_path = global_dir / "active-lessons.jsonl"
        self._make_lessons_jsonl(global_path, [self._seed_lesson(id="LL-G")])

        ws_knowledge = tmp_path / "ws" / "knowledge"
        ws_path = ws_knowledge / "active-lessons.jsonl"
        self._make_lessons_jsonl(ws_path, [
            self._seed_lesson(id="LL-WS"),
            self._seed_lesson(id="LL-G"),  # 중복 — 무시돼야 함
        ])

        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            result = hub._load_active_lessons(workspace_ai_root=tmp_path / "ws")

        ids = [l["id"] for l in result]
        assert "LL-G" in ids
        assert "LL-WS" in ids
        assert ids.count("LL-G") == 1  # 중복 없음

    def test_filter_lessons_by_peer_id(self, tmp_path):
        """applies_to.peer_ids 필터: 해당 피어만 받음."""
        cc_only = self._seed_lesson(id="LL-CC", applies_to={"peer_ids": ["cc"], "os": None, "shell": None, "task_types": None})
        all_peers = self._seed_lesson(id="LL-ALL", applies_to={"peer_ids": None, "os": None, "shell": None, "task_types": None})

        with patch.object(hub, "_knowledge_config", return_value={}):
            gc_lessons = hub._filter_lessons_for_peer([cc_only, all_peers], "gc")

        assert len(gc_lessons) == 1
        assert gc_lessons[0]["id"] == "LL-ALL"

    def test_filter_lessons_by_severity(self, tmp_path):
        """min_severity=medium → low 제외."""
        high = self._seed_lesson(id="LL-H", severity="high")
        low = self._seed_lesson(id="LL-L", severity="low")

        with patch.object(hub, "_knowledge_config", return_value={"filters": {"min_severity_default": "medium"}}):
            result = hub._filter_lessons_for_peer([high, low], "cc")

        ids = [l["id"] for l in result]
        assert "LL-H" in ids
        assert "LL-L" not in ids

    def test_compile_lessons_block_renders(self, tmp_path):
        """lessons_block 렌더링: [PEER LESSONS] 헤더 + 규칙 포함."""
        lessons = [self._seed_lesson(id="LL-X", compact_rule="Never do Z.")]
        with patch.object(hub, "_knowledge_config", return_value={
            "delivery": {"enabled": True, "max_chars": 2000, "max_items": 8,
                         "critical_always_include": True, "overflow_policy": "show_count_and_pointer"}
        }):
            block = hub._compile_lessons_block(lessons)

        assert block is not None
        assert "[PEER LESSONS]" in block
        assert "Never do Z." in block

    def test_compile_lessons_block_overflow(self, tmp_path):
        """max_items 초과 시 Omitted 메시지 표시."""
        lessons = [self._seed_lesson(id=f"LL-{i}", compact_rule=f"Rule {i}.") for i in range(10)]
        with patch.object(hub, "_knowledge_config", return_value={
            "delivery": {"enabled": True, "max_chars": 99999, "max_items": 3,
                         "critical_always_include": False, "overflow_policy": "show_count_and_pointer"}
        }):
            block = hub._compile_lessons_block(lessons)

        assert "Omitted:" in block

    def test_compile_lessons_block_disabled(self, tmp_path):
        """delivery.enabled=false → None 반환."""
        lessons = [self._seed_lesson()]
        with patch.object(hub, "_knowledge_config", return_value={"delivery": {"enabled": False}}):
            block = hub._compile_lessons_block(lessons)
        assert block is None

    def test_lessons_injected_into_context(self, ai_dir, tmp_path):
        """to_peer 있을 때 [PEER LESSONS] 블록이 컨텍스트에 주입됨."""
        import json as _json
        state = {"room_id": "room-kp", "members": {"cc": {}, "gc": {}}}
        (ai_dir / "state.json").write_text(_json.dumps(state), encoding="utf-8")
        (ai_dir / "sessions" / "room-kp").mkdir(parents=True, exist_ok=True)

        lesson = self._seed_lesson(id="LL-INJ", compact_rule="Injected rule.")
        with patch.object(hub, "_load_active_lessons", return_value=[lesson]), \
             patch.object(hub, "_filter_lessons_for_peer", return_value=[lesson]), \
             patch.object(hub, "_compile_lessons_block", return_value="[PEER LESSONS]\n- HIGH LL-INJ: Injected rule."):
            ctx = hub._build_ask_query_with_context(ai_dir, "hello", to_peer="gc")

        assert "[PEER LESSONS]" in ctx
        assert "Injected rule." in ctx

    def test_lessons_not_injected_without_to_peer(self, ai_dir, tmp_path):
        """to_peer 없으면 [PEER LESSONS] 블록 주입 안 됨."""
        import json as _json
        state = {"room_id": "room-kp2", "members": {"cc": {}}}
        (ai_dir / "state.json").write_text(_json.dumps(state), encoding="utf-8")
        (ai_dir / "sessions" / "room-kp2").mkdir(parents=True, exist_ok=True)

        ctx = hub._build_ask_query_with_context(ai_dir, "hello", to_peer=None)
        assert "[PEER LESSONS]" not in ctx

    def test_lessons_propose_and_activate(self, ai_dir, tmp_path, capsys):
        """propose → candidate, activate → active 흐름 검증."""
        # _knowledge_root() / "general" / "active-lessons.jsonl"
        lessons_path = tmp_path / "general" / "active-lessons.jsonl"
        lessons_path.parent.mkdir(parents=True, exist_ok=True)
        lessons_path.write_text("", encoding="utf-8")
        (tmp_path / "logs").mkdir(exist_ok=True)

        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            hub.action_lessons_propose(
                ai_dir, title="Test rule", rule="Never do X.", category="shell-dialect",
                severity="high", scope="global", peer_ids=["cc"],
            )

        lines = [json.loads(l) for l in lessons_path.read_text("utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        lesson_id = lines[0]["id"]
        assert lines[0]["status"] == "candidate"

        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            hub.action_lessons_activate(ai_dir, lesson_id=lesson_id)

        lines2 = [json.loads(l) for l in lessons_path.read_text("utf-8").splitlines() if l.strip()]
        assert lines2[0]["status"] == "active"
        assert lines2[0]["approval"]["approved_by"] == "coordinator"

    def test_lessons_retire(self, ai_dir, tmp_path, capsys):
        """active lesson → retired."""
        lessons_path = tmp_path / "general" / "active-lessons.jsonl"
        lesson = self._seed_lesson(id="LL-RET")
        self._make_lessons_jsonl(lessons_path, [lesson])

        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            hub.action_lessons_retire(ai_dir, lesson_id="LL-RET", reason="no longer relevant")

        result = json.loads(lessons_path.read_text("utf-8").splitlines()[0])
        assert result["status"] == "retired"
        assert result["retirement"]["retire_reason"] == "no longer relevant"

    def test_lessons_invalid_json_skipped(self, tmp_path):
        """잘못된 JSON 라인 무시."""
        global_dir = tmp_path / "general"
        global_path = global_dir / "active-lessons.jsonl"
        global_path.parent.mkdir(parents=True, exist_ok=True)
        global_path.write_text(
            '{"id":"LL-OK","status":"active","severity":"high","compact_rule":"ok","category":"x","scope":"global","applies_to":{},"source_refs":[{"ts":"20260614T000000"}],"approval":{},"retirement":{}}\n'
            'NOT VALID JSON\n'
            '\n',
            encoding="utf-8"
        )
        with patch.object(hub, "_knowledge_root", return_value=tmp_path):
            result = hub._load_active_lessons(workspace_ai_root=None)
        assert len(result) == 1
        assert result[0]["id"] == "LL-OK"


class TestContextFillFrame:
    def _seed_room(self, ai_dir):
        room = "room-frametest"
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        state["room_id"] = room
        (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        sess = ai_dir / "sessions" / room
        sess.mkdir(parents=True, exist_ok=True)
        (sess / "handoff.md").write_text(
            "## [GOAL]\nResetting blocked consensus and taking over\n", encoding="utf-8")

    def test_bare_output_has_no_neutralizer(self, ai_dir, capsys):
        self._seed_room(ai_dir)
        hub.action_context_fill(ai_dir, ["GOAL"])           # frame defaults False
        bare = capsys.readouterr().out
        assert "REFERENCE STATE" not in bare
        assert bare.startswith("<!-- context-fill")

    def test_framed_prepends_neutralizer_only(self, ai_dir, capsys):
        self._seed_room(ai_dir)
        hub.action_context_fill(ai_dir, ["GOAL"])
        bare = capsys.readouterr().out
        hub.action_context_fill(ai_dir, ["GOAL"], frame=True)
        framed = capsys.readouterr().out
        assert framed.startswith("> REFERENCE STATE")
        neutralizer, _, body = framed.partition("\n")
        assert body == bare                 # bare path byte-identical
        assert "NOT a task" in neutralizer


class TestEphemeralQueryFile:
    def _mk(self, d, name):
        d.mkdir(parents=True, exist_ok=True)
        f = d / name; f.write_text("x", encoding="utf-8"); return f

    def test_ipc_autoname_is_ephemeral(self, tmp_path):
        f = self._mk(tmp_path / "ipc", "cc-20260621223000-ab12.txt")
        assert hub._is_ephemeral_query_file(f) is True

    def test_profile_suffixed_autoname_is_ephemeral(self, tmp_path):
        f = self._mk(tmp_path / "ipc", "cc.deepthink-20260621223000-ab12.txt")
        assert hub._is_ephemeral_query_file(f) is True

    def test_ask_all_tempfile_is_ephemeral(self, tmp_path):
        f = self._mk(tmp_path, "hub-ask-all-cx-deadbeef.txt")
        assert hub._is_ephemeral_query_file(f) is True

    def test_named_staged_file_is_preserved(self, tmp_path):
        f = self._mk(tmp_path / "ipc", "cx-ratify-pro19-arch07.txt")
        assert hub._is_ephemeral_query_file(f) is False

    def test_autoname_outside_ipc_is_preserved(self, tmp_path):
        f = self._mk(tmp_path / "notipc", "cc-20260621223000-ab12.txt")
        assert hub._is_ephemeral_query_file(f) is False

    def test_custom_multi_profile_autoname_is_ephemeral(self, tmp_path):
        f = self._mk(
            tmp_path / "ipc",
            "cx-worker.review.deep_think-20260621223000-ab12.txt",
        )
        assert hub._is_ephemeral_query_file(f) is True

    def test_ask_deletes_custom_profile_autoname(self, tmp_path):
        ipc_dir = tmp_path / "ipc"
        ipc_dir.mkdir()
        qf = ipc_dir / "cx-worker.review.deep_think-20260621223000-ab12.txt"
        qf.write_text("query", encoding="utf-8")
        proc = _make_mock_proc(stdout=b"response")

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=proc):
            hub.action_ask("cx", "", str(qf), 120, None)

        assert not qf.exists()

    def test_ask_preserves_named_custom_profile_file(self, tmp_path):
        ipc_dir = tmp_path / "ipc"
        ipc_dir.mkdir()
        qf = ipc_dir / "cx-worker.review.deep_think-ratify-pro19.txt"
        qf.write_text("query", encoding="utf-8")
        proc = _make_mock_proc(stdout=b"response")

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.Popen", return_value=proc):
            hub.action_ask("cx", "", str(qf), 120, None)

        assert qf.exists()
