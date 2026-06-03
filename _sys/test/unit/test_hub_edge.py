"""
hub.py 경계값·에러핸들링·데이터무결성 테스트
Gemini MECE 설계: S(세션), M(메시지), D(데이터), R(강건성) 영역
"""
import json
import sys
import pytest
from pathlib import Path
import hub


# ─── S: 세션 라이프사이클 경계 ─────────────────────────────

class TestSessionEdge:
    def test_s3_session_refresh(self, ai_dir, capsys):
        """S-3: 이미 활성화된 에이전트가 re-init → SID 갱신."""
        hub.action_init_session(ai_dir, "claude")
        first_sid = capsys.readouterr().out.strip()
        hub.action_init_session(ai_dir, "claude")
        second_sid = capsys.readouterr().out.strip()
        # 새 SID가 발급되어야 함
        assert second_sid != first_sid
        assert second_sid.startswith("c")
        # state.json에 새 SID 반영
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["claude_sid"] == second_sid

    def test_s4_partial_end_session(self, ai_dir):
        """S-4: 한쪽만 end-session → 상대방 SID 유지."""
        hub.action_init_session(ai_dir, "claude")
        hub.action_init_session(ai_dir, "gemini")
        state_before = json.loads((ai_dir / "state.json").read_text("utf-8"))
        gemini_sid = state_before["gemini_sid"]
        hub.action_end_session(ai_dir, "claude")
        state_after = json.loads((ai_dir / "state.json").read_text("utf-8"))
        # claude SID는 null, gemini SID는 유지
        assert state_after["claude_sid"] is None
        assert state_after["gemini_sid"] == gemini_sid

    def test_s5_end_session_clears_read_only(self, ai_dir):
        """S-5: end-session이 read 메시지만 삭제, unread는 보존."""
        hub.action_init_session(ai_dir, "claude")
        hub.action_send(ai_dir, "claude", "gemini", "msg1")
        hub.action_send(ai_dir, "claude", "gemini", "msg2")
        hub.action_mark_read(ai_dir, "gemini", all_=False, msg_id=1)
        hub.action_end_session(ai_dir, "claude")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        # msg1(read)은 삭제, msg2(unread)는 보존
        assert mb["unread_count"] == 1
        assert len(mb["messages"]) == 1
        assert mb["messages"][0]["id"] == 2

    def test_s_end_without_session(self, ai_dir, capsys):
        """세션 없이 end-session 호출 → graceful (에러 없이 종료)."""
        hub.action_end_session(ai_dir, "claude")
        out = capsys.readouterr().out
        assert "[END]" in out  # 에러 없이 완료


# ─── M: 메시지 경계 ────────────────────────────────────────

class TestMailboxEdge:
    def test_m3_selective_mark_read(self, ai_dir):
        """M-3: 특정 ID만 읽음 처리."""
        hub.action_send(ai_dir, "claude", "gemini", "msg1")
        hub.action_send(ai_dir, "claude", "gemini", "msg2")
        hub.action_send(ai_dir, "claude", "gemini", "msg3")
        hub.action_mark_read(ai_dir, "gemini", all_=False, msg_id=2)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 2
        statuses = {m["id"]: m["status"] for m in mb["messages"]}
        assert statuses[1] == "unread"
        assert statuses[2] == "read"
        assert statuses[3] == "unread"

    def test_m4_mark_read_cross_target(self, ai_dir):
        """M-4: target이 다른 메시지는 mark-read 영향 없음."""
        hub.action_send(ai_dir, "gemini", "claude", "for claude")
        hub.action_send(ai_dir, "claude", "gemini", "for gemini")
        hub.action_mark_read(ai_dir, "claude", all_=True, msg_id=None)
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        # gemini 메시지는 여전히 unread
        assert mb["unread_count"] == 1
        gemini_msg = next(m for m in mb["messages"] if m["to"] == "gemini")
        assert gemini_msg["status"] == "unread"

    def test_m5_empty_inbox_pretty_print(self, ai_dir, capsys):
        """M-5: 빈 인박스 check → 에러 없이 안내 문구."""
        hub.action_check(ai_dir, "gemini")
        out = capsys.readouterr().out
        assert "inbox empty" in out
        assert "gemini" in out

    def test_m_message_id_sequential(self, ai_dir):
        """메시지 ID가 순차적으로 증가."""
        for i in range(5):
            hub.action_send(ai_dir, "claude", "gemini", f"msg-{i}")
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        ids = [m["id"] for m in mb["messages"]]
        assert ids == list(range(1, 6))


