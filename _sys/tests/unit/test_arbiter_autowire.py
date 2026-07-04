"""B6 — arbiter auto-wire on consensus finalization (_maybe_run_arbiter_on_finalize).

The auto-wire is gated by final_arbiter.auto_wire_on_finalize (default FALSE) in
ADDITION to final_arbiter.enabled, so premium cc.fable is never spent implicitly.
The hook must run OUTSIDE the round lock and never raise.
"""
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402

ROUND = {"round_id": "r-test", "subject": "x", "voters": ["ag", "cx"],
         "votes": {"ag": {"vote": "agree"}, "cx": {"vote": "disagree", "reason": "no"}}}


def test_gate_off_does_not_run(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": False})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(Path("."), ROUND)
    assert calls == []  # gated OFF -> arbiter never invoked


def test_enabled_but_no_autowire_flag_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(Path("."), ROUND)
    assert calls == []  # missing auto_wire flag defaults to no-run


def test_gate_on_runs_with_round_data(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})

    def fake_run(ai_root, data, config=None):
        calls.append(data)
        return {"fired": True}
    monkeypatch.setattr(hub, "run_arbiter_on_round", fake_run)
    hub._maybe_run_arbiter_on_finalize(Path("."), ROUND)
    assert len(calls) == 1
    assert calls[0]["round_id"] == "r-test"


def test_never_raises(monkeypatch):
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})

    def boom(*a, **k):
        raise RuntimeError("arbiter exploded")
    monkeypatch.setattr(hub, "run_arbiter_on_round", boom)
    # Must swallow — a finalized decision must not break on arbiter failure.
    hub._maybe_run_arbiter_on_finalize(Path("."), ROUND)


def test_disabled_short_circuits(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": False, "auto_wire_on_finalize": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(Path("."), ROUND)
    assert calls == []  # enabled=False -> never runs even if auto_wire true
