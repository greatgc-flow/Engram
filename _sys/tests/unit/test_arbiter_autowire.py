"""B6 — arbiter auto-wire on consensus finalization (_maybe_run_arbiter_on_finalize).

The auto-wire is gated by final_arbiter.auto_wire_on_finalize (default FALSE) in
ADDITION to final_arbiter.enabled, so premium cc.fable is never spent implicitly.
The hook must run OUTSIDE the round lock and never raise.

2026-07-24: the hook now atomically claims a round (`arbiter_claimed: true`,
written under the consensus lock) before invoking the arbiter, so at most one
invocation happens even if the direct-vote and broker-merge finalize paths race
on the same round (architecture-audit Top-5 #3 follow-up). That claim check
requires the round to actually exist on disk at `ai_root/consensus/<round_id>.json`
-- these tests now persist a real round file via `tmp_path` instead of calling
the hook against a nonexistent path, which used to (silently, incorrectly) still
let the mocked arbiter run because no on-disk existence check existed yet.
"""
import json
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402

ROUND = {"round_id": "r-test", "subject": "x", "voters": ["ag", "cx"],
         "votes": {"ag": {"vote": "agree"}, "cx": {"vote": "disagree", "reason": "no"}}}


def _persist_round(tmp_path: Path, round_data: dict) -> Path:
    """Write a round file to <tmp_path>/consensus/<round_id>.json, matching
    the real on-disk layout `_maybe_run_arbiter_on_finalize`'s claim check
    now requires."""
    consensus_dir = tmp_path / "consensus"
    consensus_dir.mkdir(parents=True, exist_ok=True)
    rpath = consensus_dir / f"{round_data['round_id']}.json"
    rpath.write_text(json.dumps(round_data), encoding="utf-8")
    return rpath


def test_gate_off_does_not_run(monkeypatch, tmp_path):
    _persist_round(tmp_path, ROUND)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": False})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert calls == []  # gated OFF -> arbiter never invoked


def test_enabled_but_no_autowire_flag_missing(monkeypatch, tmp_path):
    _persist_round(tmp_path, ROUND)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config", lambda: {"enabled": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert calls == []  # missing auto_wire flag defaults to no-run


def test_gate_on_runs_with_round_data(monkeypatch, tmp_path):
    _persist_round(tmp_path, ROUND)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})

    def fake_run(ai_root, data, config=None):
        calls.append(data)
        return {"fired": True}
    monkeypatch.setattr(hub, "run_arbiter_on_round", fake_run)
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert len(calls) == 1
    assert calls[0]["round_id"] == "r-test"
    # the claim itself must be visible on disk after the hook runs
    rpath = tmp_path / "consensus" / "r-test.json"
    assert json.loads(rpath.read_text())["arbiter_claimed"] is True


def test_never_raises(monkeypatch, tmp_path):
    _persist_round(tmp_path, ROUND)
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})

    def boom(*a, **k):
        raise RuntimeError("arbiter exploded")
    monkeypatch.setattr(hub, "run_arbiter_on_round", boom)
    # Must swallow — a finalized decision must not break on arbiter failure.
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)


def test_disabled_short_circuits(monkeypatch, tmp_path):
    _persist_round(tmp_path, ROUND)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": False, "auto_wire_on_finalize": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert calls == []  # enabled=False -> never runs even if auto_wire true


def test_already_claimed_round_is_not_invoked_again(monkeypatch, tmp_path):
    """Regression test for the 2026-07-24 duplicate-invocation fix: a round
    already marked arbiter_claimed must never trigger a second arbiter call,
    e.g. if the direct-vote and broker-merge finalize paths both reach the
    hook for the same round."""
    already_claimed = dict(ROUND, arbiter_claimed=True)
    _persist_round(tmp_path, already_claimed)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert calls == []  # already claimed -> hook must skip invocation


def test_already_decided_round_is_not_invoked_again(monkeypatch, tmp_path):
    """A round that already has an arbiter_decision (a prior override/rejection
    was already applied) must also never trigger a second invocation."""
    already_decided = dict(ROUND, arbiter_decision={"authority": "override"})
    _persist_round(tmp_path, already_decided)
    calls = []
    monkeypatch.setattr(hub, "_final_arbiter_config",
                        lambda: {"enabled": True, "auto_wire_on_finalize": True})
    monkeypatch.setattr(hub, "run_arbiter_on_round",
                        lambda *a, **k: calls.append(a) or {"fired": True})
    hub._maybe_run_arbiter_on_finalize(tmp_path, ROUND)
    assert calls == []
