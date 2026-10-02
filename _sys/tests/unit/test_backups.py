"""Tests for core.backups - the environment backup registry (design section 8).

Ownership is marker-based: every registry dir holds BACKUP.json and a payload/ dir.
Tidy may only ever delete marker-bearing dirs under data/backups/env.
"""
import errno
import json
import os
import shutil
from pathlib import Path

import pytest

from core import backups

NOW = "2026-10-10T00:00:00Z"


def days_ago(n, base="2026-10-10T00:00:00Z"):
    import datetime
    t = datetime.datetime.strptime(base, "%Y-%m-%dT%H:%M:%SZ") - datetime.timedelta(days=n)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def sys_dir(tmp_path):
    d = tmp_path / "_sys"
    (d / "data").mkdir(parents=True)
    return d


def _src(tmp_path, name="victim", files=("a.txt",)):
    d = tmp_path / "src" / name
    d.mkdir(parents=True)
    for f in files:
        (d / f).write_text(f"content of {f}", encoding="utf-8")
    return d


def _make(sys_dir, tmp_path, kind="venv", label="x", when=NOW, committed=True, size_files=("a.txt",), op="op-1"):
    ref = backups.create(sys_dir, kind, _src(tmp_path, f"{kind}-{label}-{when[:10]}", size_files),
                         reason="test", op_id=op, label=label, now=when)
    if committed:
        backups.commit(ref, now=when)
    return ref


# ---- create / commit ---------------------------------------------------------------

def test_create_moves_source_into_payload_and_writes_pending_marker(sys_dir, tmp_path):
    src = _src(tmp_path)
    ref = backups.create(sys_dir, "venv", src, reason="rebuild", op_id="op-1", label="old", now=NOW)
    assert not src.exists()
    assert (ref.path / backups.PAYLOAD / "a.txt").read_text(encoding="utf-8") == "content of a.txt"
    meta = json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))
    assert meta["state"] == "pending" and meta["kind"] == "venv" and meta["op_id"] == "op-1"
    assert meta["source_path"] == str(src) and meta["pinned"] is False
    assert meta["size_bytes"] == len("content of a.txt")
    assert ref.path.parent.parent == backups.backups_root(sys_dir)


def test_marker_is_written_before_the_payload_moves(sys_dir, tmp_path):
    src = _src(tmp_path)

    def exploding_rename(a, b):
        raise PermissionError("locked by AV")

    with pytest.raises(PermissionError):
        backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW,
                       rename=exploding_rename, sleep=lambda s: None)
    assert src.exists() and (src / "a.txt").exists()          # source untouched
    entries = backups.scan(sys_dir)
    assert len(entries.valid) == 1 and entries.valid[0].meta["state"] == "pending"  # journaled intent


def test_create_rejects_bad_input(sys_dir, tmp_path):
    src = _src(tmp_path)
    with pytest.raises(ValueError):
        backups.create(sys_dir, "nonsense", src, reason="r", op_id="o", label="l", now=NOW)
    with pytest.raises(FileNotFoundError):
        backups.create(sys_dir, "venv", tmp_path / "missing", reason="r", op_id="o", label="l", now=NOW)
    for bad in ("..\\evil", "a/b", "", "x" * 200):
        with pytest.raises(ValueError):
            backups.create(sys_dir, "venv", src, reason="r", op_id="o", label=bad, now=NOW)


def test_create_retries_rename_with_bounded_backoff(sys_dir, tmp_path):
    src = _src(tmp_path)
    calls = {"n": 0}
    real = os.rename

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("AV scan")
        return real(a, b)

    sleeps = []
    ref = backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW,
                         rename=flaky, sleep=sleeps.append)
    assert calls["n"] == 3 and sleeps == [0.1, 0.2]
    assert (ref.path / backups.PAYLOAD).is_dir()


def test_rename_gives_up_after_five_attempts(sys_dir, tmp_path):
    src = _src(tmp_path)
    calls = {"n": 0}

    def always(a, b):
        calls["n"] += 1
        raise PermissionError("locked")

    with pytest.raises(PermissionError):
        backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW,
                       rename=always, sleep=lambda s: None)
    assert calls["n"] == 5


def test_commit_sets_state_and_starts_the_ttl_clock(sys_dir, tmp_path):
    ref = _make(sys_dir, tmp_path, committed=False, when=days_ago(3))
    backups.commit(ref, now=NOW)
    meta = json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))
    assert meta["state"] == "committed" and meta["committed_at"] == NOW
    backups.commit(ref, now=days_ago(0, "2026-12-01T00:00:00Z"))   # idempotent: keeps first commit time
    assert json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))["committed_at"] == NOW


