"""Legacy backup producers write into the backup registry (design section 8.2): move, never delete."""
import json
from pathlib import Path

import pytest

from core import backups, provisioner as pv
from _sys.core import layout_migration as lm


def _registered(sys_dir, kind):
    return [r for r in backups.scan(sys_dir).valid if r.kind == kind]


# ---- backups.create_file ------------------------------------------------------------------------

def test_create_file_moves_the_file_into_a_committed_registry_entry(tmp_path):
    sys_dir = tmp_path / "_sys"
    src = tmp_path / "Engram.exe.old"
    src.write_bytes(b"EXE")
    ref = backups.create_file(sys_dir, "core-update", src, reason="r", op_id="o", label="x")
    assert not src.exists()
    assert (ref.path / backups.PAYLOAD / "Engram.exe.old").read_bytes() == b"EXE"
    assert backups.scan(sys_dir).valid[0].meta["state"] == "committed"


def test_create_file_copy_keeps_the_original(tmp_path):
    sys_dir = tmp_path / "_sys"
    src = tmp_path / "a.json"
    src.write_text("{}")
    ref = backups.create_file(sys_dir, "state", src, reason="r", op_id="o", label="a", copy=True)
    assert src.read_text() == "{}"
    assert (ref.path / backups.PAYLOAD / "a.json").read_text() == "{}"


def test_create_file_rejects_missing_source_and_bad_kind(tmp_path):
    with pytest.raises(FileNotFoundError):
        backups.create_file(tmp_path, "state", tmp_path / "nope", reason="r", op_id="o", label="a")
    f = tmp_path / "f"
    f.write_text("x")
    with pytest.raises(ValueError):
        backups.create_file(tmp_path, "bogus", f, reason="r", op_id="o", label="a")
    assert f.exists()


# ---- provisioner._install_atomic ----------------------------------------------------------------------

