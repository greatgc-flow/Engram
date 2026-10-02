"""tidy integration of the backup registry (design section 8.3).

`engram tidy` must delete only marker-bearing, expired registry dirs; dry-run by default;
never while the environment lock is held; legacy `*_old` dirs only via --adopt-legacy.
"""
import datetime
import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import backups, env_lock, env_manifest, tidy_temp  # noqa: E402

REAL_WORKTREE = find_root(__file__).parent.resolve()


def _iso(days=0.0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(autouse=True)
def _guard(monkeypatch):
    orig_rm = tidy_temp._rm

    def guarded(path, apply):
        resolved = Path(path).resolve()
        if resolved == REAL_WORKTREE or REAL_WORKTREE in resolved.parents:
            raise AssertionError(f"SAFETY: tidy touched the real worktree: {resolved}")
        return orig_rm(path, apply)

    monkeypatch.setattr(tidy_temp, "_rm", guarded)
    saved = (tidy_temp.ROOT, tidy_temp._SYS_DIR)
    yield
    tidy_temp.configure_paths(root=saved[0], sys_dir=saved[1], explicit_sys_dir=False)


@pytest.fixture
def env(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    (sys_dir / "env").mkdir(parents=True)
    tidy_temp.configure_paths(root=base, sys_dir=sys_dir, explicit_sys_dir=True)
    return base, sys_dir


def _src(tmp_path, name):
    d = tmp_path / "src" / name
    d.mkdir(parents=True)
    (d / "f.txt").write_text("data", encoding="utf-8")
    return d


def _backup(tmp_path, sys_dir, kind, label, age_days, committed=True, op="op"):
    ref = backups.create(sys_dir, kind, _src(tmp_path, f"{kind}-{label}"), reason="t", op_id=op,
                         label=label, now=_iso(age_days))
    if committed:
        backups.commit(ref, now=_iso(age_days))
    return ref


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["tidy_temp.py", *argv])
    rc = tidy_temp.main()
    return rc, capsys.readouterr().out


def test_dry_run_default_lists_but_deletes_nothing(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    old = _backup(tmp_path, sys_dir, "venv", "old", 30)
    _backup(tmp_path, sys_dir, "venv", "new", 1)
    rc, out = _run(monkeypatch, capsys, "--only", "backups")
    assert rc == 0 and "would delete 1 item" in out
    assert old.path.exists()


def test_apply_deletes_only_the_expired_marker_bearing_dir(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    old = _backup(tmp_path, sys_dir, "venv", "old", 30)
    new = _backup(tmp_path, sys_dir, "venv", "new", 1)
    stray = backups.backups_root(sys_dir) / "venv" / "stray-no-marker"
    stray.mkdir()
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert rc == 0
    assert not old.path.exists()
    assert new.path.exists() and stray.exists()


def test_pinned_and_pending_survive_apply(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    pinned = _backup(tmp_path, sys_dir, "venv", "pinned", 40)
    _backup(tmp_path, sys_dir, "venv", "mid", 30)
    _backup(tmp_path, sys_dir, "venv", "new", 1)
    backups.pin(pinned)
    pending = _backup(tmp_path, sys_dir, "python", "pend", 0.2, committed=False)
    _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert pinned.path.exists() and pending.path.exists()


def test_orphaned_pending_is_marked_on_apply_but_not_deleted_yet(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    ref = _backup(tmp_path, sys_dir, "venv", "p", 5, committed=False, op="op-gone")
    _run(monkeypatch, capsys, "--only", "backups", "--apply")
    meta = json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))
    assert meta["state"] == "orphaned" and ref.path.exists()


def test_dry_run_does_not_mark_orphans(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    ref = _backup(tmp_path, sys_dir, "venv", "p", 5, committed=False, op="op-gone")
    _run(monkeypatch, capsys, "--only", "backups")
    assert json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))["state"] == "pending"


def test_active_op_from_the_manifest_protects_its_pending_backup(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    env_manifest.write_manifest(sys_dir, {"schema_version": 1, "install_id": "i" * 36,
                                          "root": {"logical": str(base), "physical": str(base)},
                                          "last_op": {"id": "op-live"}})
    ref = _backup(tmp_path, sys_dir, "venv", "p", 5, committed=False, op="op-live")
    _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert json.loads((ref.path / backups.MARKER).read_text(encoding="utf-8"))["state"] == "pending"


def test_refuses_while_the_env_lock_is_held(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    old = _backup(tmp_path, sys_dir, "venv", "old", 30)
    _backup(tmp_path, sys_dir, "venv", "new", 1)
    with env_lock.guard(sys_dir, "other-op"):
        rc, out = _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert "environment lock" in out.lower() and old.path.exists()


def test_keep_flag_raises_the_floor(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    refs = [_backup(tmp_path, sys_dir, "venv", f"v{i}", 30 + i) for i in range(3)]
    _run(monkeypatch, capsys, "--only", "backups", "--apply", "--keep", "3")
    assert all(r.path.exists() for r in refs)


def test_max_size_flag_applies_a_size_cap(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    a = _backup(tmp_path, sys_dir, "legacy-old", "a", 5)     # inside ttl, only the cap can evict
    b = _backup(tmp_path, sys_dir, "legacy-old", "b", 4)
    c = _backup(tmp_path, sys_dir, "legacy-old", "c", 0.5)   # newest, 72h-protected
    _run(monkeypatch, capsys, "--only", "backups", "--apply", "--max-size-gb", "0.000000001")
    assert not a.path.exists() and not b.path.exists() and c.path.exists()


def test_legacy_old_dirs_are_untouched_without_the_flag(env, monkeypatch, capsys):
    base, sys_dir = env
    old = sys_dir / "env" / "git_old"
    (old / "cmd").mkdir(parents=True)
    (old / "cmd" / "git.exe").write_text("x", encoding="utf-8")
    _run(monkeypatch, capsys, "--only", "backups", "--apply")
    assert old.exists()


def test_adopt_legacy_dry_run_lists_then_apply_adopts(env, monkeypatch, capsys):
    base, sys_dir = env
    old = sys_dir / "env" / "git_old"
    (old / "cmd").mkdir(parents=True)
    (old / "cmd" / "git.exe").write_text("x", encoding="utf-8")
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--adopt-legacy")
    assert "git_old" in out and old.exists()
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--adopt-legacy", "--apply")
    assert not old.exists()
    assert [r.kind for r in backups.scan(sys_dir).valid] == ["legacy-old"]


def test_backups_is_part_of_the_default_targets(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    old = _backup(tmp_path, sys_dir, "venv", "old", 30)
    _backup(tmp_path, sys_dir, "venv", "new", 1)
    rc, out = _run(monkeypatch, capsys)          # no --only
    assert "[backups]" in out and old.path.exists()   # still dry-run


def test_build_plan_exposes_a_backups_category(env, tmp_path):
    base, sys_dir = env
    _backup(tmp_path, sys_dir, "venv", "old", 30)
    _backup(tmp_path, sys_dir, "venv", "new", 1)
    plan = {key: items for _, key, items in tidy_temp.build_plan()}
    assert len(plan["backups"]) == 1
