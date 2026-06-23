"""pytest fixtures and session hooks for unit tests."""
import os
import sys
import json
import shutil
import threading
import time
import psutil
import pytest
from pathlib import Path

# hub.py 경로를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

# --- OOM / Hang Protection ---

class MemoryGuard(threading.Thread):
    """Monitor system memory and force-terminate if it drops below threshold."""
    def __init__(self, threshold_mb=512, interval=1.0):
        super().__init__(daemon=True)
        self.threshold_mb = threshold_mb
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                available_mb = psutil.virtual_memory().available / (1024 * 1024)
                if available_mb < self.threshold_mb:
                    # Emergency exit to prevent OS hang/freeze
                    print(f"\n[CRITICAL] OOM Guard: Available RAM ({available_mb:.1f}MB) below threshold ({self.threshold_mb}MB)!")
                    print("[CRITICAL] Force-terminating pytest and child processes to save OS...")
                    # os._exit is used to bypass pytest's normal teardown which might hang during OOM
                    os._exit(1)
            except Exception as e:
                # Fail-safe: if psutil fails, don't crash the test runner but log it
                print(f"\n[OOM-GUARD] Monitor Error: {e}")
            time.sleep(self.interval)

    def stop(self):
        self.stop_event.set()

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Start memory guard at the beginning of the test session."""
    # pytest-timeout: 기본값이 0(disabled)일 때만 60s로 강제 설정.
    # pytest.ini의 timeout= 또는 --timeout CLI 옵션이 우선순위를 가짐.
    if session.config.pluginmanager.hasplugin("timeout"):
        current = session.config.getoption("timeout", default=0)
        if not current:  # 0 또는 None이면 기본값 60s 적용
            session.config.option.timeout = 60

    # Start OOM monitor
    session.memory_guard = MemoryGuard(threshold_mb=512)
    session.memory_guard.start()
    print(f"\n[OOM-GUARD] Active (Threshold: 512MB, Interval: 1.0s)")

def pytest_sessionfinish(session, exitstatus):
    """Stop memory guard when the session ends."""
    if hasattr(session, "memory_guard"):
        session.memory_guard.stop()

# --- Existing Fixtures ---

@pytest.fixture
def ai_dir(tmp_path):
    """격리된 임시 .ai/ 디렉토리."""
    ai = tmp_path / ".ai"
    (ai / ".lock").mkdir(parents=True)
    (ai / "sessions").mkdir()
    (ai / "consensus").mkdir()
    (ai / "mailbox.json").write_text(
        json.dumps({"messages": [], "unread_count": 0}), encoding="utf-8"
    )
    (ai / "state.json").write_text(
        json.dumps({
            "room_id": None,
            "members": {},
            "mission": None, "blocked": None, "phase": None, "updated_at": None
        }), encoding="utf-8"
    )
    (ai / "nodes.json").write_text(
        json.dumps({
            "version": "1",
            "nodes": {
                "cc": {"tier": 1, "type": "orchestrator", "invoke": "claude",
                       "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "persistent"},
                "ca": {"tier": 2, "type": "agent", "invoke": "claude",
                       "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "short-term"},
                "ag": {"tier": 3, "type": "sensor", "invoke": "agy",
                       "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "session"},
            }
        }), encoding="utf-8"
    )
    (ai / "mailbox").mkdir(exist_ok=True)
    (ai / "leases.json").write_text(json.dumps({}), encoding="utf-8")
    return ai


@pytest.fixture
def patch_ai_root(ai_dir, monkeypatch):
    """hub.py 테스트에서 find_ai_root()가 tmp .ai/ 반환하도록 패치.
    autouse 제거: hub와 무관한 테스트(doc_consistency 등)에서 hub import를 강제하지 않음."""
    import hub
    monkeypatch.setattr(hub, "find_ai_root", lambda: ai_dir)
    monkeypatch.setattr(hub, "ensure_ai_dir", lambda p: p)
    return ai_dir