def test_pin_and_unpin(sys_dir, tmp_path):
    ref = _make(sys_dir, tmp_path)
    backups.pin(ref)
    assert backups.scan(sys_dir).valid[0].meta["pinned"] is True
    backups.unpin(ref)
    assert backups.scan(sys_dir).valid[0].meta["pinned"] is False


# ---- scan ----------------------------------------------------------------------------------

def test_scan_ignores_unmarked_dirs_and_reports_invalid_markers(sys_dir, tmp_path):
    good = _make(sys_dir, tmp_path)
    root = backups.backups_root(sys_dir)
    (root / "venv" / "20261010T000000Z-stray").mkdir(parents=True)            # no marker
    bad = root / "venv" / "20261010T000001Z-bad"
    bad.mkdir()
    (bad / backups.MARKER).write_text("{broken", encoding="utf-8")
    res = backups.scan(sys_dir)
    assert [r.path for r in res.valid] == [good.path]
    assert [p.name for p in res.invalid] == ["20261010T000001Z-bad"]
    assert [p.name for p in res.unmarked] == ["20261010T000000Z-stray"]


def test_scan_of_missing_root_is_empty(sys_dir):
    res = backups.scan(sys_dir)
    assert res.valid == [] and res.invalid == [] and res.unmarked == []


# ---- restore -------------------------------------------------------------------------------------

def test_restore_moves_payload_back_to_the_original_path(sys_dir, tmp_path):
    src = _src(tmp_path)
    ref = backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW)
    backups.commit(ref, now=NOW)
    restored = backups.restore(ref)
    assert restored == src and (src / "a.txt").exists()
    assert not (ref.path / backups.PAYLOAD).exists()


def test_restore_refuses_to_overwrite(sys_dir, tmp_path):
    src = _src(tmp_path)
    ref = backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW)
    src.mkdir()
    with pytest.raises(FileExistsError):
        backups.restore(ref)


# ---- cross-volume fallback ---------------------------------------------------------------------------

def _exdev(a, b):
    raise OSError(errno.EXDEV, "cross-device link")


def test_cross_volume_falls_back_to_verified_copy_then_delete(sys_dir, tmp_path):
    src = _src(tmp_path, files=("a.txt", "sub/b.txt")) if False else _src(tmp_path)
    (src / "sub").mkdir()
    (src / "sub" / "b.txt").write_text("bbb", encoding="utf-8")
    ref = backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW, rename=_exdev)
    assert not src.exists()
    assert (ref.path / backups.PAYLOAD / "sub" / "b.txt").read_text(encoding="utf-8") == "bbb"


def test_cross_volume_copy_verification_failure_keeps_the_source(sys_dir, tmp_path, monkeypatch):
    src = _src(tmp_path)
    real_copy = shutil.copytree

    def corrupting_copy(s, d, **kw):
        out = real_copy(s, d, **kw)
        (Path(d) / "a.txt").write_text("tampered", encoding="utf-8")
        return out

    monkeypatch.setattr(backups.shutil, "copytree", corrupting_copy)
    with pytest.raises(backups.BackupVerificationError):
        backups.create(sys_dir, "venv", src, reason="r", op_id="o", label="l", now=NOW, rename=_exdev)
    assert (src / "a.txt").read_text(encoding="utf-8") == "content of a.txt"   # never deleted unverified


# ---- retention ---------------------------------------------------------------------------------------------

def _plan(sys_dir, now=NOW, **kw):
    return backups.plan_retention(backups.scan(sys_dir).valid, now=now, **kw)


def _names(plan):
    return sorted(r.path.name for r, _ in plan.delete)


def test_nothing_is_deleted_inside_ttl(sys_dir, tmp_path):
    _make(sys_dir, tmp_path, "venv", "a", when=days_ago(3))
    _make(sys_dir, tmp_path, "venv", "b", when=days_ago(1))
    assert _plan(sys_dir).delete == []


def test_ttl_expired_but_min_keep_protects_the_newest(sys_dir, tmp_path):
    only = _make(sys_dir, tmp_path, "venv", "only", when=days_ago(30))     # venv: min_keep 1, ttl 7
    assert _plan(sys_dir).delete == []
    newer = _make(sys_dir, tmp_path, "venv", "newer", when=days_ago(20))
    plan = _plan(sys_dir)
    assert [r.path for r, _ in plan.delete] == [only.path]                  # older one goes, newest kept
    assert newer.path not in [r.path for r, _ in plan.delete]


