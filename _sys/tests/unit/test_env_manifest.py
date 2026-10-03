"""Tests for core.env_manifest (design: docs/design/engram-env-resilience-design-2026-10-02.md, section 3)."""
import json
import os
from pathlib import Path

import pytest

from core import env_manifest as em


@pytest.fixture
def sys_dir(tmp_path):
    d = tmp_path / "root" / "_sys"
    (d / "data" / "state").mkdir(parents=True)
    return d


def _sample(root: str = "D:\\Engram"):
    return {
        "schema_version": 1,
        "engram_version": "3.5.0",
        "sys_dir_name": "_sys",
        "install_id": "11111111-1111-1111-1111-111111111111",
        "root": {"logical": root, "physical": root, "volume_serial": "AAAA-BBBB"},
        "python": {"version": "3.14.8"},
        "venv": {"python_version": "3.14.8"},
    }


# ---- read/write ------------------------------------------------------------

def test_read_absent(sys_dir):
    r = em.read_manifest(sys_dir)
    assert r.status == "absent" and r.data is None


def test_write_then_read_roundtrip(sys_dir):
    em.write_manifest(sys_dir, _sample())
    r = em.read_manifest(sys_dir)
    assert r.status == "ok"
    assert r.data["install_id"] == "11111111-1111-1111-1111-111111111111"
    # no temp debris left behind
    assert [p.name for p in em.manifest_path(sys_dir).parent.iterdir()
            if p.name.startswith(em.MANIFEST_FILENAME) and p.name != em.MANIFEST_FILENAME] == []


def test_read_corrupt(sys_dir):
    em.manifest_path(sys_dir).write_text("{broken", encoding="utf-8")
    r = em.read_manifest(sys_dir)
    assert r.status == "corrupt" and r.data is None


def test_read_unsupported_schema(sys_dir):
    data = _sample()
    data["schema_version"] = 99
    em.manifest_path(sys_dir).write_text(json.dumps(data), encoding="utf-8")
    assert em.read_manifest(sys_dir).status == "unsupported"


def test_read_missing_required_keys_is_corrupt(sys_dir):
    em.manifest_path(sys_dir).write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert em.read_manifest(sys_dir).status == "corrupt"


def test_write_retries_replace_on_permission_error(sys_dir):
    calls = {"n": 0}
    real = os.replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("locked by AV")
        return real(src, dst)

    em.write_manifest(sys_dir, _sample(), replace=flaky, sleep=lambda s: None)
    assert calls["n"] == 3
    assert em.read_manifest(sys_dir).status == "ok"


def test_write_surfaces_final_failure_and_keeps_old_manifest(sys_dir):
    em.write_manifest(sys_dir, _sample())

    def always_fail(src, dst):
        raise PermissionError("locked")

    new = _sample()
    new["install_id"] = "22222222-2222-2222-2222-222222222222"
    with pytest.raises(PermissionError):
        em.write_manifest(sys_dir, new, replace=always_fail, sleep=lambda s: None)
    assert em.read_manifest(sys_dir).data["install_id"].startswith("1111")


def test_new_install_id_is_unique_uuid():
    a, b = em.new_install_id(), em.new_install_id()
    assert a != b and len(a) == 36


# ---- root identity -----------------------------------------------------------

def test_roots_equal_normalizes_case_slashes_and_trailing_sep():
    assert em.roots_equal("D:\\Engram", "d:/engram/")
    assert not em.roots_equal("D:\\Engram", "D:\\Engram2")


def test_current_root_identity_uses_injected_probes():
    ident = em.current_root_identity(
        Path("P:\\Engram"),
        realpath=lambda p: "D:\\Real\\Engram",
        volume_serial=lambda p: "1234-5678",
    )
    assert ident == {"logical": "P:\\Engram", "physical": "D:\\Real\\Engram",
                     "volume_serial": "1234-5678"}


def test_subst_alias_of_same_folder_is_not_a_move(sys_dir):
    manifest = _sample("D:\\Real\\Engram")  # recorded when accessed via the real path
    drift = em.detect_root_drift(
        manifest, Path("P:\\Engram"), sys_dir,
        realpath=lambda p: "D:\\Real\\Engram",  # P: is a SUBST of D:\Real\Engram
        path_exists=lambda p: True,
    )
    assert drift.status == "consistent"


