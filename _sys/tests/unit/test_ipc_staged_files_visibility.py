"""diag FRAME visibility for staged (non-single-use) IPC query files (2026-07-18).

Found live: ~655 files had accumulated in _sys/ai/ipc/ back to 2026-06-20
because the ephemeral-file naming regex silently never matched real-world
tag usage. This surfaces the backlog so it's never invisible again.
"""
import importlib.util
import sys
import time
from pathlib import Path

DIAG_PATH = Path(__file__).resolve().parents[2] / "cli" / "diag.py"


def load_diag():
    spec = importlib.util.spec_from_file_location("diag_under_test_ipc", DIAG_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ipc_staged_files_line_counts_staged_and_stale(tmp_path, monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "SYS_DIR", tmp_path)
    ipc_dir = tmp_path / "ai" / "ipc"
    ipc_dir.mkdir(parents=True)

    # ephemeral (auto-generated, single-use pattern) -- should NOT be counted
    (ipc_dir / "cx-20260718001306-zombie1.txt").write_text("x", encoding="utf-8")
    # staged (no 14-digit timestamp) -- fresh, counted as staged but not stale
    fresh = ipc_dir / "ping-ag.txt"
    fresh.write_text("x", encoding="utf-8")
    # staged AND old -- counted as staged AND stale
    stale = ipc_dir / "probe-cx.txt"
    stale.write_text("x", encoding="utf-8")
    import os
    old = time.time() - 3600 * 5
    os.utime(stale, (old, old))

    line = diag._ipc_staged_files_line()
    assert "IPC staged files: 2 " in line
    assert "1 >=" in line


def test_ipc_staged_files_line_missing_dir_is_safe(tmp_path, monkeypatch):
    diag = load_diag()
    monkeypatch.setattr(diag, "SYS_DIR", tmp_path)  # no ai/ipc under here
    line = diag._ipc_staged_files_line()
    assert "IPC staged files: absent" in line