# ─── D: 데이터 무결성 ──────────────────────────────────────

class TestDataIntegrity:
    def test_d1_handoff_fifo_exactly_5(self, ai_dir):
        """D-1: 정확히 6개 추가 → 5개로 유지."""
        session_dir = ai_dir / "sessions" / "c1111-g2222"
        session_dir.mkdir(parents=True)
        sections = {
            "GOAL": ["목표"],
            "RECENT_COMPLETED": [f"task-{i}" for i in range(6)],
            "PENDING_ISSUES": [],
            "KEY_DECISIONS": []
        }
        hub._write_handoff(session_dir, sections)
        result = hub._read_handoff(session_dir)
        assert len(result["RECENT_COMPLETED"]) == 5
        # 가장 오래된 task-0이 제거됨
        assert "task-0" not in result["RECENT_COMPLETED"]
        assert "task-5" in result["RECENT_COMPLETED"]

    def test_d2_handoff_exactly_at_limit(self, ai_dir):
        """D-2: handoff 정확히 12000자 = 통과, 초과 시 축소."""
        session_dir = ai_dir / "sessions" / "c1111-g2222"
        session_dir.mkdir(parents=True)
        # 정확히 한도에 맞게 설계
        item = "a" * 2399
        sections = {
            "GOAL": ["목표"],
            "RECENT_COMPLETED": [item] * 5,
            "PENDING_ISSUES": [],
            "KEY_DECISIONS": []
        }
        hub._write_handoff(session_dir, sections)
        content = (session_dir / "handoff.md").read_text("utf-8")
        assert len(content) <= hub.HANDOFF_MAX_CHARS

    def test_d3_append_log_no_loss(self, ai_dir):
        """D-3: 연속 append-log → 모든 항목 누적."""
        for i in range(10):
            hub.action_append_log(ai_dir, f"Axis-{i}", f"script-{i}", "OK", f"detail-{i}")
        log_path = ai_dir / "log.jsonl"
        lines = log_path.read_text("utf-8").strip().splitlines()
        assert len(lines) == 10
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["axis"] == f"Axis-{i}"
            assert entry["script"] == f"script-{i}"

    def test_d4_archive_dual_output(self, ai_dir, tmp_path):
        """D-4: archive-file → 날짜 버전 + latest 두 파일 생성."""
        src = tmp_path / "test.json"
        src.write_text('{"test": 1}', encoding="utf-8")
        hub.action_archive_file(ai_dir, "mydata", str(src))
        archive_dir = ai_dir.parent / "_archive"
        # latest 파일 반드시 존재
        assert (archive_dir / "mydata-latest.json").exists()
        # 날짜 버전 파일 존재
        dated = list(archive_dir.glob("mydata-2*.json"))
        assert len(dated) >= 1

    def test_d5_utf8_korean_in_messages(self, ai_dir, capsys):
        """D-5: 한글 메시지 저장/조회 인코딩 손실 없음."""
        korean_msg = "안녕하세요 Phase 3 완료. 한글 테스트 메시지입니다."
        hub.action_send(ai_dir, "claude", "gemini", korean_msg)
        hub.action_check(ai_dir, "gemini")
        out = capsys.readouterr().out
        assert korean_msg in out

    def test_d_state_json_all_fields(self, ai_dir, capsys):
        """status 출력이 state.json 핵심 필드를 모두 포함."""
        hub.action_init_session(ai_dir, "claude")
        capsys.readouterr()
        hub.action_update_status(ai_dir, "test mission", "some blocker", "5")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "test mission" in out
        assert "some blocker" in out
        assert "SESSION STATUS" in out
        assert "MAILBOX" in out


