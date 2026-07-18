"""Prior-failure detection for staged query file reuse (2026-07-18).

Forensic deep-dive (cx.effort) found reusing an already-failed query file is
a MUCH stronger zombie predictor than mere file age: PTY zombie rate for
reused files was 5/9 (55.6%) vs 2/75 (2.7%) for first-time files (odds ratio
~45.6, p=0.0000786). One file zombied 3/3 times it was ever dispatched.
"""
import json
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub


def _write_history(ai_root, entries):
    path = ai_root / "ask_history.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def test_prior_failures_counts_matching_filename_failures_only(tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    qf = tmp_path / "ipc" / "ag.opus-poison.txt"
    _write_history(ai_root, [
        {"query_file": "_sys/ai/ipc/ag.opus-poison.txt", "success": False},
        {"query_file": "P:\\_sys\\ai\\ipc\\ag.opus-poison.txt", "success": False},  # same file, different path style
        {"query_file": "_sys/ai/ipc/ag.opus-poison.txt", "success": True},  # a success doesn't count
        {"query_file": "_sys/ai/ipc/unrelated-file.txt", "success": False},  # different file
    ])
    assert hub._staged_query_file_prior_failures(qf, ai_root) == 2


def test_prior_failures_zero_when_no_history(tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    qf = tmp_path / "fresh.txt"
    assert hub._staged_query_file_prior_failures(qf, ai_root) == 0


def test_prior_failures_zero_when_no_ai_root():
    assert hub._staged_query_file_prior_failures(Path("x.txt"), None) == 0


def test_notify_warns_loudly_and_records_telemetry_on_prior_failure(tmp_path, monkeypatch, capsys):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    qf = tmp_path / "staged.txt"
    qf.write_text("x", encoding="utf-8")
    _write_history(ai_root, [
        {"query_file": "staged.txt", "success": False},
        {"query_file": "staged.txt", "success": False},
        {"query_file": "staged.txt", "success": False},
    ])
    monkeypatch.setattr(hub, "_load_protocol_cfg", lambda: {"active_constraints": {"staged_query_file_warn_age_hours": 999}})
    recorded = []
    monkeypatch.setattr(hub, "_record_routing_metric",
                        lambda ai_root, event, **fields: recorded.append({"event": event, **fields}))
    hub._notify_staged_query_file_reuse(qf, "ag.effort", ai_root)
    err = capsys.readouterr().err
    assert "FAILED 3 prior time(s)" in err
    events = [r["event"] for r in recorded]
    assert "staged_query_file_prior_failure_reuse" in events
    rec = next(r for r in recorded if r["event"] == "staged_query_file_prior_failure_reuse")
    assert rec["prior_failures"] == 3
