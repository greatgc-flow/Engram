"""T71 runtime recovery metadata through Engram's existing backup verbs."""
import hashlib
import io
import json
import os
import sys
import zipfile

import pytest

from checks import backup_personal_data
from core import env_manifest, env_ops, python_registry
from test_python_registry import candidate, snapshot


@pytest.fixture
def runtime(tmp_path):
    base = tmp_path / "portable 한글"
    root = base / "_sys"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                      "root": {"physical": str(base), "logical": str(base)}})
    document = candidate()
    lock = json.dumps({"schema": 1, "build_sha256": "a" * 64, "wheels": []}).encode()
    ref = "sha256-" + hashlib.sha256(lock).hexdigest()
    document["environments"]["env-a"]["lock_ref"] = ref
    assert python_registry.publish(root, 0, document)["phase"] == "COMMITTED"
    document["revision"] += 1
    assert python_registry.publish(root, 1, document)["phase"] == "COMMITTED"
    destination = root / "data/setup-files/python-locks" / (ref + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(lock)
    personal = base / ".engram/claude"
    personal.mkdir(parents=True)
    (personal / "CLAUDE.md").write_text("private synthetic sentinel", encoding="utf-8")
    return {"sys_dir": root, "base_dir": base}, destination, tmp_path / "runtime.zip"


def _backup(ctx, bundle):
    backup_personal_data.run_backup({**ctx, "args": ["--only", "python-runtime", "--out", str(bundle)]})


def _restore(ctx, bundle, *flags):
    backup_personal_data.run_restore({**ctx, "args": [str(bundle), "--only", "python-runtime", *flags]})


def test_backup_and_restore_exact_metadata(runtime, monkeypatch):
    ctx, lock, bundle = runtime
    def forbidden(*args, **kwargs):
        pytest.fail("Scoped runtime backup entered the personal-data pipeline.")
    monkeypatch.setattr(backup_personal_data, "check_running_processes", forbidden)
    registry = python_registry.registry_path(ctx["sys_dir"])
    before = registry.read_bytes(), lock.read_bytes()
    _backup(ctx, bundle)
    with zipfile.ZipFile(bundle) as archive:
        assert len(archive.namelist()) == 3
        assert not any(b"private synthetic sentinel" in archive.read(name) for name in archive.namelist())
    registry.rename(registry.with_suffix(".held"))
    lock.rename(lock.with_suffix(".held"))
    preview = snapshot(ctx["base_dir"])
    _restore(ctx, bundle, "--apply", "--dry-run")
    assert snapshot(ctx["base_dir"]) == preview
    _restore(ctx, bundle, "--apply")
    assert (registry.read_bytes(), lock.read_bytes()) == before
    assert python_registry.inventory(ctx["sys_dir"])["revision"] == 2
    _restore(ctx, bundle, "--apply")
    assert (registry.read_bytes(), lock.read_bytes()) == before


def test_backup_refuses_missing_lock_and_preserves_output(runtime):
    ctx, lock, bundle = runtime
    lock.rename(lock.with_suffix(".held"))
    with pytest.raises(OSError, match="Missing offline lock"):
        _backup(ctx, bundle)
    assert not bundle.exists()
    bundle.write_bytes(b"existing")
    with pytest.raises(OSError, match="already exists"):
        _backup(ctx, bundle)
    assert bundle.read_bytes() == b"existing"


@pytest.mark.parametrize("conflict", ["registry", "lock", "foreign", "extra_entry"])
def test_restore_refuses_before_any_destination_writes(runtime, conflict):
    ctx, lock, bundle = runtime
    _backup(ctx, bundle)
    root = ctx["sys_dir"]
    path = python_registry.registry_path(root)
    if conflict == "registry":
        doc = python_registry.inventory(root)["registry"]
        doc["revision"] = 3
        python_registry.publish(root, 2, doc)
        lock.rename(lock.with_suffix(".held"))
    elif conflict == "lock":
        path.rename(path.with_suffix(".held"))
        lock.write_bytes(b"conflicting file")
    elif conflict == "foreign":
        different = root.parent.parent / "other"
        env_manifest.write_manifest(different, {"schema_version": 1, "install_id": "other",
                                                 "root": {"physical": str(different), "logical": str(different)}})
        ctx = {"sys_dir": different, "base_dir": different.parent}
    else:
        with zipfile.ZipFile(bundle, "a") as archive:
            archive.writestr("../escape", b"sentinel")
    before = snapshot(ctx["base_dir"])
    with pytest.raises(OSError):
        _restore(ctx, bundle, "--apply")
    assert snapshot(ctx["base_dir"]) == before


@pytest.mark.parametrize("mode", ["resume", "rollback"])
def test_interrupted_metadata_restore_has_recovery(runtime, monkeypatch, mode):
    from core import python_runtime_backup

    ctx, lock, bundle = runtime
    root = ctx["sys_dir"]
    registry = python_registry.registry_path(root)
    exact = registry.read_bytes()
    _backup(ctx, bundle)
    registry.rename(registry.with_suffix(".held"))
    lock.rename(lock.with_suffix(".held"))
    write = env_manifest._atomic_write_text
    def interrupt(path, text, **kwargs):
        write(path, text, **kwargs)
        if path == registry:
            raise env_ops.SimulatedCrash()
    with monkeypatch.context() as patch:
        patch.setattr(env_manifest, "_atomic_write_text", interrupt)
        with pytest.raises(env_ops.SimulatedCrash):
            _restore(ctx, bundle, "--apply")
    bundle.rename(bundle.with_suffix(".held"))
    if os.name == "nt":
        from core import repair
        result = repair.repair_main({**ctx, "args": ["--" + mode, "--json"]})
        assert result["exit_code"] == 0, result
    else:
        result = getattr(env_ops, mode)(
            root, lambda active: python_runtime_backup.recovery_steps(root, active, mode))
        assert result["phase"] == ("COMMITTED" if mode == "resume" else "ROLLED_BACK")
    assert env_ops.active_journal(root) is None
    assert (registry.read_bytes() if registry.exists() else None) == (exact if mode == "resume" else None)
    assert lock.is_file()


def test_unicode_archive_path_when_output_is_redirected_to_cp1252(runtime, monkeypatch):
    ctx, _, bundle = runtime
    bundle = bundle.with_name("runtime 한글.zip")
    output = io.BytesIO()
    with io.TextIOWrapper(output, encoding="cp1252") as console:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", console)
            _backup(ctx, bundle)
        console.flush()
        assert b"Saved Python runtime metadata revision 2." in output.getvalue()
    assert bundle.is_file()
