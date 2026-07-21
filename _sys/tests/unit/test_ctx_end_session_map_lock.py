from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import ctx_end  # noqa: E402


def _make_portable_root(tmp_path):
    sys_gemini = tmp_path / "_sys" / "gemini"
    sys_gemini.mkdir(parents=True)
    (sys_gemini / "session-id.txt").write_text("abc123", encoding="utf-8")
    return tmp_path


def test_lock_owner_removes_its_own_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_end.time, "sleep", lambda *_: None)
    portable_root = _make_portable_root(tmp_path)
    lock_dir = portable_root / "_sys" / "gemini" / "session-map.json.lock"

    ctx_end.archive_gemini_session(portable_root)

    assert not lock_dir.exists()
    smap = json.loads((portable_root / "_sys" / "gemini" / "session-map.json").read_text(encoding="utf-8"))
    assert smap["active"] is None


def test_non_owner_does_not_steal_or_delete_another_process_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_end.time, "sleep", lambda *_: None)
    portable_root = _make_portable_root(tmp_path)
    lock_dir = portable_root / "_sys" / "gemini" / "session-map.json.lock"
    # Simulate another process already holding the lock for the entire retry window.
    lock_dir.mkdir(parents=True)

    ctx_end.archive_gemini_session(portable_root)

    # Must not have deleted the lock it never acquired.
    assert lock_dir.exists()
