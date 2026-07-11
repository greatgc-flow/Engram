"""Tests for check_operational_guard_shadow.py - D2 Gate 3 soak reporter."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_operational_guard_shadow.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_operational_guard_shadow_ut", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _event(ts, case_key="action=status|origin=terminal|phase=default|force=0|collab=below_threshold|consensus=0|coord=healthy|worker_tier=-", shadow_match=True):
    return {"ts": ts, "event": "operational_guard_shadow", "action": "status", "case_key": case_key, "shadow_match": shadow_match}


def test_insufficient_events_is_informational_not_a_problem():
    m = _mod()
    events = [_event("2026-07-11T00:00:00")]
    report = m.evaluate_soak(events, {_event("x")["case_key"]})
    assert report["meets_count_bar"] is False
    assert report["mismatch_count"] == 0
    assert report["coverage_gaps"] == []


def test_meets_count_and_span_bar_with_enough_events():
    m = _mod()
    key = "action=status|origin=terminal|phase=default|force=0|collab=below_threshold|consensus=0|coord=healthy|worker_tier=-"
    events = [_event("2026-07-11T00:00:00", key)] + [_event("2026-07-12T01:00:00", key) for _ in range(100)]
    report = m.evaluate_soak(events, {key})
    assert report["meets_count_bar"] is True
    assert report["meets_span_bar"] is True
    assert report["zero_mismatches"] is True
    assert report["zero_coverage_gaps"] is True


def test_span_under_24h_does_not_meet_span_bar():
    m = _mod()
    key = "k"
    events = [_event("2026-07-11T00:00:00", key)] + [_event("2026-07-11T05:00:00", key) for _ in range(100)]
    report = m.evaluate_soak(events, {key})
    assert report["meets_count_bar"] is True
    assert report["meets_span_bar"] is False


def test_mismatch_is_flagged():
    m = _mod()
    key = "k"
    events = [_event("2026-07-11T00:00:00", key), _event("2026-07-12T01:00:00", key, shadow_match=False)]
    report = m.evaluate_soak(events, {key})
    assert report["mismatch_count"] == 1
    assert report["zero_mismatches"] is False


def test_coverage_gap_is_flagged_when_live_case_key_absent_from_static_matrix():
    m = _mod()
    live_key = "action=weird-new-action|origin=terminal|phase=default|force=0|collab=below_threshold|consensus=0|coord=healthy|worker_tier=-"
    events = [_event("2026-07-11T00:00:00", live_key), _event("2026-07-12T01:00:00", live_key)]
    report = m.evaluate_soak(events, {"some-other-key-in-the-static-matrix"})
    assert report["coverage_gaps"] == [live_key]
    assert report["zero_coverage_gaps"] is False


def test_main_exits_1_when_soak_insufficient(tmp_path, monkeypatch, capsys):
    m = _mod()
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    (ai_root / "routing_metrics.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(m, "_static_case_keys", lambda: set())
    rc = m.main(["--ai-root", str(ai_root)])
    assert rc == 1


def test_main_exits_2_on_mismatch(tmp_path, monkeypatch):
    m = _mod()
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    key = "k"
    lines = "\n".join([
        '{"ts": "2026-07-11T00:00:00", "event": "operational_guard_shadow", "case_key": "%s", "shadow_match": false}' % key,
    ])
    (ai_root / "routing_metrics.jsonl").write_text(lines + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "_static_case_keys", lambda: {key})
    rc = m.main(["--ai-root", str(ai_root)])
    assert rc == 2


def test_main_exits_0_when_soak_bar_fully_met(tmp_path, monkeypatch):
    m = _mod()
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    key = "k"
    lines = ['{"ts": "2026-07-11T00:00:00", "event": "operational_guard_shadow", "case_key": "%s", "shadow_match": true}' % key]
    lines += ['{"ts": "2026-07-12T01:00:00", "event": "operational_guard_shadow", "case_key": "%s", "shadow_match": true}' % key] * 100
    (ai_root / "routing_metrics.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "_static_case_keys", lambda: {key})
    rc = m.main(["--ai-root", str(ai_root)])
    assert rc == 0
