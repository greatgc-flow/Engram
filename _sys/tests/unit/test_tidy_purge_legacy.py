"""`engram tidy --deep` (implies --adopt-legacy) and `engram tidy --purge-legacy`.

--purge-legacy adopts every structurally valid env/<name>_old dir and deletes ALL legacy-old backups at once
(no 14-day grace). Dry-run by default. It must never touch pinned entries or other backup kinds, and it fails
closed on an unfinished env-op journal, a busy environment lock, or when the running interpreter lives inside
a deletion target.
"""
import builtins
import datetime
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import backups, env_lock, tidy_temp  # noqa: E402

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
    (d / "f.txt").write_text("data" * 100, encoding="utf-8")
    return d


def _backup(tmp_path, sys_dir, kind, label, age_days=0.0):
    ref = backups.create(sys_dir, kind, _src(tmp_path, f"{kind}-{label}"), reason="t", op_id="op",
                         label=label, now=_iso(age_days))
    backups.commit(ref, now=_iso(age_days))
    return ref


def _legacy_dir(sys_dir, name="git"):
    old = sys_dir / "env" / f"{name}_old"
    (old / "cmd").mkdir(parents=True)
    (old / "cmd" / "git.exe").write_text("x" * 2048, encoding="utf-8")
    return old


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["tidy_temp.py", *argv])
    rc = tidy_temp.main()
    return rc, capsys.readouterr().out


def _write_active_journal(sys_dir):
    from core import env_ops
    jp = env_ops.journal_path(sys_dir)
    jp.parent.mkdir(parents=True, exist_ok=True)
    ap = env_ops._append_record_fn(jp, [0], env_ops.utc_now)
    ap("PHASE", name="PLANNED", op_id="op-live", kind="repair")


# ---- --deep implies --adopt-legacy ----------------------------------------------------------------

def test_deep_implies_adopt_legacy(env, monkeypatch, capsys):
    base, sys_dir = env
    old = _legacy_dir(sys_dir)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--deep")
    assert "git_old" in out and "would adopt 1" in out and old.exists()
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--deep", "--apply")
    assert not old.exists()
    assert [r.kind for r in backups.scan(sys_dir).valid] == ["legacy-old"]


# ---- --purge-legacy ------------------------------------------------------------------------------

def test_purge_dry_run_lists_with_sizes_and_changes_nothing(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "fresh", 0)      # well inside the 14-day grace
    cand = _legacy_dir(sys_dir)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy")
    assert rc == 0
    assert "[purge_legacy]" in out and "would delete 2" in out
    assert reg.path.name in out and "git_old" in out
    assert "KiB" in out or "MiB" in out or " B" in out
    assert reg.path.exists() and cand.exists()


def test_purge_apply_yes_adopts_and_deletes_all_legacy_without_grace(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "fresh", 0)
    cand = _legacy_dir(sys_dir)
    venv = _backup(tmp_path, sys_dir, "venv", "keepme", 0)
    state = _backup(tmp_path, sys_dir, "state", "keepme2", 0)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 0
    assert not reg.path.exists() and not cand.exists()
    assert venv.path.exists() and state.path.exists()
    assert [r.kind for r in backups.scan(sys_dir).valid if r.kind == "legacy-old"] == []
    assert "deleted 2" in out


def test_purge_never_deletes_pinned(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    pinned = _backup(tmp_path, sys_dir, "legacy-old", "pinned", 30)
    other = _backup(tmp_path, sys_dir, "legacy-old", "other", 30)
    backups.pin(pinned)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 0 and pinned.path.exists() and not other.path.exists()
    assert "pinned" in out


def test_purge_dry_run_flag_overrides_apply(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--dry-run")
    assert rc == 0 and reg.path.exists() and "would delete" in out


def test_purge_refuses_while_journal_is_active(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    _write_active_journal(sys_dir)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 14
    assert "journal" in out.lower() and "engram repair" in out
    assert reg.path.exists()


def test_purge_dry_run_with_journal_warns_but_deletes_nothing(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    _write_active_journal(sys_dir)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy")
    assert rc == 0 and reg.path.exists()
    assert "--apply would be refused" in out and "journal" in out.lower()


def test_purge_refuses_while_lock_is_busy(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    with env_lock.guard(sys_dir, "other-op"):
        rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 11 and "lock" in out.lower() and reg.path.exists()


def test_purge_refuses_when_lock_is_taken_after_preflight(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)

    def busy(*a, **k):
        raise env_lock.EnvLockBusy({"op_id": "racer"})
    monkeypatch.setattr(env_lock, "acquire", busy)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 11 and reg.path.exists()


def test_purge_holds_the_lock_while_deleting(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    seen = []
    orig = tidy_temp._rm

    def spy(path, apply):
        if apply:
            seen.append(env_lock.inspect(sys_dir)["state"])
        return orig(path, apply)
    monkeypatch.setattr(tidy_temp, "_rm", spy)
    _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert seen and set(seen) == {"held"}


def test_purge_refuses_when_running_interpreter_is_inside_a_target(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "py", 0)
    fake_exe = reg.path / backups.PAYLOAD / "f.txt"
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 11 and "interpreter" in out.lower() and reg.path.exists()


def test_purge_prompt_decline_and_accept(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)
    monkeypatch.setattr(builtins, "input", lambda *_: "n")
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply")
    assert rc == 3 and reg.path.exists() and "cancelled" in out.lower()
    monkeypatch.setattr(builtins, "input", lambda *_: "y")
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply")
    assert rc == 0 and not reg.path.exists()


def test_purge_prompt_eof_cancels(env, tmp_path, monkeypatch, capsys):
    base, sys_dir = env
    reg = _backup(tmp_path, sys_dir, "legacy-old", "x", 0)

    def eof(*_):
        raise EOFError
    monkeypatch.setattr(builtins, "input", eof)
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply")
    assert rc == 3 and reg.path.exists()


def test_purge_requires_backups_category(env, monkeypatch, capsys):
    base, sys_dir = env
    rc, out = _run(monkeypatch, capsys, "--only", "tmp", "--purge-legacy")
    assert rc == 2 and "backups" in out


def test_purge_with_nothing_to_delete_is_a_clean_noop(env, monkeypatch, capsys):
    base, sys_dir = env
    rc, out = _run(monkeypatch, capsys, "--only", "backups", "--purge-legacy", "--apply", "--yes")
    assert rc == 0 and "nothing to purge" in out.lower()
