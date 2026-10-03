"""Tests for core.env_lock (design: docs/design/engram-env-resilience-design-2026-10-02.md, section 9).

The lock is an exclusive-create file ({pid, start_time, op_id}); stale only if the
owning pid is dead or its start_time differs; stale locks are broken atomically.
"""
import json
import threading
from pathlib import Path

import pytest

from core import env_lock


def _probe_factory(alive: dict):
    """alive maps pid -> start_time; absent pid means the process is dead."""
    def probe(pid):
        return alive.get(pid)
    return probe


@pytest.fixture
def sys_dir(tmp_path):
    d = tmp_path / "_sys"
    (d / "data" / "state").mkdir(parents=True)
    return d


def test_acquire_creates_lock_file_with_owner_record(sys_dir):
    h = env_lock.acquire(sys_dir, "op-1", pid=100, start_time=111.0,
                         process_probe=_probe_factory({100: 111.0}))
    data = json.loads(env_lock.lock_path(sys_dir).read_text(encoding="utf-8"))
    assert data == {"pid": 100, "start_time": 111.0, "op_id": "op-1"}
    h.release()
    assert not env_lock.lock_path(sys_dir).exists()


def test_second_acquire_while_owner_alive_is_busy(sys_dir):
    probe = _probe_factory({100: 111.0, 200: 222.0})
    env_lock.acquire(sys_dir, "op-1", pid=100, start_time=111.0, process_probe=probe)
    with pytest.raises(env_lock.EnvLockBusy) as exc:
        env_lock.acquire(sys_dir, "op-2", pid=200, start_time=222.0, process_probe=probe)
    assert exc.value.owner["op_id"] == "op-1"
    # the original lock is untouched
    assert json.loads(env_lock.lock_path(sys_dir).read_text(encoding="utf-8"))["op_id"] == "op-1"


def test_stale_lock_dead_pid_is_broken(sys_dir):
    probe = _probe_factory({200: 222.0})  # pid 100 is dead
    env_lock.lock_path(sys_dir).write_text(
        json.dumps({"pid": 100, "start_time": 111.0, "op_id": "old"}), encoding="utf-8")
    h = env_lock.acquire(sys_dir, "op-2", pid=200, start_time=222.0, process_probe=probe)
    assert json.loads(env_lock.lock_path(sys_dir).read_text(encoding="utf-8"))["op_id"] == "op-2"
    h.release()
    # no leftover broken-lock debris next to the lock
    assert [p.name for p in env_lock.lock_path(sys_dir).parent.iterdir()
            if p.name.startswith("env-op.lock")] == []


def test_stale_lock_pid_reused_with_different_start_time_is_broken(sys_dir):
    probe = _probe_factory({100: 999.0, 200: 222.0})  # pid 100 alive but a different process
    env_lock.lock_path(sys_dir).write_text(
        json.dumps({"pid": 100, "start_time": 111.0, "op_id": "old"}), encoding="utf-8")
    h = env_lock.acquire(sys_dir, "op-2", pid=200, start_time=222.0, process_probe=probe)
    assert h.op_id == "op-2"


def test_corrupt_lock_file_is_treated_as_stale(sys_dir):
    import os, time
    lp = env_lock.lock_path(sys_dir)
    lp.write_text("{not json", encoding="utf-8")
    old = time.time() - 60
    os.utime(lp, (old, old))
    h = env_lock.acquire(sys_dir, "op-3", pid=1, start_time=1.0,
                         process_probe=_probe_factory({1: 1.0}))
    assert h.op_id == "op-3"


def test_guard_releases_on_exception(sys_dir):
    probe = _probe_factory({1: 1.0})
    with pytest.raises(RuntimeError):
        with env_lock.guard(sys_dir, "op-g", pid=1, start_time=1.0, process_probe=probe):
            assert env_lock.lock_path(sys_dir).exists()
            raise RuntimeError("boom")
    assert not env_lock.lock_path(sys_dir).exists()


def test_release_is_idempotent_and_does_not_remove_foreign_lock(sys_dir):
    probe = _probe_factory({1: 1.0, 2: 2.0})
    h = env_lock.acquire(sys_dir, "op-a", pid=1, start_time=1.0, process_probe=probe)
    h.release()
    h.release()  # second call is a no-op
    other = env_lock.acquire(sys_dir, "op-b", pid=2, start_time=2.0, process_probe=probe)
    h.release()  # stale handle must not delete the new owner's lock
    assert env_lock.lock_path(sys_dir).exists()
    other.release()


def test_exactly_one_winner_under_contention(sys_dir):
    probe = _probe_factory({i: float(i) for i in range(1, 17)})
    winners, busy = [], []
    barrier = threading.Barrier(16)

    def worker(i):
        barrier.wait()
        try:
            winners.append(env_lock.acquire(sys_dir, f"op-{i}", pid=i, start_time=float(i),
                                            process_probe=probe))
        except env_lock.EnvLockBusy:
            busy.append(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, 17)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(winners) == 1
    assert len(busy) == 15


def test_inspect_reports_state_without_mutating(sys_dir):
    probe = _probe_factory({100: 111.0})
    assert env_lock.inspect(sys_dir, process_probe=probe) == {"state": "free"}
    env_lock.acquire(sys_dir, "op-1", pid=100, start_time=111.0, process_probe=probe)
    info = env_lock.inspect(sys_dir, process_probe=probe)
    assert info["state"] == "held" and info["owner"]["op_id"] == "op-1"
    stale = _probe_factory({})
    info = env_lock.inspect(sys_dir, process_probe=stale)
    assert info["state"] == "stale"
    assert env_lock.lock_path(sys_dir).exists()  # inspect never breaks the lock


def test_default_probe_sees_current_process():
    import os
    info = env_lock.default_process_probe(os.getpid())
    assert info is not None
    assert env_lock.default_process_probe(2**31 - 7) is None


def test_fresh_unreadable_lock_is_assumed_mid_write_not_stale(sys_dir):
    # Covers the exFAT fallback window: an empty/partial record younger than the grace
    # period must not be broken by a concurrent starter.
    env_lock.lock_path(sys_dir).write_text("", encoding="utf-8")
    with pytest.raises(env_lock.EnvLockBusy):
        env_lock.acquire(sys_dir, "op-x", pid=1, start_time=1.0,
                         process_probe=_probe_factory({1: 1.0}))


def test_no_temp_debris_after_acquire_and_contention(sys_dir):
    probe = _probe_factory({1: 1.0, 2: 2.0})
    env_lock.acquire(sys_dir, "a", pid=1, start_time=1.0, process_probe=probe)
    with pytest.raises(env_lock.EnvLockBusy):
        env_lock.acquire(sys_dir, "b", pid=2, start_time=2.0, process_probe=probe)
    names = [p.name for p in env_lock.lock_path(sys_dir).parent.iterdir()]
    assert names == [env_lock.LOCK_FILENAME]


def test_fallback_when_hard_links_unsupported(sys_dir, monkeypatch):
    def no_link(src, dst):
        raise OSError(1, "function not supported")
    monkeypatch.setattr(env_lock.os, "link", no_link)
    probe = _probe_factory({1: 1.0, 2: 2.0})
    h = env_lock.acquire(sys_dir, "a", pid=1, start_time=1.0, process_probe=probe)
    with pytest.raises(env_lock.EnvLockBusy):
        env_lock.acquire(sys_dir, "b", pid=2, start_time=2.0, process_probe=probe)
    h.release()
