"""Tests for hub.detect_dissent arbiter context classification.

Pure dissent detection only: no I/O, no model call, no arbiter decision.
cx authored these tests; the impl was applied by the terminal (LL-005).
"""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub


def test_all_agree_unanimous_is_routine():
    ctx = hub.detect_dissent({
        "round_id": "r-1000",
        "subject": "merge branch",
        "voters": ["cc", "ag", "cx"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "agree", "reason": "ok"},
            "cx": {"vote": "agree", "reason": "ok"},
        },
    })

    assert ctx["kind"] == "routine"
    assert ctx["round_id"] == "r-1000"
    assert ctx["proposal"] == "merge branch"
    assert ctx["positions"] == {"ag": "agree", "cc": "agree", "cx": "agree"}
    assert ctx["blockers"] == []


def test_one_disagree_is_dissent_with_blocker():
    ctx = hub.detect_dissent({
        "round_id": "r-1001",
        "subject": "merge branch",
        "voters": ["cc", "ag", "cx"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "disagree", "reason": "missing regression test"},
            "cx": {"vote": "agree", "reason": "ok"},
        },
    })

    assert ctx["kind"] == "dissent"
    assert ctx["positions"]["ag"] == "disagree"
    assert ctx["blockers"] == ["ag: missing regression test"]


def test_abstain_is_dissent_with_blocker():
    ctx = hub.detect_dissent({
        "round_id": "r-1002",
        "subject": "ratify policy",
        "voters": ["cc", "ag"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "abstain", "reason": "insufficient evidence"},
        },
    })

    assert ctx["kind"] == "dissent"
    assert ctx["positions"]["ag"] == "abstain"
    assert ctx["blockers"] == ["ag: insufficient evidence"]


def test_missing_or_none_vote_is_unresolved_dissent_no_vote():
    ctx = hub.detect_dissent({
        "round_id": "r-1003",
        "subject": "final call",
        "voters": ["ag", "cc", "cx"],
        "votes": {
            "ag": None,
            "cc": {"vote": "agree", "reason": "ok"},
        },
    })

    assert ctx["kind"] == "dissent"
    assert ctx["positions"] == {"ag": "no_vote", "cc": "agree", "cx": "no_vote"}
    assert ctx["blockers"] == []


def test_empty_voters_or_empty_round_is_routine_and_never_raises():
    empty = hub.detect_dissent({})
    none_round = hub.detect_dissent(None)

    assert empty == {
        "kind": "routine",
        "round_id": None,
        "proposal": "",
        "positions": {},
        "blockers": [],
    }
    assert none_round["kind"] == "routine"
    assert none_round["positions"] == {}
    assert none_round["blockers"] == []


def test_deterministic_positions_and_blockers_sorted_by_peer():
    ctx = hub.detect_dissent({
        "round_id": "r-1004",
        "subject": "ship",
        "voters": ["cx", "ag", "cc"],
        "votes": {
            "cx": {"vote": "agree", "reason": "ok"},
            "cc": {"vote": "disagree", "reason": "contract gap"},
            "ag": {"vote": "abstain", "reason": "needs evidence"},
        },
    })

    assert list(ctx["positions"].keys()) == ["ag", "cc", "cx"]
    assert ctx["blockers"] == ["ag: needs evidence", "cc: contract gap"]


def test_round_id_passthrough_and_proposal_from_subject():
    ctx = hub.detect_dissent({
        "round_id": "r-1005",
        "subject": "promote arbiter hook",
        "voters": ["cx"],
        "votes": {"cx": {"vote": "agree", "reason": "ok"}},
    })

    assert ctx["round_id"] == "r-1005"
    assert ctx["proposal"] == "promote arbiter hook"

def test_unanimity_failure_is_r10_final():
    ctx = hub.detect_dissent({
        "round_id": "r-1006",
        "subject": "merge branch",
        "voters": ["cc", "ag", "cx"],
        "votes": {
            "cc": {"vote": "agree", "reason": "ok"},
            "ag": {"vote": "disagree", "reason": "missing regression test"},
            "cx": {"vote": "agree", "reason": "ok"},
        },
        "outcome": "human_gate_unanimity_failed"
    })

    assert ctx["kind"] == "r10_final"
    assert ctx["positions"]["ag"] == "disagree"
    assert ctx["blockers"] == ["ag: missing regression test"]