# ---- previous-root evidence ----------------------------------------------------

def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_evidence_order_pyvenv_state_sidecar_lastbase(sys_dir, tmp_path):
    _write(sys_dir / "env" / "venv" / "pyvenv.cfg",
           "home = E:\\OldRoot\\_sys\\env\\python\nversion = 3.14.8\n")
    _write(sys_dir / "data" / "state" / "install.state.json", json.dumps({"base_dir": "F:\\StateRoot"}))
    local = tmp_path / "local"
    _write(local / "SandboxRun_x_engram_open.root.txt", "G:\\SidecarRoot")
    _write(sys_dir / "data" / "last_base_dir.txt", "H:\\LastBase")
    ev = em.previous_root_evidence(sys_dir, localappdata=local)
    assert [(s, r) for s, r in ev] == [
        ("pyvenv.cfg", "E:\\OldRoot"),
        ("state", "F:\\StateRoot"),
        ("sidecar", "G:\\SidecarRoot"),
        ("last_base_dir", "H:\\LastBase"),
    ]


def test_ambiguous_sidecars_are_not_evidence(sys_dir, tmp_path):
    local = tmp_path / "local"
    _write(local / "SandboxRun_a_engram_open.root.txt", "G:/InstallA")
    _write(local / "SandboxRun_b_engram_open.root.txt", "H:/InstallB")
    assert em.previous_root_evidence(sys_dir, localappdata=local) == []


def test_live_sidecar_root_is_ignored_by_drift_detection(sys_dir, tmp_path):
    local = tmp_path / "local"
    _write(local / "SandboxRun_a_engram_open.root.txt", "G:/InstallA")
    d = em.detect_root_drift(None, Path("D:/New"), sys_dir, realpath=lambda p: str(p),
                             path_exists=lambda p: True, localappdata=local)
    assert d.status == "unknown"


def test_evidence_skips_missing_sources(sys_dir):
    _write(sys_dir / "data" / "last_base_dir.txt", "H:\\LastBase")
    assert em.previous_root_evidence(sys_dir, localappdata=None) == [("last_base_dir", "H:\\LastBase")]


def test_pyvenv_home_outside_sys_layout_is_ignored(sys_dir):
    _write(sys_dir / "env" / "venv" / "pyvenv.cfg", "home = C:\\Python314\n")
    assert em.previous_root_evidence(sys_dir, localappdata=None) == []


# ---- drift detection --------------------------------------------------------------

def test_drift_consistent_with_manifest(sys_dir):
    d = em.detect_root_drift(_sample("D:\\Engram"), Path("D:\\Engram"), sys_dir,
                             realpath=lambda p: str(p), path_exists=lambda p: True)
    assert d.status == "consistent"


def test_drift_moved_when_old_root_is_gone(sys_dir):
    d = em.detect_root_drift(_sample("D:\\Old"), Path("D:\\New"), sys_dir,
                             realpath=lambda p: str(p), path_exists=lambda p: False)
    assert d.status == "moved" and d.previous_root == "D:\\Old" and d.source == "manifest"


def test_drift_copy_suspected_when_old_root_still_exists(sys_dir):
    d = em.detect_root_drift(_sample("D:\\Old"), Path("D:\\New"), sys_dir,
                             realpath=lambda p: str(p), path_exists=lambda p: True)
    assert d.status == "copied"


def test_drift_without_manifest_uses_evidence(sys_dir):
    _write(sys_dir / "data" / "last_base_dir.txt", "D:\\Old")
    d = em.detect_root_drift(None, Path("D:\\New"), sys_dir, realpath=lambda p: str(p),
                             path_exists=lambda p: False, localappdata=None)
    assert d.status == "moved" and d.source == "last_base_dir"


def test_drift_unknown_without_any_evidence(sys_dir):
    d = em.detect_root_drift(None, Path("D:\\New"), sys_dir, realpath=lambda p: str(p),
                             path_exists=lambda p: False, localappdata=None)
    assert d.status == "unknown"


