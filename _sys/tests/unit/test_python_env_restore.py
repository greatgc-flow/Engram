"""Offline managed environment recovery, without editing the registry or other environments."""
import hashlib
import json
from pathlib import Path

import pytest

from core import env_manifest, env_ops, python_registry
from test_python_registry import candidate


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / "_sys"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                        "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    document = candidate()
    wheel = b"synthetic wheel data"
    name = "test_package-1.0-py3-none-any.whl"
    lock = json.dumps({"schema": 1, "build_sha256": document["builds"]["build-a"]["sha256"],
                       "wheels": [{"filename": name, "sha256": hashlib.sha256(wheel).hexdigest()}]}).encode()
    ref = "sha256-" + hashlib.sha256(lock).hexdigest()
    env = document["environments"]["env-a"]
    env["lock_ref"] = ref
    env["root_rel"] = "env/python-envs/demo/env-a"
    assert python_registry.publish(root, 0, document)["phase"] == "COMMITTED"
    base = root / document["builds"]["build-a"]["executable_rel"]
    base.parent.mkdir(parents=True)
    base.touch()
    lock_path = root / "data/setup-files/python-locks" / (ref + ".json")
    lock_path.parent.mkdir(parents=True)
    lock_path.write_bytes(lock)
    wheel_path = root / "data/setup-files/python-wheels" / name
    return root, root / env["root_rel"], wheel_path, wheel, lock_path


def test_missing_and_tampered_wheel_fail_without_creating_venv(fixture):
    from core import python_env_restore as recovery

    root, destination, wheel, payload, _ = fixture
    with pytest.raises(ValueError, match="Missing offline wheel"):
        recovery.plan(root)
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(payload + b"changed")
    with pytest.raises(ValueError, match="Wheel digest mismatch"):
        recovery.plan(root)
    assert not destination.exists()
    assert env_ops.active_journal(root) is None


def test_lock_bytes_are_bound_to_recorded_digest(fixture):
    from core import python_env_restore as recovery

    root, destination, _, _, lock = fixture
    lock.write_bytes(lock.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Lock digest mismatch"):
        recovery.plan(root)
    assert not destination.exists()


@pytest.mark.parametrize("fail", [False, True])
def test_rebuild_uses_final_path_and_preserves_registry(fixture, monkeypatch, fail):
    from core import python_env_restore as recovery

    root, destination, wheel, payload, _ = fixture
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(payload)
    before = python_registry.registry_path(root).read_bytes()
    spec, = recovery.plan(root)
    def rebuild(base, target, work, lock):
        assert target == destination
        assert base.name == "python.exe"
        assert Path(work, wheel.name).read_bytes() == payload
        (target / "Scripts").mkdir()
        (target / "Scripts/python.exe").touch()
        if fail:
            raise ValueError("fixture pip check failed")
    monkeypatch.setattr(recovery, "_rebuild", rebuild)
    step = recovery.step(root, **spec["params"])
    result = env_ops.execute(root, "repair", [step])
    assert result["phase"] == ("ROLLED_BACK" if fail else "COMMITTED")
    assert destination.exists() is not fail
    assert python_registry.registry_path(root).read_bytes() == before


@pytest.mark.parametrize("failure", [False, True])
def test_relocate_keeps_stale_environment_bytes_even_when_rebuild_fails(fixture, monkeypatch, failure):
    from core import python_env_restore as recovery

    root, destination, wheel, payload, _ = fixture
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(payload)
    (destination / "Scripts").mkdir(parents=True)
    (destination / "Scripts/python.exe").write_bytes(b"source venv")
    config = b"home = a directory that was moved\n"
    (destination / "pyvenv.cfg").write_bytes(config)
    lock_ref = python_registry.inventory(root)["registry"]["environments"]["env-a"]["lock_ref"]
    marker = {"op_id": "fixture-operation", "env_id": "env-a", "lock_ref": lock_ref, "state": "complete"}
    (destination / recovery._MARKER).write_text(json.dumps(marker))
    with pytest.raises(ValueError, match="stale base path"):
        recovery.plan(root)
    spec, = recovery.plan(root, relocate=True)

    def rebuild(base, target, work, lock):
        (target / "Scripts").mkdir()
        (target / "Scripts/python.exe").write_bytes(b"destination venv")
        if failure:
            raise ValueError("fixture rebuilding failed")

    monkeypatch.setattr(recovery, "_rebuild", rebuild)
    result = env_ops.execute(root, "relocate", [recovery.step(root, **spec["params"])])
    if failure:
        assert result["phase"] == "ROLLED_BACK"
        assert (destination / "pyvenv.cfg").read_bytes() == config
        assert (destination / "Scripts/python.exe").read_bytes() == b"source venv"
    else:
        assert result["phase"] == "COMMITTED"
        assert (destination / "Scripts/python.exe").read_bytes() == b"destination venv"
        preserved, = destination.parent.glob(".env-a.previous-*")
        assert (preserved / "pyvenv.cfg").read_bytes() == config
        assert (preserved / "Scripts/python.exe").read_bytes() == b"source venv"