def test_ttl_clock_starts_at_commit_not_at_creation(sys_dir, tmp_path):
    ref = backups.create(sys_dir, "venv", _src(tmp_path, "old"), reason="r", op_id="o", label="l", now=days_ago(30))
    backups.commit(ref, now=days_ago(2))                                    # created long ago, committed 2 days ago
    other = _make(sys_dir, tmp_path, "venv", "newer", when=days_ago(1))
    assert ref.path not in [r.path for r, _ in _plan(sys_dir).delete]


def test_pinned_is_never_deleted(sys_dir, tmp_path):
    a = _make(sys_dir, tmp_path, "venv", "a", when=days_ago(40))
    _make(sys_dir, tmp_path, "venv", "b", when=days_ago(30))
    _make(sys_dir, tmp_path, "venv", "c", when=days_ago(20))
    backups.pin(a)
    assert a.path not in [r.path for r, _ in _plan(sys_dir).delete]


def test_pending_is_never_deleted_but_old_orphans_are_marked(sys_dir, tmp_path):
    p = _make(sys_dir, tmp_path, "venv", "p", when=days_ago(5), committed=False, op="op-gone")
    plan = _plan(sys_dir)
    assert plan.delete == []
    assert [r.path for r in plan.orphan_marks] == [p.path]


def test_pending_with_an_active_op_is_not_orphaned(sys_dir, tmp_path):
    _make(sys_dir, tmp_path, "venv", "p", when=days_ago(5), committed=False, op="op-live")
    plan = _plan(sys_dir, active_op_ids={"op-live"})
    assert plan.orphan_marks == []


def test_young_pending_is_not_orphaned_within_the_grace_period(sys_dir, tmp_path):
    _make(sys_dir, tmp_path, "venv", "p", when="2026-10-09T20:00:00Z", committed=False, op="op-gone")
    assert _plan(sys_dir).orphan_marks == []     # 4 hours old < 24 h grace


def test_orphaned_backup_becomes_deletable_only_after_its_own_ttl(sys_dir, tmp_path):
    p = _make(sys_dir, tmp_path, "venv", "p", when=days_ago(30), committed=False, op="op-gone")
    keep = _make(sys_dir, tmp_path, "venv", "keep", when=days_ago(1))
    backups.mark_orphaned(p, now=days_ago(2))
    assert p.path not in [r.path for r, _ in _plan(sys_dir).delete]        # orphaned 2 days ago, ttl 7
    backups.mark_orphaned(p, now=days_ago(9))
    refreshed = backups.scan(sys_dir).valid
    plan = backups.plan_retention(refreshed, now=NOW)
    assert p.path in [r.path for r, _ in plan.delete]


def test_per_kind_policies_differ(sys_dir, tmp_path):
    f = [_make(sys_dir, tmp_path, "venv-freeze", f"f{i}", when=days_ago(10 + i)) for i in range(7)]
    plan = _plan(sys_dir)
    # venv-freeze: min_keep 5, ttl 180 -> nothing deleted at 10-16 days
    assert plan.delete == []
    v = [_make(sys_dir, tmp_path, "venv", f"v{i}", when=days_ago(10 + i)) for i in range(3)]
    assert len(_plan(sys_dir).delete) == 2                                   # venv: min_keep 1, ttl 7


def test_keep_override_can_only_raise_the_floor(sys_dir, tmp_path):
    for i in range(4):
        _make(sys_dir, tmp_path, "venv", f"v{i}", when=days_ago(30 + i))
    assert len(_plan(sys_dir).delete) == 3                                   # policy floor 1
    assert len(_plan(sys_dir, keep_override=3).delete) == 1                  # raised to 3
    assert len(_plan(sys_dir, keep_override=0).delete) == 3                  # cannot lower below the policy floor


def test_size_cap_deletes_oldest_first_but_respects_floor_and_pins(sys_dir, tmp_path):
    big = tuple(["f1.txt"])
    refs = []
    for i, age in enumerate((6, 5, 4, 3)):      # all inside ttl so only the cap can evict
        r = _make(sys_dir, tmp_path, "state", f"s{i}", when=days_ago(age), size_files=big)
        refs.append(r)
    size = refs[0].meta["size_bytes"]
    plan = _plan(sys_dir, size_cap_bytes=size * 2 + 1)
    assert plan.delete and all(reason == "size_cap" for _, reason in plan.delete)
    assert [r.path for r, _ in plan.delete] == [refs[0].path]                # state: min_keep 3 -> only 1 evictable


