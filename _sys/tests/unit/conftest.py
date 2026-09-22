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

# Register _sys via bootstrap_root_package so 'from _sys.core import ...' works
_SYS_DIR = Path(__file__).resolve().parent.parent.parent
# Also keep core and _sys in path for tests doing 'import hub' or 'from core import ...' directly
sys.path.insert(0, str(_SYS_DIR / "core"))
if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))

from root import bootstrap_root_package
bootstrap_root_package(_SYS_DIR)

# --- OOM / Hang Protection ---

def _enforce_oom_guard(threshold_mb: float, available_mb: float, marker_path: str = "oom_marker.json") -> None:
    """Decision point for the OOM guard. Isolated for testability."""
    if available_mb < threshold_mb:
        print(f"\n[CRITICAL] OOM Guard: Available RAM ({available_mb:.1f}MB) below threshold ({threshold_mb}MB)!")
        print("[CRITICAL] Force-terminating pytest and child processes to save OS...")
        try:
            with open(marker_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "available_mb": available_mb,
                    "threshold_mb": threshold_mb,
                    "reason": "OOM Guard triggered"
                }, f)
        except Exception:
            pass
        os._exit(1)

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
                _enforce_oom_guard(self.threshold_mb, available_mb)
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

# --- Log isolation (prevents tests from polluting tracked _sys/data/logs) ---

@pytest.fixture(autouse=True)
def isolate_hub_logs(tmp_path, monkeypatch):
    """Redirect HubLogger output to a per-test temp dir so error/ipc/etc. log
    fixtures never write into the tracked production logs under _sys/data/logs."""
    monkeypatch.setenv("HUB_LOG_DIR", str(tmp_path / "hub-logs"))


