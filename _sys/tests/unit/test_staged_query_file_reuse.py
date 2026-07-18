"""Staged (non-ephemeral) query file reuse visibility (2026-07-18).

Found live: a 2-day-old staged file from the 2026-07-16 mega-audit was
silently re-dispatched to ag.effort with zero visible signal that a stale,
previously-attempted request was being reused rather than a fresh one --
correlated with an unrelated dispatch stalling ~21 minutes on lock
contention. This makes every staged-file reuse an explicit, greppable event.
"""
import sys
import time
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub


def test_staged_query_file_age_hours_computes_correctly(tmp_path):
    f = tmp_path / "staged.txt"
    f.write_text("x", encoding="utf-8")
    now = time.time()
    # backdate mtime by 2 hours
    import os
    os.utime(f, (now - 7200, now - 7200))
    age = hub._staged_query_file_age_hours(f, now=now)
    assert age is not None
    assert 1.9 < age < 2.1


def test_staged_query_file_age_hours_missing_file_returns_none(tmp_path):
    assert hub._staged_query_file_age_hours(tmp_path / "nope.txt") is None


def test_notify_prints_notice_always(tmp_path, monkeypatch, capsys):
    f = tmp_path / "staged.txt"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"active_constraints": {"staged_query_file_warn_age_hours": 1}})
    hub._notify_staged_query_file_reuse(f, "ag.effort", None)
    err = capsys.readouterr().err
    assert "[HUB:NOTICE] staged query file reused" in err
    assert "ag.effort" in err


def test_notify_warns_and_records_telemetry_when_stale(tmp_path, monkeypatch, capsys):
    f = tmp_path / "staged.txt"
    f.write_text("x", encoding="utf-8")
    import os
    old = time.time() - 3600 * 5  # 5h old
    os.utime(f, (old, old))
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"active_constraints": {"staged_query_file_warn_age_hours": 1}})
    recorded = {}
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai_root, event, **fields: recorded.update({"event": event, **fields}))
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    hub._notify_staged_query_file_reuse(f, "ag.effort", ai_root)
    err = capsys.readouterr().err
    assert "[HUB:WARN] staged query file is" in err
    assert recorded["event"] == "staged_query_file_stale_reuse"
    assert recorded["target"] == "ag.effort"
    assert recorded["age_hours"] >= 4.9


def test_notify_does_not_warn_or_record_when_fresh(tmp_path, monkeypatch, capsys):
    f = tmp_path / "staged.txt"
    f.write_text("x", encoding="utf-8")  # fresh, mtime = now
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"active_constraints": {"staged_query_file_warn_age_hours": 1}})
    recorded = {"called": False}
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda *a, **k: recorded.update({"called": True}))
    hub._notify_staged_query_file_reuse(f, "ag.effort", tmp_path / ".ai")
    err = capsys.readouterr().err
    assert "[HUB:NOTICE]" in err
    assert "[HUB:WARN]" not in err
    assert recorded["called"] is False