def test_72h_rule_protects_the_latest_commit_from_the_size_cap(sys_dir, tmp_path):
    a = _make(sys_dir, tmp_path, "legacy-old", "a", when=days_ago(20))
    b = _make(sys_dir, tmp_path, "legacy-old", "b", when="2026-10-09T12:00:00Z")   # 12 h old, newest
    plan = _plan(sys_dir, size_cap_bytes=1)
    assert b.path not in [r.path for r, _ in plan.delete]
    assert a.path in [r.path for r, _ in plan.delete]


def test_unmarked_invalid_and_reparse_dirs_are_never_planned(sys_dir, tmp_path, monkeypatch):
    a = _make(sys_dir, tmp_path, "venv", "a", when=days_ago(40))
    _make(sys_dir, tmp_path, "venv", "b", when=days_ago(1))
    root = backups.backups_root(sys_dir)
    (root / "venv" / "stray").mkdir()
    monkeypatch.setattr(backups, "_is_reparse_point", lambda p: Path(p) == a.path)
    plan = backups.plan_retention(backups.scan(sys_dir).valid, now=NOW)
    assert plan.delete == []        # the only candidate is a reparse point -> refused, not traversed


def test_ref_must_resolve_under_the_registry_root(sys_dir, tmp_path):
    ref = _make(sys_dir, tmp_path, "venv", "a", when=days_ago(40))
    _make(sys_dir, tmp_path, "venv", "b", when=days_ago(1))
    ref.meta["state"] = "committed"
    outside = backups.BackupRef("venv", tmp_path / "elsewhere", dict(ref.meta))
    plan = backups.plan_retention([outside], now=NOW, root=backups.backups_root(sys_dir))
    assert plan.delete == []


def test_planning_never_touches_the_filesystem(sys_dir, tmp_path):
    _make(sys_dir, tmp_path, "venv", "a", when=days_ago(40))
    _make(sys_dir, tmp_path, "venv", "b", when=days_ago(1))
    before = sorted(str(p) for p in backups.backups_root(sys_dir).rglob("*"))
    _plan(sys_dir)
    assert before == sorted(str(p) for p in backups.backups_root(sys_dir).rglob("*"))


def test_default_size_cap_is_two_gib_or_ten_percent_of_free_space():
    assert backups.default_size_cap(free_bytes=100 * 2**30) == 2 * 2**30
    assert backups.default_size_cap(free_bytes=5 * 2**30) == 2**29       # 10% of 5 GiB


# ---- legacy adoption --------------------------------------------------------------------------------------------

def _legacy(sys_dir, name, structure):
    d = sys_dir / "env" / name
    for rel in structure:
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    return d


def test_adopt_legacy_moves_a_structurally_valid_old_dir_into_the_registry(sys_dir):
    old = _legacy(sys_dir, "git_old", ["cmd/git.exe", "etc/gitconfig"])
    adopted = backups.adopt_legacy(sys_dir, now=NOW)
    assert len(adopted) == 1 and not old.exists()
    meta = adopted[0].meta
    assert meta["kind"] == "legacy-old" and meta["state"] == "committed"
    assert (adopted[0].path / backups.PAYLOAD / "cmd" / "git.exe").exists()


def test_adopt_legacy_skips_a_look_alike_without_the_expected_structure(sys_dir):
    impostor = _legacy(sys_dir, "git_old", ["my-notes.txt"])        # name matches, content does not
    assert backups.adopt_legacy(sys_dir, now=NOW) == []
    assert (impostor / "my-notes.txt").exists()


def test_adopt_legacy_requires_confirmation_per_candidate(sys_dir):
    old = _legacy(sys_dir, "vscode_old", ["Code.exe"])
    assert backups.adopt_legacy(sys_dir, now=NOW, confirm=lambda c: False) == []
    assert old.exists()


def test_adopt_legacy_lists_candidates_without_moving_in_dry_run(sys_dir):
    old = _legacy(sys_dir, "nodejs_old", ["node.exe"])
    found = backups.find_legacy_candidates(sys_dir)
    assert [c.name for c in found] == ["nodejs_old"] and old.exists()


def test_adopt_legacy_ignores_non_old_dirs(sys_dir):
    _legacy(sys_dir, "git", ["cmd/git.exe"])
    assert backups.find_legacy_candidates(sys_dir) == []
