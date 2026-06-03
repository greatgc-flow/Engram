"""hub.py 11개 액션 단위 테스트 (ask 포함, --format llm 제거됨)."""
import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import hub


# ─── init-session ───────────────────────────────────────────
class TestInitSession:
    def test_claude_creates_sid(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "claude")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["claude_sid"] is not None
        assert state["claude_sid"].startswith("c")

    def test_gemini_creates_sid(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "gemini")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["gemini_sid"] is not None
        assert state["gemini_sid"].startswith("g")

    def test_pair_format(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "claude")
        hub.action_init_session(ai_dir, "gemini")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        pair = state["pair"]
        assert pair.startswith("c")
        assert "-g" in pair

    def test_output_is_sid_only(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "claude")
        out = capsys.readouterr().out.strip()
        # SID만 출력 (단 1줄, 5자: prefix + 4 hex)
        assert len(out) == 5
        assert out.startswith("c")

    def test_session_dir_created(self, ai_dir):
        hub.action_init_session(ai_dir, "claude")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert (ai_dir / "sessions" / state["pair"]).exists()


# ─── send + check ────────────────────────────────────────────
class TestSendCheck:
    def test_send_creates_message(self, ai_dir):
        hub.action_send(ai_dir, "claude", "gemini", "hello")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert len(mb["messages"]) == 1
        assert mb["messages"][0]["content"] == "hello"
        assert mb["messages"][0]["status"] == "unread"
        assert mb["unread_count"] == 1

    def test_check_pretty_print(self, ai_dir, capsys):
        hub.action_send(ai_dir, "claude", "gemini", "full message content")
        hub.action_check(ai_dir, "gemini")
        out = capsys.readouterr().out
        assert "1 messages for gemini" in out   # 3TCP v1 [HUB] READ 형식
        assert "full message content" in out  # 전문 출력 확인

    def test_check_empty(self, ai_dir, capsys):
        hub.action_check(ai_dir, "claude")
        out = capsys.readouterr().out
        assert "inbox empty" in out

    def test_check_shows_all_messages(self, ai_dir, capsys):
        for i in range(3):
            hub.action_send(ai_dir, "gemini", "claude", f"msg content {i}")
        hub.action_check(ai_dir, "claude")
        out = capsys.readouterr().out
        assert "3 messages for claude" in out  # 3TCP v1 [HUB] READ 형식
        for i in range(3):
            assert f"msg content {i}" in out  # 전문 모두 출력


# ─── mark-read ───────────────────────────────────────────────
class TestMarkRead:
    def test_mark_all(self, ai_dir):
        hub.action_send(ai_dir, "claude", "gemini", "m1")
        hub.action_send(ai_dir, "claude", "gemini", "m2")
        hub.action_mark_read(ai_dir, "gemini", all_=True, msg_id=None)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 0

    def test_mark_by_id(self, ai_dir):
        hub.action_send(ai_dir, "claude", "gemini", "m1")
        hub.action_send(ai_dir, "claude", "gemini", "m2")
        hub.action_mark_read(ai_dir, "gemini", all_=False, msg_id=1)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 1


# ─── update-status + status ──────────────────────────────────
class TestStatus:
    def test_update_and_status(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "claude")
        capsys.readouterr()  # SID 출력 flush
        hub.action_update_status(ai_dir, "test mission", None, "2")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "SESSION STATUS" in out
        assert "test mission" in out
        assert "Phase" in out

    def test_status_shows_mailbox_counts(self, ai_dir, capsys):
        hub.action_send(ai_dir, "gemini", "claude", "hi claude")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "1 unread" in out

    def test_status_shows_handoff(self, ai_dir, capsys):
        hub.action_init_session(ai_dir, "claude")
        capsys.readouterr()
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        sd = ai_dir / "sessions" / state["pair"]
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "handoff.md").write_text("## [GOAL]\n- 테스트 목표\n", encoding="utf-8")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "HANDOFF" in out
        assert "테스트 목표" in out  # handoff 원문 전체 출력


# ─── end-session ─────────────────────────────────────────────
class TestEndSession:
    def test_end_cleans_read_messages(self, ai_dir):
        hub.action_init_session(ai_dir, "claude")
        hub.action_send(ai_dir, "gemini", "claude", "done")
        hub.action_mark_read(ai_dir, "claude", all_=True, msg_id=None)
        hub.action_end_session(ai_dir, "claude")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert len(mb["messages"]) == 0

    def test_end_updates_handoff(self, ai_dir):
        hub.action_init_session(ai_dir, "claude")
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        hub.action_end_session(ai_dir, "claude")
        handoff = (ai_dir / "sessions" / state["pair"] / "handoff.md").read_text("utf-8")
        assert "claude: 세션 종료" in handoff


