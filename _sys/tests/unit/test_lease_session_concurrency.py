"""Regression coverage for T83 lease and session-state concurrency."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading
from uuid import UUID

import pytest


SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "core"))

import hub  # noqa: E402


PEER_ID = "cx"
PID_A = 11001
PID_B = 11002


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    """Keep lease files, locks, and peer session state below tmp_path."""
    ai_root = tmp_path / ".ai"
    (ai_root / ".lock").mkdir(parents=True)
    (ai_root / "state.json").write_text(
        json.dumps({"room_id": "room-t83"}), encoding="utf-8"
    )
    (ai_root / "leases.json").write_text("{}", encoding="utf-8")

    session_dir = tmp_path / "peer-session-state"
    session_dir.mkdir()
    monkeypatch.setattr(
        hub,
        "_session_state_path",
        lambda peer_id: session_dir / f"{peer_id}.json",
    )
    return ai_root, session_dir / f"{PEER_ID}.json"


def _read_leases(ai_root: Path) -> dict:
    return json.loads((ai_root / "leases.json").read_text(encoding="utf-8"))


def _read_session_state(session_path: Path) -> dict:
    return json.loads(session_path.read_text(encoding="utf-8"))


def _open_pair(ai_root: Path) -> tuple[str, str]:
    lease_a = hub._lease_open(
        ai_root,
        PEER_ID,
        PID_A,
        300,
        ask_id="ask-a",
        ask_query_file="query-a.txt",
    )
    lease_b = hub._lease_open(
        ai_root,
        PEER_ID,
        PID_B,
        300,
        ask_id="ask-b",
        ask_query_file="query-b.txt",
    )
    assert lease_a is not None
    assert lease_b is not None
    return lease_a, lease_b


def test_overlapping_same_peer_lease_opens_are_independently_addressable(
    isolated_runtime,
):
    ai_root, _ = isolated_runtime
    start = threading.Barrier(2)

    def open_lease(pid: int, ask_id: str) -> str | None:
        start.wait(timeout=5)
        return hub._lease_open(
            ai_root,
            PEER_ID,
            pid,
            300,
            ask_id=ask_id,
            ask_query_file=f"{ask_id}.txt",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(open_lease, PID_A, "ask-a")
        future_b = pool.submit(open_lease, PID_B, "ask-b")
        lease_a = future_a.result(timeout=10)
        lease_b = future_b.result(timeout=10)

    assert lease_a is not None
    assert lease_b is not None
    assert lease_a != lease_b
    assert str(UUID(lease_a)) == lease_a
    assert str(UUID(lease_b)) == lease_b

    leases = _read_leases(ai_root)
    assert set(leases) == {lease_a, lease_b}
    assert leases[lease_a]["peer_id"] == PEER_ID
    assert leases[lease_a]["pid"] == PID_A
    assert leases[lease_a]["ask_id"] == "ask-a"
    assert leases[lease_b]["peer_id"] == PEER_ID
    assert leases[lease_b]["pid"] == PID_B
    assert leases[lease_b]["ask_id"] == "ask-b"


def test_renew_updates_only_the_owned_lease(isolated_runtime, monkeypatch):
    ai_root, _ = isolated_runtime
    lease_a, lease_b = _open_pair(ai_root)
    before = _read_leases(ai_root)
    lease_b_times = {
        "heartbeat_at": before[lease_b]["heartbeat_at"],
        "expires_at": before[lease_b]["expires_at"],
    }

    monkeypatch.setattr(hub, "_now", lambda: "2040-01-02T03:04:05")
    hub._lease_renew(ai_root, lease_a, PID_A, 90)

    after = _read_leases(ai_root)
    assert after[lease_a]["heartbeat_at"] == "2040-01-02T03:04:05"
    assert after[lease_a]["expires_at"] == "2040-01-02T03:05:35"
    assert {
        "heartbeat_at": after[lease_b]["heartbeat_at"],
        "expires_at": after[lease_b]["expires_at"],
    } == lease_b_times


@pytest.mark.parametrize(
    "close_order",
    [("a", "b"), ("b", "a")],
    ids=["a-then-b", "b-then-a"],
)
def test_same_peer_leases_close_independently_in_either_order(
    isolated_runtime, close_order
):
    ai_root, _ = isolated_runtime
    lease_a, lease_b = _open_pair(ai_root)
    leases_by_name = {"a": (lease_a, PID_A), "b": (lease_b, PID_B)}
    status_by_name = {"a": "completed", "b": "retry"}

    first, second = close_order
    first_lease, first_pid = leases_by_name[first]
    hub._lease_close(
        ai_root, first_lease, first_pid, status_by_name[first]
    )

    halfway = _read_leases(ai_root)
    assert halfway[first_lease]["status"] == status_by_name[first]
    second_lease, second_pid = leases_by_name[second]
    assert halfway[second_lease]["status"] == "open"

    hub._lease_close(
        ai_root, second_lease, second_pid, status_by_name[second]
    )
    final = _read_leases(ai_root)
    assert final[lease_a]["status"] == "completed"
    assert final[lease_b]["status"] == "retry"


def test_unknown_or_wrong_pid_lease_mutations_raise_without_changes(
    isolated_runtime,
):
    ai_root, _ = isolated_runtime
    lease_a, _ = _open_pair(ai_root)
    leases_path = ai_root / "leases.json"
    original_bytes = leases_path.read_bytes()
    missing_lease = "00000000-0000-0000-0000-000000000000"

    invalid_mutations = [
        lambda: hub._lease_renew(ai_root, missing_lease, PID_A, 60),
        lambda: hub._lease_renew(ai_root, lease_a, PID_B, 60),
        lambda: hub._lease_close(ai_root, missing_lease, PID_A, "completed"),
        lambda: hub._lease_close(ai_root, lease_a, PID_B, "completed"),
    ]
    for mutate in invalid_mutations:
        with pytest.raises(hub.LeaseOwnershipError):
            mutate()
        assert leases_path.read_bytes() == original_bytes


def test_sweep_expires_only_expired_same_peer_lease(
    isolated_runtime, monkeypatch
):
    ai_root, _ = isolated_runtime
    lease_a, lease_b = _open_pair(ai_root)
    leases = _read_leases(ai_root)
    leases[lease_a]["expires_at"] = "2039-12-31T23:59:59"
    leases[lease_a]["heartbeat_at"] = "2039-12-31T23:59:00"
    leases[lease_b]["expires_at"] = "2040-01-01T00:10:00"
    leases[lease_b]["heartbeat_at"] = "2040-01-01T00:00:00"
    (ai_root / "leases.json").write_text(
        json.dumps(leases, indent=2), encoding="utf-8"
    )
    live_before = dict(leases[lease_b])

    killed = []
    failures = []
    monkeypatch.setattr(hub, "_now", lambda: "2040-01-01T00:00:01")
    monkeypatch.setattr(hub, "_pid_alive", lambda pid: pid == PID_A)
    monkeypatch.setattr(hub, "_kill_process_tree", killed.append)
    monkeypatch.setattr(
        hub,
        "_record_ask_failure",
        lambda *args, **kwargs: failures.append((args, kwargs)),
    )
    monkeypatch.setattr(hub, "_log_p2p", lambda *args, **kwargs: None)

    hub._lease_sweep(ai_root)

    swept = _read_leases(ai_root)
    assert swept[lease_a]["status"] == "expired"
    assert swept[lease_b] == live_before
    assert killed == [PID_A]
    assert len(failures) == 1
    assert failures[0][0][0] == PEER_ID


def test_concurrent_distinct_scope_sessions_all_survive(
    isolated_runtime, monkeypatch
):
    ai_root, session_path = isolated_runtime
    worker_count = 12
    start = threading.Barrier(worker_count)

    # Under the pre-T83 implementation every worker reached _save_session_state
    # only after its unlocked read. Holding those legacy saves here makes the
    # lost-update failure deterministic. The transactional implementation does
    # not call this split read/save helper.
    legacy_save_barrier = threading.Barrier(worker_count)
    real_save = hub._save_session_state

    def synchronize_legacy_saves(peer_id, data, ai_root=None):
        legacy_save_barrier.wait(timeout=5)
        return real_save(peer_id, data, ai_root)

    monkeypatch.setattr(hub, "_save_session_state", synchronize_legacy_saves)

    def set_session(index: int) -> None:
        start.wait(timeout=5)
        hub._set_active_session(
            PEER_ID,
            f"scope-{index}",
            f"session-{index}",
            f"ask-{index}",
            ai_root,
            fingerprint=f"fingerprint-{index}",
        )

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(set_session, index) for index in range(worker_count)]
        for future in futures:
            future.result(timeout=15)

    state = _read_session_state(session_path)
    assert set(state["active"]) == {
        f"scope-{index}" for index in range(worker_count)
    }
    for index in range(worker_count):
        entry = state["active"][f"scope-{index}"]
        assert entry["session_id"] == f"session-{index}"
        assert entry["last_ask_id"] == f"ask-{index}"
        assert entry["fingerprint"] == f"fingerprint-{index}"


def test_concurrent_retire_and_set_preserve_both_transactions(
    isolated_runtime, monkeypatch
):
    ai_root, session_path = isolated_runtime

    def seed(data: dict) -> None:
        data.setdefault("active", {}).update(
            {
                "scope-a": {
                    "session_id": "session-a",
                    "scope_key": "scope-a",
                    "status": "active",
                },
                "scope-stable": {
                    "session_id": "session-stable",
                    "scope_key": "scope-stable",
                    "status": "active",
                },
            }
        )

    seeded = hub._mutate_session_state(PEER_ID, ai_root, seed)
    assert seeded == _read_session_state(session_path)

    # As above, this barrier deterministically exposes any regression back to
    # unlocked-read/locked-save wrappers while remaining unused by the fixed path.
    legacy_save_barrier = threading.Barrier(2)
    real_save = hub._save_session_state

    def synchronize_legacy_saves(peer_id, data, ai_root=None):
        legacy_save_barrier.wait(timeout=5)
        return real_save(peer_id, data, ai_root)

    monkeypatch.setattr(hub, "_save_session_state", synchronize_legacy_saves)
    start = threading.Barrier(2)

    def retire_a() -> None:
        start.wait(timeout=5)
        hub._retire_session(PEER_ID, "scope-a", "test-retire", ai_root)

    def set_b() -> None:
        start.wait(timeout=5)
        hub._set_active_session(
            PEER_ID, "scope-b", "session-b", "ask-b", ai_root
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        retire_future = pool.submit(retire_a)
        set_future = pool.submit(set_b)
        retire_future.result(timeout=10)
        set_future.result(timeout=10)

    state = _read_session_state(session_path)
    assert set(state["active"]) == {"scope-b", "scope-stable"}
    assert state["active"]["scope-b"]["session_id"] == "session-b"
    retired_a = [
        entry for entry in state["history"]
        if entry.get("session_id") == "session-a"
    ]
    assert len(retired_a) == 1
    assert retired_a[0]["status"] == "retired"
    assert retired_a[0]["retire_reason"] == "test-retire"


def test_clear_peer_sessions_retires_all_scopes_in_one_transaction(
    isolated_runtime, monkeypatch
):
    ai_root, session_path = isolated_runtime
    scope_count = 5

    def seed(data: dict) -> None:
        active = data.setdefault("active", {})
        for index in range(scope_count):
            active[f"scope-{index}"] = {
                "session_id": f"session-{index}",
                "scope_key": f"scope-{index}",
                "status": "active",
            }

    hub._mutate_session_state(PEER_ID, ai_root, seed)

    real_get_lock = hub._get_lock
    session_lock_calls = []

    def count_session_lock(root: Path, resource: str):
        if resource == f"ss_{PEER_ID}":
            session_lock_calls.append((root, resource))
        return real_get_lock(root, resource)

    monkeypatch.setattr(hub, "_get_lock", count_session_lock)
    hub._clear_peer_sessions(PEER_ID, "clear-test", ai_root)

    state = _read_session_state(session_path)
    assert state["active"] == {}
    assert len(session_lock_calls) == 1
    assert len(state["history"]) == scope_count
    assert {
        entry["session_id"] for entry in state["history"]
    } == {f"session-{index}" for index in range(scope_count)}
    assert all(entry["status"] == "retired" for entry in state["history"])
    assert all(
        entry["retire_reason"] == "clear-test" for entry in state["history"]
    )
