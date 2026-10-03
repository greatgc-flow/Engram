"""`engram snapshots` - front-end of the backup registry (design section 10, D10).

list | show | pin | unpin | restore.  restore is dry-run by default, takes the environment
lock, never overwrites, and refuses python/venv kinds until the journal-backed repair engine
exists (design section 9: those restores must go through lock + journal).
"""
import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import backups, env_lock  # noqa: E402

NOW = "2026-10-10T00:00:00Z"


@pytest.fixture
def layout(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    return base, sys_dir


def _ctx(sys_dir, *args):
    return {"base_dir": sys_dir.parent, "sys_dir": sys_dir, "paths": {"state": sys_dir / "data" / "state"},
            "command": "snapshots", "args": list(args)}


def _backup(tmp_path, sys_dir, kind="state", label="x", commit=True):
    src = tmp_path / "src" / f"{kind}-{label}"
    src.mkdir(parents=True)
    (src / "f.txt").write_text("data", encoding="utf-8")
    ref = backups.create(sys_dir, kind, src, reason="t", op_id="op", label=label, now=NOW)
    if commit:
        backups.commit(ref, now=NOW)
    return ref, src


def run(sys_dir, *args):
    return backups.snapshots_main(_ctx(sys_dir, *args))


def test_list_shows_kind_state_size_and_pin(layout, tmp_path, capsys):
    base, sys_dir = layout
    ref, _ = _backup(tmp_path, sys_dir, "state", "alpha")
    backups.pin(ref)
    res = run(sys_dir, "list")
    out = capsys.readouterr().out
    assert res["status"] == "success"
    assert ref.path.name in out and "state" in out and "committed" in out and "pinned" in out


def test_list_json_is_machine_readable(layout, tmp_path, capsys):
    base, sys_dir = layout
    _backup(tmp_path, sys_dir, "state", "alpha")
    run(sys_dir, "list", "--json")
    data = json.loads(capsys.readouterr().out)
    assert data[0]["kind"] == "state" and data[0]["state"] == "committed" and "size_bytes" in data[0]


def test_list_empty(layout, capsys):
    base, sys_dir = layout
    res = run(sys_dir, "list")
    assert res["status"] == "success" and "no backups" in capsys.readouterr().out.lower()


def test_list_reports_invalid_and_unmarked_but_never_touches_them(layout, tmp_path, capsys):
    base, sys_dir = layout
    root = backups.backups_root(sys_dir)
    (root / "state" / "stray").mkdir(parents=True)
    bad = root / "state" / "badmarker"
    bad.mkdir()
    (bad / backups.MARKER).write_text("{x", encoding="utf-8")
    run(sys_dir, "list")
    out = capsys.readouterr().out
    assert "unmarked" in out.lower() and "invalid" in out.lower()
    assert (root / "state" / "stray").exists() and bad.exists()


def test_show_by_name_and_by_kind_slash_name(layout, tmp_path, capsys):
    base, sys_dir = layout
    ref, _ = _backup(tmp_path, sys_dir, "state", "alpha")
    assert run(sys_dir, "show", ref.path.name)["status"] == "success"
    assert "source_path" in capsys.readouterr().out
    assert run(sys_dir, "show", f"state/{ref.path.name}")["status"] == "success"


def test_show_unknown_fails(layout):
    base, sys_dir = layout
    assert run(sys_dir, "show", "nope")["status"] == "failed"


def test_ambiguous_name_across_kinds_requires_kind_prefix(layout, tmp_path):
    base, sys_dir = layout
    a, _ = _backup(tmp_path, sys_dir, "state", "same")
    b, _ = _backup(tmp_path, sys_dir, "ai-state", "same")
    assert a.path.name == b.path.name
    assert run(sys_dir, "show", a.path.name)["status"] == "failed"
    assert run(sys_dir, "show", f"ai-state/{b.path.name}")["status"] == "success"


def test_pin_and_unpin(layout, tmp_path):
    base, sys_dir = layout
    ref, _ = _backup(tmp_path, sys_dir)
    assert run(sys_dir, "pin", ref.path.name)["status"] == "success"
    assert backups.scan(sys_dir).valid[0].meta["pinned"] is True
    assert run(sys_dir, "unpin", ref.path.name)["status"] == "success"
    assert backups.scan(sys_dir).valid[0].meta["pinned"] is False


def test_restore_is_dry_run_by_default(layout, tmp_path, capsys):
    base, sys_dir = layout
    ref, src = _backup(tmp_path, sys_dir, "state", "alpha")
    res = run(sys_dir, "restore", ref.path.name)
    assert res["status"] == "success" and not src.exists()
    assert (ref.path / backups.PAYLOAD / "f.txt").exists()
    assert "--apply" in capsys.readouterr().out


def test_restore_apply_moves_the_payload_back_under_the_lock(layout, tmp_path):
    base, sys_dir = layout
    ref, src = _backup(tmp_path, sys_dir, "state", "alpha")
    res = run(sys_dir, "restore", ref.path.name, "--apply")
    assert res["status"] == "success" and (src / "f.txt").exists()
    assert not env_lock.lock_path(sys_dir).exists()


def test_restore_refuses_when_the_lock_is_held(layout, tmp_path):
    base, sys_dir = layout
    ref, src = _backup(tmp_path, sys_dir, "state", "alpha")
    with env_lock.guard(sys_dir, "other"):
        res = run(sys_dir, "restore", ref.path.name, "--apply")
    assert res["status"] == "failed" and not src.exists()


def test_restore_never_overwrites_an_existing_target(layout, tmp_path):
    base, sys_dir = layout
    ref, src = _backup(tmp_path, sys_dir, "state", "alpha")
    src.mkdir(parents=True)
    assert run(sys_dir, "restore", ref.path.name, "--apply")["status"] == "failed"


@pytest.mark.parametrize("kind", ["python", "venv", "venv-interp"])
def test_restore_of_python_and_venv_kinds_is_refused_until_the_repair_engine_exists(layout, tmp_path, kind, capsys):
    base, sys_dir = layout
    ref, src = _backup(tmp_path, sys_dir, kind, "x")
    res = run(sys_dir, "restore", ref.path.name, "--apply")
    assert res["status"] == "failed" and not src.exists()
    assert "repair" in capsys.readouterr().out.lower()


def test_restore_of_a_file_snapshot_kind_is_refused(layout, tmp_path):
    base, sys_dir = layout
    ref = backups.create_text(sys_dir, "venv-freeze", "snapshot.json", "{}", reason="t", op_id="op",
                              label="snap", now=NOW)
    assert run(sys_dir, "restore", ref.path.name, "--apply")["status"] == "failed"


def test_no_args_prints_usage_and_succeeds(layout, capsys):
    base, sys_dir = layout
    res = run(sys_dir)
    assert res["status"] == "success" and "usage" in capsys.readouterr().out.lower()


def test_unknown_action_fails(layout):
    base, sys_dir = layout
    assert run(sys_dir, "explode")["status"] == "failed"


@pytest.mark.parametrize("flag", ["--help", "-h", "/?"])
def test_help_flags(layout, flag, capsys):
    base, sys_dir = layout
    res = run(sys_dir, flag)
    out = capsys.readouterr().out
    assert res["status"] == "success" and "engram snapshots" in out
    assert "list" in out and "restore" in out


# ---- create_text (file-payload backups, used for venv package snapshots) ----------------------------------

def test_create_text_writes_a_committed_file_backup(layout):
    base, sys_dir = layout
    ref = backups.create_text(sys_dir, "venv-freeze", "snapshot.json", '{"a": 1}', reason="t", op_id="op",
                              label="snap", now=NOW)
    assert (ref.path / backups.PAYLOAD / "snapshot.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert ref.meta["state"] == "committed" and ref.meta["committed_at"] == NOW
    assert ref.meta["source_path"] is None
    assert backups.scan(sys_dir).valid[0].path == ref.path
