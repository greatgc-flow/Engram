"""
Unit Tests for Cluster C5 (Terminal Identity & Freshness Unification)

Covers:
  1. resolve_terminal_identity() pure evaluation (VACANT, EXPIRED, MISMATCH, FRESH)
  2. Fail-closed behavior on missing/malformed state
  3. Lease minting on action_terminal_handoff()
  4. CAS-protected action_terminal_heartbeat() renewal and rejection
  5. CAS-protected action_terminal_close() release and rejection
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import pytest
import sys

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

import core.hub as hub


class TestResolveTerminalIdentity:
    """Pure evaluator tests for resolve_terminal_identity()."""

    def test_vacant_empty_state(self):
        res = hub.resolve_terminal_identity({})
        assert res["status"] == "VACANT"
        assert res["is_active_terminal"] is False
        assert res["reason"] == "no_terminal_assigned"
        assert res["peer"] is None
        assert res["profile"] is None
        assert res["lease_id"] is None

    def test_vacant_legacy_only_missing_assignment(self):
        state = {"human_interface_peer": "ag"}
        res = hub.resolve_terminal_identity(state)
        assert res["status"] == "VACANT"
        assert res["is_active_terminal"] is False
        assert res["reason"] == "missing_assignment_lease"
        assert res["peer"] == "ag"

    def test_mismatch_legacy_and_lease_peer_differ(self):
        state = {
            "human_interface_peer": "cc",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-123",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            },
        }
        res = hub.resolve_terminal_identity(state)
        assert res["status"] == "MISMATCH"
        assert res["is_active_terminal"] is False
        assert "mismatch" in res["reason"]
        assert res["peer"] == "ag"

    def test_expired_past_timestamp(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        state = {
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-123",
                "expires_at": past.isoformat(),
            },
        }
        res = hub.resolve_terminal_identity(state, now=now)
        assert res["status"] == "EXPIRED"
        assert res["is_active_terminal"] is False
        assert "lease_expired_at" in res["reason"]
        assert res["peer"] == "ag"

    def test_expired_invalid_expiry_timestamp(self):
        state = {
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-123",
                "expires_at": "invalid-date",
            },
        }
        res = hub.resolve_terminal_identity(state)
        assert res["status"] == "EXPIRED"
        assert res["is_active_terminal"] is False
        assert res["reason"] == "missing_or_invalid_expiry_timestamp"

    def test_fresh_active_lease(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=15)
        state = {
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-999",
                "expires_at": future.isoformat(),
            },
        }
        res = hub.resolve_terminal_identity(state, now=now)
        assert res["status"] == "FRESH"
        assert res["is_active_terminal"] is True
        assert res["reason"] == "lease_active_and_fresh"
        assert res["peer"] == "ag"
        assert res["profile"] == "deepthink"
        assert res["lease_id"] == "term-lease-999"

    def test_timezone_offset_not_silently_dropped(self):
        """Regression: expires_at must be parsed as real UTC-normalized time,
        not truncated-then-mislabeled-UTC. A lease that (in real UTC) expired
        9 hours ago, but is written with a +09:00 offset, must resolve
        EXPIRED -- not FRESH via a 9-hour-wrong wall-clock comparison."""
        now_utc = datetime.now(timezone.utc)
        # In real UTC this is now_utc - 9h -- already well expired -- but its
        # wall-clock digits (ignoring the offset) equal "now" in +09:00.
        local_wall_clock_now = now_utc.astimezone(timezone(timedelta(hours=9)))
        expires_at_str = local_wall_clock_now.isoformat()
        state = {
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-tz",
                "expires_at": expires_at_str,
            },
        }
        res = hub.resolve_terminal_identity(state, now=now_utc)
        assert res["status"] == "EXPIRED"
        assert res["is_active_terminal"] is False

    def test_falsy_close_reason_still_treated_as_closed(self):
        """Regression: close_reason="" (or any falsy-but-present value) must
        still mark the lease closed -- a bare truthiness check would silently
        skip this and fall through to the (possibly still-future) expiry."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        state = {
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-closed",
                "expires_at": future,
                "close_reason": "",
            },
        }
        res = hub.resolve_terminal_identity(state)
        assert res["status"] == "EXPIRED"
        assert res["is_active_terminal"] is False

    def test_cleared_legacy_pointer_with_orphaned_lease_is_not_fresh(self):
        """Regression: _normalize_runtime_files clears human_interface_peer to
        None for a disabled/retired peer but doesn't touch
        human_interface_assignment. A None legacy pointer must NOT be treated
        as "no opinion, trust the lease" -- an orphaned lease for a
        peer the canonical pointer no longer names must not resolve FRESH."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        state = {
            "human_interface_peer": None,
            "human_interface_assignment": {
                "peer": "ag",
                "profile": "deepthink",
                "lease_id": "term-lease-orphan",
                "expires_at": future,
            },
        }
        res = hub.resolve_terminal_identity(state)
        assert res["status"] == "MISMATCH"
        assert res["is_active_terminal"] is False


class TestTerminalHandoffAndLeaseLifecycle:
    """Stateful lease lifecycle tests for handoff, heartbeat, and close."""

    @pytest.fixture
    def setup_ai_root(self, tmp_path):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        state = {
            "version": 1,
            "human_interface_peer": "cc",
            "human_interface_assignment": {
                "peer": "cc",
                "profile": "claude",
                "lease_id": "term-lease-initial",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            },
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return ai_root

    def test_action_terminal_handoff_mints_lease(self, setup_ai_root):
        ai_root = setup_ai_root
        assignment = hub.action_terminal_handoff(ai_root, "cc", "ag", reason="test_handoff")
        assert assignment["peer"] == "ag"
        assert assignment["lease_id"].startswith("term-lease-")
        assert "expires_at" in assignment

        state = hub._read_json(ai_root / "state.json")
        assert state["human_interface_peer"] == "ag"
        assert state["human_interface_assignment"]["lease_id"] == assignment["lease_id"]

        term_info = hub.resolve_terminal_identity(state)
        assert term_info["status"] == "FRESH"
        assert term_info["is_active_terminal"] is True
        assert term_info["peer"] == "ag"

    def test_action_terminal_heartbeat_renews_active_lease(self, setup_ai_root):
        ai_root = setup_ai_root
        state = hub._read_json(ai_root / "state.json")
        lease_id = state["human_interface_assignment"]["lease_id"]

        ok = hub.action_terminal_heartbeat(ai_root, "cc", lease_id, owner_pid=9999)
        assert ok is True

        updated_state = hub._read_json(ai_root / "state.json")
        updated_assignment = updated_state["human_interface_assignment"]
        assert updated_assignment["owner_pid"] == 9999
        assert updated_assignment["lease_id"] == lease_id

    def test_action_terminal_heartbeat_cas_rejection_on_stale_lease(self, setup_ai_root):
        ai_root = setup_ai_root
        ok = hub.action_terminal_heartbeat(ai_root, "cc", "term-lease-stale-id")
        assert ok is False

    def test_action_terminal_close_expires_lease(self, setup_ai_root):
        ai_root = setup_ai_root
        state = hub._read_json(ai_root / "state.json")
        lease_id = state["human_interface_assignment"]["lease_id"]

        ok = hub.action_terminal_close(ai_root, lease_id, reason="user_exit")
        assert ok is True

        updated_state = hub._read_json(ai_root / "state.json")
        term_info = hub.resolve_terminal_identity(updated_state)
        assert term_info["status"] == "EXPIRED"
        assert term_info["is_active_terminal"] is False


class TestDutySweepMismatchResolution:
    """Regression: action_terminal_duty_sweep() must actually correct a
    MISMATCH (recorded human_interface_peer disagrees with the lease's peer),
    not silently no-op forever because it compared the replacement pick
    against the lease's peer instead of the stale recorded pointer."""

    def test_sweep_resolves_a_mismatch_even_when_lease_peer_is_the_eligible_pick(self, tmp_path, monkeypatch):
        ai_root = tmp_path / ".ai"
        ai_root.mkdir()
        # Recorded pointer says "ag"; the lease (e.g. left over from an
        # in-flight handoff, or corrupted by an external write) says "cc".
        state = {
            "version": 1,
            "human_interface_peer": "ag",
            "human_interface_assignment": {
                "peer": "cc",
                "profile": "claude",
                "lease_id": "term-lease-mismatch",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            },
        }
        (ai_root / "state.json").write_text(json.dumps(state), encoding="utf-8")

        handoff_calls = []
        real_handoff = hub.action_terminal_handoff

        def spy_handoff(ai_root_arg, current_peer, next_peer, reason="", **kwargs):
            handoff_calls.append((current_peer, next_peer))
            return real_handoff(ai_root_arg, current_peer, next_peer, reason=reason, **kwargs)

        monkeypatch.setattr(hub, "action_terminal_handoff", spy_handoff)
        # _select_human_interface_peer's own eligibility machinery needs live
        # health/config state this test doesn't set up -- pin its result
        # directly so this test isolates the sweep's comparison logic, not
        # replacement-selection itself (which is untouched by this fix).
        monkeypatch.setattr(
            hub, "_select_human_interface_peer",
            lambda ai_root_arg, now=None: {"peer": "cc", "profile": "claude", "eligible": True},
        )

        hub.action_terminal_duty_sweep(ai_root)

        assert handoff_calls == [("ag", "cc")], (
            "sweep must call action_terminal_handoff(current=ag, next=cc) to "
            "correct the mismatch -- comparing against the lease's own peer "
            "('cc' == 'cc') would wrongly skip the handoff and leave the "
            "recorded pointer stuck on the stale 'ag' forever"
        )
        updated_state = hub._read_json(ai_root / "state.json")
        assert updated_state["human_interface_peer"] == "cc"