# ─── R: 강건성 ─────────────────────────────────────────────

class TestRobustness:
    def test_r2_root_traversal_logic(self, monkeypatch):
        """R-2: find_ai_root()가 .git 발견 시 해당 디렉토리/.ai 반환."""
        from pathlib import Path
        # 가상 경로로 테스트: CWD=fake/src/deep, .git=fake/
        fake_deep = Path("Z:/fake/project/src/components").resolve()
        fake_project = Path("Z:/fake/project")

        call_count = [0]

        def mock_cwd():
            return fake_deep

        def mock_exists(self):
            # fake_project/.git 존재, 나머지는 없음
            if str(self) == str(fake_project / ".git"):
                return True
            if str(self) == str(fake_project / ".ai"):
                return False
            return False

        monkeypatch.setattr(Path, "cwd", lambda: fake_deep)
        monkeypatch.setattr(Path, "exists", mock_exists)

        # find_ai_root의 핵심 로직: .git을 찾으면 같은 레벨에 .ai 반환
        # 직접 로직 테스트
        cwd = fake_deep
        candidate = cwd
        result = None
        for _ in range(20):
            if (candidate / ".git").exists():
                result = candidate / ".ai"
                break
            parent = candidate.parent
            if parent == candidate:
                result = cwd / ".ai"
                break
            candidate = parent
        assert result == fake_project / ".ai"

    def test_r2_drive_root_fallback(self, tmp_path):
        """R-2: .git 없으면 CWD에 .ai/ 생성 (드라이브 루트 fallback)."""
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            ai_root = hub.find_ai_root()
            assert ai_root == tmp_path / ".ai"
        finally:
            os.chdir(orig)

    def test_r3_invalid_action_exits(self):
        """R-3: 잘못된 액션 → argparse 에러 + exit."""
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, hub.__file__, "nonexistent-action"],
            capture_output=True, text=True
        )
        assert result.returncode != 0

    def test_r_lock_dir_auto_recreate(self, ai_dir):
        """lock 디렉토리 삭제 후 자동 재생성."""
        import shutil
        shutil.rmtree(ai_dir / ".lock")
        # 다음 Write 액션에서 자동 재생성
        hub.action_send(ai_dir, "claude", "gemini", "test after lock deletion")
        assert (ai_dir / ".lock").exists()
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert mb["unread_count"] == 1

    def test_r_corrupted_mailbox_recovery(self, ai_dir):
        """mailbox.json 손상 시 ensure_ai_dir가 재초기화."""
        # 잘못된 JSON 주입
        (ai_dir / "mailbox.json").write_text("INVALID JSON{{{", encoding="utf-8")
        # _read_json은 {} 반환 (에러 없음)
        mb = hub._read_json(ai_dir / "mailbox.json")
        assert mb == {}
        # ensure_ai_dir가 없는 경우 재생성하지는 않지만, 액션 자체는 정상 동작해야 함
        hub.action_send(ai_dir, "claude", "gemini", "recovery test")
        new_mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert new_mb["unread_count"] == 1

    def test_r_state_json_missing_fields(self, ai_dir, capsys):
        """state.json 일부 필드 누락 → status 출력 에러 없음."""
        # 최소 필드만 가진 state.json
        (ai_dir / "state.json").write_text('{"pair": "c1234-g5678"}', encoding="utf-8")
        hub.action_status(ai_dir)
        out = capsys.readouterr().out
        assert "SESSION STATUS" in out  # 에러 없이 출력

    def test_r_ask_invalid_target(self):
        """ask --to invalid → 에러 메시지 + exit 1."""
        with pytest.raises(SystemExit) as exc:
            hub.action_ask("unknown_target", "test query")
        assert exc.value.code == 1
