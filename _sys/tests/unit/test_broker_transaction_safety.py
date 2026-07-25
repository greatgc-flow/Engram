"""Tests for Top-5 #1 (mutation broker transaction safety & lock protection).

2026-07-25 (Top-5 #1, ag design draft cross-verified + corrected by cc against
real hub.py before application -- see docs-v2/ops/backlog-design-consensus-
2026-07-24.md). `_try_broker_fallback()` is deleted: a synchronous write must
commit or raise, never silently queue-and-pretend-success. Broker requests now
carry an `expected_revision` (sha256 of the target's raw bytes at queue time)
and `_commit_hub_mutation_request()` rejects a stale request via CAS instead of
silently overwriting newer state (reuses C1's `_commit_host_mutation()` CAS
pattern). Broker request files are written crash-safely (temp file + atomic
rename). `_normalize_runtime_files()` and `action_thread_promote()` wrap their
read-modify-write in `_mutation_lock_resource()` locks.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def test_broker_drain_cas_mismatch_moves_request_to_error_dir(tmp_path):
    """A stale broker request (queued against revision 1) must be rejected once
    the target has advanced to revision 2 -- moved to .ai/broker/error/, and
    revision 2 must survive on disk untouched."""
    ai_root = tmp_path / ".ai"
    hub.ensure_ai_dir(ai_root)

    state_file = ai_root / "state.json"
    rev1_state = {
        "room_id": "room-1", "active_coordinator": "cc",
        "members": {"cc": "s1"}, "updated_at": "2026-07-25T00:00:00",
    }
    hub._write_json_atomic(state_file, rev1_state)

    payload_stale = {
        "room_id": "room-1", "active_coordinator": "cc",
        "members": {"cc": "s1", "stale_peer": "s_stale"},
        "updated_at": "2026-07-25T00:01:00",
    }
    hub.action_broker_submit(ai_root, "state.json", json.dumps(payload_stale), origin="test_worker")

    rev2_state = {
        "room_id": "room-1", "active_coordinator": "ag",
        "members": {"cc": "s1", "ag": "s2"}, "updated_at": "2026-07-25T00:02:00",
    }
    hub._write_json_atomic(state_file, rev2_state)

    hub.action_broker_drain(ai_root, force_tier0=True)

    pending_dir, done_dir, error_dir = hub._broker_dirs(ai_root)
    assert len(list(pending_dir.glob("*.json"))) == 0
    assert len(list(done_dir.glob("*.json"))) == 0
    assert len(list(error_dir.glob("*.json"))) == 1

    current_state = hub._read_json(state_file)
    assert current_state["active_coordinator"] == "ag"
    assert "ag" in current_state["members"]
    assert "stale_peer" not in current_state["members"]


def test_broker_drain_matching_revision_commits_cleanly(tmp_path):
    """A request whose expected_revision still matches the target's current
    hash must commit normally (CAS must not false-positive on a clean drain)."""
    ai_root = tmp_path / ".ai"
    hub.ensure_ai_dir(ai_root)

    state_file = ai_root / "state.json"
    hub._write_json_atomic(state_file, {"room_id": "r1", "active_coordinator": None, "members": {}})

    payload = {"room_id": "r1", "active_coordinator": "cc", "members": {"cc": "s1"}}
    hub.action_broker_submit(ai_root, "state.json", json.dumps(payload), origin="test_worker")

    hub.action_broker_drain(ai_root, force_tier0=True)

    pending_dir, done_dir, error_dir = hub._broker_dirs(ai_root)
    assert len(list(pending_dir.glob("*.json"))) == 0
    assert len(list(error_dir.glob("*.json"))) == 0
    assert len(list(done_dir.glob("*.json"))) == 1
    assert hub._read_json(state_file)["active_coordinator"] == "cc"


def test_deleted_broker_fallback_raises_sandbox_rename_denied_error(monkeypatch, tmp_path):
    """With `_try_broker_fallback()` deleted, a sandbox-denied atomic replace
    must raise SandboxRenameDeniedError directly -- never a silent queued
    'success' that leaves the target file untouched."""
    assert not hasattr(hub, "_try_broker_fallback")

    monkeypatch.setattr(hub, "_is_sandbox_rename_denied", lambda exc: True)

    def mock_os_replace(src, dst):
        raise PermissionError("Access is denied (sandbox rename blocked)")

    monkeypatch.setattr(hub.os, "replace", mock_os_replace)

    target_file = tmp_path / "test.json"
    with pytest.raises(hub.SandboxRenameDeniedError):
        hub._write_json_atomic(target_file, {"key": "val"})
    assert not target_file.exists()


def test_crash_safe_broker_submit(tmp_path):
    """action_broker_submit() writes the pending request via temp-file +
    atomic rename: no .tmp_* remnants, and the committed file carries a real
    64-hex-char expected_revision."""
    ai_root = tmp_path / ".ai"
    hub.ensure_ai_dir(ai_root)

    target_file = ai_root / "state.json"
    hub._write_json_atomic(target_file, {"room_id": "r1", "active_coordinator": None, "members": {}})

    hub.action_broker_submit(
        ai_root, "state.json",
        json.dumps({"room_id": "r1", "active_coordinator": "cc", "members": {}}),
    )

    pending_dir, _, _ = hub._broker_dirs(ai_root)
    pending_files = list(pending_dir.glob("*.json"))
    assert len(pending_files) == 1

    req = hub._read_json(pending_files[0])
    assert req["target"] == "state.json"
    assert len(req["expected_revision"]) == 64

    assert list(pending_dir.glob(".tmp_*")) == []


def test_broker_submit_rejects_invalid_json_payload(tmp_path, capsys):
    """A malformed payload string must exit cleanly with a diagnostic message,
    not propagate a raw json.JSONDecodeError (pre-existing contract, must
    survive the Top-5 #1 rewrite of action_broker_submit)."""
    ai_root = tmp_path / ".ai"
    hub.ensure_ai_dir(ai_root)

    with pytest.raises(SystemExit) as exc_info:
        hub.action_broker_submit(ai_root, "state.json", "{not valid json")
    assert exc_info.value.code == 1
    assert "invalid JSON payload" in capsys.readouterr().err


def test_normalize_runtime_files_acquires_locks_and_preserves_t83_lease_matching(tmp_path):
    """_normalize_runtime_files() must lock nodes/state/leases individually,
    using the SAME plain lock names ("nodes"/"state"/"leases") already used
    by every other writer of those files (action_init_session, register-node,
    lease-sweep, etc.) -- a different lock name (e.g. the C1/broker
    _mutation_lock_resource() naming) would not actually serialize against
    those other writers and can silently drop concurrent writes (reproduced
    live: 4 parallel init-session processes lost 3 of 4 members before this
    was caught and fixed). Must also keep matching leases by
    entry['peer_id'] (T83: leases.json is keyed by lease_id/uuid, not peer_id)
    -- a dict-key-based match would silently drop every real lease."""
    ai_root = tmp_path / ".ai"
    ai_root.mkdir(parents=True, exist_ok=True)

    (ai_root / "nodes.json").write_text(json.dumps({"version": "2", "nodes": {}}), encoding="utf-8")
    (ai_root / "state.json").write_text(
        json.dumps({"members": {}, "active_coordinator": None, "role_assignments": {}}),
        encoding="utf-8",
    )
    lease_id = "11111111-1111-1111-1111-111111111111"
    (ai_root / "leases.json").write_text(
        json.dumps({lease_id: {"peer_id": "cc", "resource": "some_resource"}}),
        encoding="utf-8",
    )

    locked_resources = []
    real_get_lock = hub._get_lock

    def mock_get_lock(root, resource):
        locked_resources.append(resource)
        return real_get_lock(root, resource)

    with _patched(hub, "_get_lock", mock_get_lock), \
         _patched(hub, "_runtime_node_policy", lambda: ({"cc"}, {"cc"}, set())):
        hub._normalize_runtime_files(ai_root)

    assert set(locked_resources) == {"nodes", "state", "leases"}

    remaining_leases = hub._read_json(ai_root / "leases.json")
    assert lease_id in remaining_leases, (
        "a real lease keyed by lease_id (not peer_id) must survive normalization "
        "as long as its peer_id is a currently-configured, active root"
    )


class _patched:
    """Minimal monkeypatch-free attribute swap for use outside a pytest fixture
    (this test builds its own lock-call spy without needing the monkeypatch
    fixture's teardown ordering)."""

    def __init__(self, obj, name, value):
        self._obj = obj
        self._name = name
        self._value = value

    def __enter__(self):
        self._orig = getattr(self._obj, self._name)
        setattr(self._obj, self._name, self._value)
        return self._value

    def __exit__(self, *exc):
        setattr(self._obj, self._name, self._orig)


def test_action_thread_promote_acquires_mailbox_lock(tmp_path):
    """action_thread_promote() must wrap its mailbox read-modify-write in the
    SAME "mailbox" lock name already used by every other mailbox.json writer
    (action_end_session, message send/mark-read, etc.) -- a different lock
    name (e.g. the C1/broker _mutation_lock_resource() naming) would not
    actually serialize against those other writers. Must still promote the
    message correctly."""
    ai_root = tmp_path / ".ai"
    hub.ensure_ai_dir(ai_root)

    mailbox_path = ai_root / "mailbox.json"
    msg_id = "msg-101"
    hub._write_json_atomic(mailbox_path, {
        "messages": [{"id": msg_id, "from": "cc", "msg": "test message", "ts": "2026-07-25T00:00:00"}],
        "unread_count": 1,
    })

    locked_resources = []
    real_get_lock = hub._get_lock

    def mock_get_lock(root, resource):
        locked_resources.append(resource)
        return real_get_lock(root, resource)

    with _patched(hub, "_get_lock", mock_get_lock):
        hub.action_thread_promote(ai_root, msg_id, "topic-general", "cc")

    assert "mailbox" in locked_resources

    mbox = hub._read_json(mailbox_path)
    assert mbox["messages"][0]["promoted_to"] == "topic-general"