def test_drift_no_manifest_current_equals_evidence_is_consistent(sys_dir):
    _write(sys_dir / "data" / "last_base_dir.txt", "D:\\Engram")
    d = em.detect_root_drift(None, Path("D:\\Engram"), sys_dir, realpath=lambda p: str(p),
                             path_exists=lambda p: True, localappdata=None)
    assert d.status == "consistent"


# ---- adoption proposal (pure) --------------------------------------------------------

def test_propose_adoption_from_disk_evidence(sys_dir):
    _write(sys_dir / "env" / "venv" / "pyvenv.cfg",
           "home = D:\\Engram\\_sys\\env\\python\nversion = 3.14.8\nversion_info = 3.14.8.final.0\n")
    proposal = em.propose_adoption(
        sys_dir, Path("D:\\Engram"),
        python_version_probe=lambda p: "3.14.8",
        engram_version="3.5.0",
        realpath=lambda p: str(p), volume_serial=lambda p: "AAAA-BBBB",
        now="2026-10-02T00:00:00Z",
    )
    assert proposal["schema_version"] == 1
    assert proposal["root"]["logical"] == "D:\\Engram"
    assert proposal["python"]["version"] == "3.14.8"
    assert proposal["venv"]["python_version"] == "3.14.8"
    assert proposal["sys_dir_name"] == "_sys"
    assert len(proposal["install_id"]) == 36
    assert proposal["adopted_from_evidence"] is True


def test_propose_adoption_does_not_write(sys_dir):
    em.propose_adoption(sys_dir, Path("D:\\Engram"), python_version_probe=lambda p: None,
                        engram_version="3.5.0", realpath=lambda p: str(p),
                        volume_serial=lambda p: None, now="2026-10-02T00:00:00Z")
    assert not em.manifest_path(sys_dir).exists()


# ---- fresh-install commit -----------------------------------------------------------------

def test_commit_fresh_install_writes_manifest_and_last_base_dir(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    ctx = {"base_dir": base, "sys_dir": sys_dir, "paths": {"state": sys_dir / "data" / "state"},
           "command": "install"}
    res = em.commit_install(ctx, python_version_probe=lambda p: "3.14.8", engram_version="3.5.0",
                            realpath=lambda p: str(p), volume_serial=lambda p: None)
    assert res["status"] == "success"
    assert em.read_manifest(sys_dir).status == "ok"
    assert (sys_dir / "data" / "last_base_dir.txt").read_text(encoding="utf-8") == str(base)


def test_commit_install_is_a_noop_for_existing_install_without_manifest(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    state = sys_dir / "data" / "state"
    state.mkdir(parents=True)
    (state / "install.state.json").write_text("{}", encoding="utf-8")  # prior install exists
    (sys_dir / "data" / "last_base_dir.txt").write_text("D:\\Old", encoding="utf-8")
    ctx = {"base_dir": base, "sys_dir": sys_dir, "paths": {"state": state}, "command": "install"}
    res = em.commit_install(ctx, python_version_probe=lambda p: "3.14.8", engram_version="3.5.0",
                            realpath=lambda p: str(p), volume_serial=lambda p: None)
    assert res["status"] == "success" and res.get("skipped") is True
    assert not em.manifest_path(sys_dir).exists()
    # the move signal must survive an `install` re-run
    assert (sys_dir / "data" / "last_base_dir.txt").read_text(encoding="utf-8") == "D:\\Old"


def test_commit_install_does_not_overwrite_existing_manifest(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    state = sys_dir / "data" / "state"
    state.mkdir(parents=True)
    em.write_manifest(sys_dir, _sample(str(base)))
    ctx = {"base_dir": base, "sys_dir": sys_dir, "paths": {"state": state}, "command": "install"}
    res = em.commit_install(ctx, python_version_probe=lambda p: "9.9.9", engram_version="3.5.0",
                            realpath=lambda p: str(p), volume_serial=lambda p: None)
    assert res.get("skipped") is True
    assert em.read_manifest(sys_dir).data["python"]["version"] == "3.14.8"
