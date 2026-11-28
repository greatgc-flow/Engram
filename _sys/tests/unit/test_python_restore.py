"""Exact offline restore prepares only wholly missing managed build directories."""
import hashlib

import pytest

from core import env_manifest, env_ops, python_install, python_provider, python_registry
from test_python_registry import candidate


@pytest.fixture
def damaged(tmp_path):
    root = tmp_path / "_sys"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                        "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    archive = b"controlled fixture bytes"
    artifact = python_install.Artifact("20261124", "3.14.10", 788332448,
                                       hashlib.sha256(archive).hexdigest(), len(archive))
    document = candidate()
    document["builds"]["build-a"].update(artifact.identity())
    assert python_registry.publish(root, 0, document)["phase"] == "COMMITTED"
    path = root / "data/setup-files/python-archives" / python_provider.asset_name(artifact)
    return root, path, archive


def test_missing_and_changed_cache_fail_before_materialization(damaged):
    from core import python_restore

    root, path, archive = damaged
    for contents, pattern in [(None, "Missing offline archive"), (archive + b"!", "digest mismatch")]:
        if contents:
            path.parent.mkdir(parents=True)
            path.write_bytes(contents)
        with pytest.raises(ValueError, match=pattern):
            python_restore.plan(root)
        assert not (root / "env").exists()
        assert env_ops.active_journal(root) is None


def test_restore_uses_existing_build_id_and_never_replaces_partial_directory(damaged, monkeypatch):
    from core import python_restore

    root, path, archive = damaged
    path.parent.mkdir(parents=True)
    path.write_bytes(archive)
    before = python_registry.registry_path(root).read_bytes()
    def unpack(input_archive, artifact, destination):
        payload = destination / "python"
        payload.mkdir()
        (payload / "python.exe").write_bytes(b"controlled interpreter fixture")
    monkeypatch.setattr(python_install, "extract_verified", unpack)
    monkeypatch.setattr(python_install, "_probe", lambda *args: None)
    scope = python_restore.plan(root)
    assert len(scope) == 1 and scope[0]["params"]["build_id"] == "build-a"
    steps = python_restore.step(root, **scope[0]["params"])
    assert env_ops.execute(root, "repair", [steps])["phase"] == "COMMITTED"
    assert python_registry.registry_path(root).read_bytes() == before
    assert not python_restore.plan(root)
    exe = root / "env/python-versions/3.14/build-a/python.exe"
    exe.unlink()
    with pytest.raises(ValueError, match="Incomplete build directory"):
        python_restore.plan(root)
    assert exe.parent.is_dir()


@pytest.mark.parametrize("mode", ["resume", "rollback"])
def test_resume_and_rollback_after_atomic_restore_rename(damaged, monkeypatch, mode):
    from pathlib import Path
    from core import python_restore

    root, cache, archive = damaged
    cache.parent.mkdir(parents=True)
    cache.write_bytes(archive)
    def unpack(_, artifact, destination):
        payload = destination / "python"
        payload.mkdir()
        (payload / "python.exe").touch()
    monkeypatch.setattr(python_install, "extract_verified", unpack)
    monkeypatch.setattr(python_install, "_probe", lambda *args: None)
    spec = python_restore.plan(root)[0]
    restore = python_restore.step(root, **spec["params"])
    original = Path.rename
    def crash_after_publish(path, destination):
        result = original(path, destination)
        if Path(destination).name == "build-a":
            raise env_ops.SimulatedCrash()
        return result
    with monkeypatch.context() as m:
        m.setattr(Path, "rename", crash_after_publish)
        with pytest.raises(env_ops.SimulatedCrash):
            env_ops.execute(root, "repair", [restore], initial_data={"spec": [spec]})
    cache.unlink()
    result = getattr(env_ops, mode)(root, lambda active: [python_restore.step(root, **spec["params"])])
    exe = root / "env/python-versions/3.14/build-a/python.exe"
    assert result["phase"] == ("COMMITTED" if mode == "resume" else "ROLLED_BACK")
    assert exe.is_file() is (mode == "resume")
