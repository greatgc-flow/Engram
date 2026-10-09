"""pytest fixtures and session hooks for unit tests."""
import os
import sys
import json
import shutil
import threading
import time
import tempfile
import psutil
import pytest
from pathlib import Path
from contextlib import contextmanager
import uuid

# Register _sys via bootstrap_root_package so 'from _sys.core import ...' works
_SYS_DIR = Path(__file__).resolve().parent.parent.parent
# Also keep core and _sys in path for tests doing 'import hub' or 'from core import ...' directly
sys.path.insert(0, str(_SYS_DIR / "core"))
if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))

from root import bootstrap_root_package, find_root
bootstrap_root_package(_SYS_DIR)

# --- OOM / Hang Protection ---

DEFAULT_OOM_MARKER = str(Path(tempfile.gettempdir()) / "oom_marker.json")

def _enforce_oom_guard(threshold_mb: float, available_mb: float, marker_path: str | None = None) -> None:
    """Decision point for the OOM guard. Isolated for testability."""
    if marker_path is None:
        marker_path = DEFAULT_OOM_MARKER
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

def pytest_addoption(parser):
    parser.addoption(
        "--cp949-strict",
        action="store_true",
        default=False,
        help="Fail unconditionally if any cp949 test is skipped or if the cp949 test set is empty",
    )

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Start memory guard and initialize strict CP949 tracking at session start."""
    # pytest-timeout: enforce 60s fallback when disabled (0 or None)
    # Values in pytest.ini or CLI --timeout take precedence.
    if session.config.pluginmanager.hasplugin("timeout"):
        current = session.config.getoption("timeout", default=0)
        if not current:
            session.config.option.timeout = 60

    # Start OOM monitor
    session.memory_guard = MemoryGuard(threshold_mb=512)
    session.memory_guard.start()
    print(f"\n[OOM-GUARD] Active (Threshold: 512MB, Interval: 1.0s)")

    # CP949 verification tracking
    session.cp949_collected = 0
    session.cp949_skipped = []

def pytest_collection_modifyitems(session, config, items):
    """Track collected cp949 tests for strict verification."""
    cp949_items = [item for item in items if item.get_closest_marker("cp949") is not None]
    session.cp949_collected = len(cp949_items)

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture skipped cp949 tests."""
    outcome = yield
    report = outcome.get_result()
    if report.skipped and item.get_closest_marker("cp949") is not None:
        session = item.session
        if hasattr(session, "cp949_skipped"):
            session.cp949_skipped.append((item.nodeid, str(report.longrepr or "")))

def pytest_sessionfinish(session, exitstatus):
    """Stop memory guard and enforce CP949 strict gate if enabled."""
    if hasattr(session, "memory_guard"):
        session.memory_guard.stop()

    if session.config.getoption("--cp949-strict", default=False):
        collected = getattr(session, "cp949_collected", 0)
        skipped = getattr(session, "cp949_skipped", [])
        if collected == 0:
            print("\n[CP949-STRICT] FAILED: CP949 test set is empty (0 tests collected).", file=sys.stderr)
            session.exitstatus = 1
        elif skipped:
            print(f"\n[CP949-STRICT] FAILED: {len(skipped)} CP949 test(s) skipped on CI:", file=sys.stderr)
            for nodeid, reason in skipped:
                print(f"  - {nodeid}: {reason.strip()}", file=sys.stderr)
            session.exitstatus = 1

# --- Log isolation (prevents tests from polluting tracked _sys/data/logs) ---

@pytest.fixture(autouse=True)
def isolate_hub_logs(tmp_path, monkeypatch):
    """Redirect HubLogger output to a per-test temp dir so error/ipc/etc. log
    fixtures never write into the tracked production logs under _sys/data/logs."""
    monkeypatch.setenv("HUB_LOG_DIR", str(tmp_path / "hub-logs"))


@contextmanager
def scratch_dir():
    """Shared unittest scratch with inherited ACLs and best-effort cleanup."""
    parent = find_root(__file__) / "data" / "temp"
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / ("unit_scratch_" + uuid.uuid4().hex)
    path.mkdir()  # Plain mkdir preserves ACL access for child cmd.exe.
    try:
        yield path
    finally:
        for attempt in range(3):
            try:
                shutil.rmtree(path)
                break
            except OSError:
                if attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    shutil.rmtree(path, ignore_errors=True)
