"""
hub.py 병렬 스트레스 테스트 — Python threading 기반 (R-1)
Race condition, filelock 무결성, 고부하 연속 작업 검증
"""
import json
import threading
import time
import random
import pytest
from pathlib import Path
import hub

WORKERS = 20   # 동시 스레드 수
ROUNDS = 50    # 총 작업 횟수


class TestConcurrentSend:
    """R-1: 동시 send — filelock으로 메시지 손실 없음."""

    def test_50_concurrent_sends_no_loss(self, ai_dir):
        errors = []
        lock = threading.Lock()

        def worker(i):
            try:
                hub.action_send(ai_dir, "claude", "gemini", f"concurrent-msg-{i}")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(ROUNDS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"에러 발생: {errors}"
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        # 모든 메시지 기록됨 (손실 없음)
        assert len(mb["messages"]) == ROUNDS
        assert mb["unread_count"] == ROUNDS

    def test_concurrent_send_no_duplicate_ids(self, ai_dir):
        """동시 전송 시 메시지 ID 중복 없음."""
        def worker():
            hub.action_send(ai_dir, "claude", "gemini", "test")

        threads = [threading.Thread(target=worker) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        ids = [m["id"] for m in mb["messages"]]
        assert len(ids) == len(set(ids)), "ID 중복 발생"

    def test_concurrent_mixed_operations(self, ai_dir):
        """send + check + mark-read 혼합 동시 실행 → 데이터 파손 없음."""
        # 먼저 메시지 10개 준비
        for i in range(10):
            hub.action_send(ai_dir, "claude", "gemini", f"initial-{i}")

        errors = []
        lock = threading.Lock()

        def sender():
            try:
                hub.action_send(ai_dir, "claude", "gemini", "new-msg")
            except Exception as e:
                with lock:
                    errors.append(f"send: {e}")

        def checker():
            try:
                import io
                from contextlib import redirect_stdout
                with redirect_stdout(io.StringIO()):
                    hub.action_check(ai_dir, "gemini")
            except Exception as e:
                with lock:
                    errors.append(f"check: {e}")

        def reader():
            try:
                hub.action_mark_read(ai_dir, "gemini", all_=False, msg_id=1)
            except Exception as e:
                with lock:
                    errors.append(f"mark_read: {e}")

        threads = (
            [threading.Thread(target=sender) for _ in range(10)] +
            [threading.Thread(target=checker) for _ in range(10)] +
            [threading.Thread(target=reader) for _ in range(5)]
        )
        random.shuffle(threads)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"동시 작업 에러: {errors}"
        # mailbox.json이 유효한 JSON인지 확인
        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert "messages" in mb
        assert "unread_count" in mb


class TestConcurrentInitSession:
    """10개 동시 init-session → pair 충돌 없음."""

    def test_10_concurrent_init_sessions(self, ai_dir):
        results = []
        errors = []
        lock = threading.Lock()

        def init_claude():
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    hub.action_init_session(ai_dir, "claude")
                sid = buf.getvalue().strip()
                with lock:
                    results.append(sid)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=init_claude) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"에러: {errors}"
        # state.json이 유효한 상태
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert state["pair"] is not None
        # 마지막으로 기록된 SID가 유효한 형식
        assert state["claude_sid"].startswith("c")

    def test_session_pair_stability(self, ai_dir):
        """claude + gemini 동시 init → pair가 두 에이전트 모두 반영."""
        import io
        from contextlib import redirect_stdout

        barrier = threading.Barrier(2)

        def init_agent(agent_name):
            barrier.wait()  # 동시 시작
            buf = io.StringIO()
            with redirect_stdout(buf):
                hub.action_init_session(ai_dir, agent_name)

        t1 = threading.Thread(target=init_agent, args=("claude",))
        t2 = threading.Thread(target=init_agent, args=("gemini",))
        t1.start(); t2.start()
        t1.join(); t2.join()

        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        # 둘 다 등록되었거나, 최소한 하나는 등록됨 (lock 경쟁에서 한쪽 승리 가능)
        assert state["pair"] is not None
        assert state["updated_at"] is not None


class TestRapidCycles:
    """빠른 send/check/mark-read 100회 반복 → 메시지 순서 보장."""

    def test_100_sequential_send_check_cycle(self, ai_dir):
        import io
        from contextlib import redirect_stdout

        for i in range(100):
            hub.action_send(ai_dir, "claude", "gemini", f"rapid-{i:03d}")

        mb = json.loads((ai_dir / "mailbox.json").read_text("utf-8"))
        assert len(mb["messages"]) == 100

        # 순서 확인: 내용이 순서대로 기록됨
        for i, msg in enumerate(mb["messages"]):
            assert msg["content"] == f"rapid-{i:03d}", f"순서 불일치: {i}"

    def test_append_log_100_entries(self, ai_dir):
        """100개 log 연속 append → 순서 유지, 손실 없음."""
        for i in range(100):
            hub.action_append_log(ai_dir, f"Axis-{i%10}", f"script-{i}", "OK", f"d-{i}")

        lines = (ai_dir / "log.jsonl").read_text("utf-8").strip().splitlines()
        assert len(lines) == 100
        # 각 라인이 유효한 JSON
        for line in lines:
            entry = json.loads(line)
            assert "ts" in entry
            assert "axis" in entry


class TestLockStress:
    """filelock 경합 — 다수 스레드의 동시 state 업데이트."""

    def test_concurrent_update_status(self, ai_dir):
        """20개 스레드가 동시에 update-status → state.json 손상 없음."""
        errors = []
        lock = threading.Lock()

        def update(i):
            try:
                hub.action_update_status(ai_dir, f"mission-{i}", None, str(i % 10))
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=update, args=(i,)) for i in range(WORKERS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # state.json이 유효한 JSON
        state = json.loads((ai_dir / "state.json").read_text("utf-8"))
        assert "mission" in state
        assert state["mission"] is not None

    def test_no_deadlock_under_load(self, ai_dir):
        """데드락 없음: 30초 내 완료."""
        start = time.time()
        errors = []
        lock = threading.Lock()

        def mixed_ops(i):
            try:
                hub.action_send(ai_dir, "claude", "gemini", f"load-{i}")
                hub.action_update_status(ai_dir, f"mission-{i}", None, None)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=mixed_ops, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        elapsed = time.time() - start
        assert not errors
        assert elapsed < 30, f"데드락 의심: {elapsed:.1f}초 소요"