@pytest.fixture
def install_env(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    target_root = sys_dir / "tools"
    target_root.mkdir(parents=True)
    active = target_root / "tool"
    active.mkdir()
    (active / "bin.exe").write_text("old_content")
    monkeypatch.setattr(pv, "_secure_download", lambda url, dest: dest.write_text("new"))
    monkeypatch.setattr(pv, "_hash_file", lambda path, algo: "h")
    monkeypatch.setattr(pv, "_run_canary", lambda tmp_dir, canary: (True, "v"))
    cfg = {"url": "https://example.com/tool.zip", "version": "2.0.0",
           "install_mechanism": "exe_tool", "bin": "bin.exe"}
    return sys_dir, target_root, active, cfg


def test_install_atomic_registers_the_replaced_dir(install_env):
    sys_dir, target_root, active, cfg = install_env
    res = pv._install_atomic("tool", cfg, active / ".m.json", target_root, sys_dir)
    assert res["status"] == "success"
    assert not (target_root / "tool_old").exists()
    refs = _registered(sys_dir, "legacy-old")
    assert len(refs) == 1 and refs[0].meta["state"] == "committed"
    assert (refs[0].path / backups.PAYLOAD / "bin.exe").read_text() == "old_content"
    assert (active / "bin.exe").exists()


def test_install_atomic_leaves_a_preexisting_legacy_old_dir_alone(install_env):
    sys_dir, target_root, active, cfg = install_env
    legacy = target_root / "tool_old"
    legacy.mkdir()
    (legacy / "keep.txt").write_text("k")
    pv._install_atomic("tool", cfg, active / ".m.json", target_root, sys_dir)
    assert (legacy / "keep.txt").read_text() == "k"


def test_install_atomic_registration_failure_leaves_original_intact(install_env, monkeypatch):
    sys_dir, target_root, active, cfg = install_env

    def boom(*a, **k):
        raise OSError(5, "locked")

    monkeypatch.setattr(backups, "create", boom)
    res = pv._install_atomic("tool", cfg, active / ".m.json", target_root, sys_dir)
    assert res["status"] == "in_use_retry_at_session_boundary"
    assert (active / "bin.exe").read_text() == "old_content"


def test_install_atomic_swap_failure_restores_from_the_registry(install_env, monkeypatch):
    sys_dir, target_root, active, cfg = install_env
    real = pv._safe_rename

    def flaky(src, dst, *a, **k):
        if src.name.endswith("_tmp"):
            raise OSError(5, "swap locked")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(pv, "_safe_rename", flaky)
    res = pv._install_atomic("tool", cfg, active / ".m.json", target_root, sys_dir)
    assert res["status"] == "in_use_retry_at_session_boundary"
    assert (active / "bin.exe").read_text() == "old_content"
    refs = _registered(sys_dir, "legacy-old")
    assert [r.meta["state"] for r in refs] == ["restored"]


# ---- layout_migration -----------------------------------------------------------------------------------

def test_pre_merge_copy_failure_aborts_before_the_live_file_is_rewritten(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    live, defaults, base = sys_dir, sys_dir / "defaults", sys_dir / "data" / "state" / "defaults-base"
    for d in (defaults, base):
        d.mkdir(parents=True)
    for d, v in ((live, "1"), (defaults, "2"), (base, "1")):
        (d / "runtimes.json").write_text(json.dumps({"runtimes": {"x": {"version": v}}}))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(lm.backups, "create_file", boom)
    with pytest.raises(SystemExit):
        lm.merge_declarations_impl(defaults, live, base, sys_dir / "m", ["runtimes.json"])
    assert json.loads((live / "runtimes.json").read_text())["runtimes"]["x"]["version"] == "1"


def _migrate(tmp_path):
    base_dir = tmp_path / "base"
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir(parents=True)
    return base_dir, sys_dir


def test_engram_exe_old_is_registered_not_deleted(tmp_path):
    base_dir, sys_dir = _migrate(tmp_path)
    (base_dir / "Engram.exe.old").write_bytes(b"OLD")
    lm.migrate_layout(base_dir, sys_dir)
    assert not (base_dir / "Engram.exe.old").exists()
    refs = _registered(sys_dir, "core-update")
    assert len(refs) == 1 and refs[0].meta["state"] == "committed"
    assert (refs[0].path / backups.PAYLOAD / "Engram.exe.old").read_bytes() == b"OLD"


def test_engram_exe_old_registration_failure_leaves_it_in_place(tmp_path, monkeypatch):
    base_dir, sys_dir = _migrate(tmp_path)
    (base_dir / "Engram.exe.old").write_bytes(b"OLD")

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr(lm.backups, "create_file", boom)
    lm.migrate_layout(base_dir, sys_dir)
    assert (base_dir / "Engram.exe.old").read_bytes() == b"OLD"


def test_core_update_backup_dir_is_registered_before_temp_cleanup(tmp_path):
    base_dir, sys_dir = _migrate(tmp_path)
    bdir = sys_dir / "data" / "temp" / "core-update" / "1.2.3" / "backup" / "_sys" / "core"
    bdir.mkdir(parents=True)
    (bdir / "x.py").write_text("old code")
    lm.migrate_layout(base_dir, sys_dir)
    refs = _registered(sys_dir, "core-update")
    assert len(refs) == 1 and refs[0].meta["state"] == "committed"
    assert (refs[0].path / backups.PAYLOAD / "_sys" / "core" / "x.py").read_text() == "old code"
    assert not (sys_dir / "data" / "temp" / "core-update").exists()


def test_core_update_temp_is_kept_when_the_backup_cannot_be_registered(tmp_path, monkeypatch):
    base_dir, sys_dir = _migrate(tmp_path)
    bfile = sys_dir / "data" / "temp" / "core-update" / "1.2.3" / "backup" / "f.txt"
    bfile.parent.mkdir(parents=True)
    bfile.write_text("keep me")

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr(lm.backups, "create", boom)
    lm.migrate_layout(base_dir, sys_dir)
    assert bfile.read_text() == "keep me"


def test_legacy_adopt_still_works_for_preexisting_old_dirs(tmp_path):
    sys_dir = tmp_path / "_sys"
    old = sys_dir / "env" / "git_old" / "cmd"
    old.mkdir(parents=True)
    (old / "git.exe").write_text("x")
    adopted = backups.adopt_legacy(sys_dir)
    assert len(adopted) == 1 and not (sys_dir / "env" / "git_old").exists()