# ─── ask (동기 subprocess) ───────────────────────────────────
class TestAsk:
    def test_ask_gemini_calls_subprocess(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = "Gemini raw response"
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            hub.action_ask("gemini", "test query")
            call_args = mock_run.call_args[0][0]
            assert "gemini" in call_args[0]
            assert "-p" in call_args
            assert "test query" in call_args

    def test_ask_claude_calls_subprocess(self, tmp_path):
        mock_result = MagicMock()
        mock_result.stdout = "Claude raw response"
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            hub.action_ask("claude", "test query")
            call_args = mock_run.call_args[0][0]
            assert "claude" in call_args[0]
            assert "-p" in call_args

    def test_ask_strips_ansi(self, capsys):
        mock_result = MagicMock()
        mock_result.stdout = "\x1b[32mcolored response\x1b[0m"
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.run", return_value=mock_result):
            hub.action_ask("gemini", "test")
        out = capsys.readouterr().out
        assert "\x1b" not in out
        assert "colored response" in out

    def test_ask_timeout_exits(self):
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gemini", 120)):
            with pytest.raises(SystemExit):
                hub.action_ask("gemini", "test")

    def test_ask_not_found_exits(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit):
                hub.action_ask("gemini", "test")

    def test_ask_query_file(self, tmp_path, capsys):
        qf = tmp_path / "query.txt"
        qf.write_text("file query content", encoding="utf-8")
        mock_result = MagicMock()
        mock_result.stdout = "response"
        mock_result.stderr = ""
        mock_result.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            hub.action_ask("gemini", "", str(qf))
            # 파일 내용이 쿼리로 전달됐는지 확인
            call_args = mock_run.call_args[0][0]
            assert "file query content" in call_args
        # 쿼리 파일 자동 삭제 확인
        assert not qf.exists()

    def test_ask_nonzero_exit_warns(self, capsys):
        mock_result = MagicMock()
        mock_result.stdout = "partial response"
        mock_result.stderr = "some error"
        mock_result.returncode = 1
        with patch("shutil.which", return_value="/usr/bin/gemini"), \
             patch("subprocess.run", return_value=mock_result):
            hub.action_ask("gemini", "test")
        out, err = capsys.readouterr()
        assert "[HUB:WARN] gemini exited 1" in err  # 3TCP v1 [HUB:WARN] 형식
        assert "partial response" in out


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
        hub.action_send(ai_dir, "claude", "gemini", "old style msg")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        msg = mb["messages"][0]
        assert msg["type"] == "MSG"
        assert msg["cc"] == []
        assert msg["ref"] is None
        assert msg["thread_id"].startswith("t-")


# ─── §P-3 만장일치 협의 프로토콜 ─────────────────────────────
class TestConsensusProtocol:
    def test_propose_creates_round(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Test subject", ["cc", "ca", "gc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        assert len(rounds) == 1
        r = json.loads(rounds[0].read_text("utf-8"))
        assert r["subject"] == "Test subject"
        assert r["status"] == "voting"
        assert set(r["voters"]) == {"cc", "ca", "gc"}
        assert all(v is None for v in r["votes"].values())

    def test_vote_unanimous_finalized(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Approve X", ["cc", "ca", "gc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree")
        hub.action_consensus_vote(ai_dir, rid, "ca", "agree")
        hub.action_consensus_vote(ai_dir, rid, "gc", "agree")

        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "finalized"
        assert r["outcome"] == "unanimous"

        out = capsys.readouterr().out
        assert "FINALIZED" in out
        assert "unanimous" in out

    def test_vote_disagree_escalated(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Risky change", ["cc", "ca", "gc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree")
        hub.action_consensus_vote(ai_dir, rid, "ca", "disagree", "too risky")
        hub.action_consensus_vote(ai_dir, rid, "gc", "agree")

        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "escalated"
        assert r["outcome"] == "human_gate"

    def test_vote_partial_still_voting(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Partial vote", ["cc", "ca", "gc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]

        hub.action_consensus_vote(ai_dir, rid, "cc", "agree")
        # Only 1/3 voted — should still be voting
        r = json.loads((ai_dir / "consensus" / f"{rid}.json").read_text("utf-8"))
        assert r["status"] == "voting"

    def test_consensus_check_all_rounds(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Round 1", ["cc", "ca"])
        hub.action_consensus_propose(ai_dir, "Round 2", ["cc", "gc"])
        hub.action_consensus_check(ai_dir)
        out = capsys.readouterr().out
        assert "Round 1" in out
        assert "Round 2" in out

    def test_consensus_check_specific_round(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Specific", ["cc", "ca", "gc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        hub.action_consensus_check(ai_dir, rid)
        out = capsys.readouterr().out
        assert "Specific" in out

    def test_invalid_voter_rejected(self, ai_dir, capsys):
        hub.action_consensus_propose(ai_dir, "Closed vote", ["cc", "ca"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        import sys as _sys
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "unknown_node", "agree")

    def test_vote_on_closed_round_rejected(self, ai_dir):
        hub.action_consensus_propose(ai_dir, "Quick", ["cc"])
        rounds = list((ai_dir / "consensus").glob("*.json"))
        rid = json.loads(rounds[0].read_text("utf-8"))["round_id"]
        hub.action_consensus_vote(ai_dir, rid, "cc", "agree")  # finalized
        with pytest.raises(SystemExit):
            hub.action_consensus_vote(ai_dir, rid, "cc", "agree")  # already closed


# ─── §P-7 N-Node 등록 ─────────────────────────────────────────
class TestNodeManagement:
    def test_list_nodes_shows_defaults(self, ai_dir, capsys):
        hub.action_list_nodes(ai_dir)
        out = capsys.readouterr().out
        assert "cc" in out
        assert "gc" in out
        assert "ca" in out

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
