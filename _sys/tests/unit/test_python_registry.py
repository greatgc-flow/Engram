"""Read-only legacy inventory and compare-and-swap recovery (Rev 0.6 T58/T64)."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from core import env_manifest, env_ops, provisioner


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() if p.is_file() else None
            for p in root.rglob("*")}


def candidate():
    build = {"implementation": "cpython", "series": "3.14", "version": "3.14.10",
             "abi": "cp314", "arch": "win_amd64", "provider": "pbs", "flavor": "full",
             "sha256": "a" * 64, "artifact_ref": "fixture-archive",
             "executable_rel": "env/python-versions/3.14/build-a/python.exe",
             "state": "ACTIVE", "owner": "engram"}
    return {"schema_version": "1.0", "revision": 1, "installation_id": "fixture-install",
            "default_binding": "legacy-default",
            "series": {"3.14": {"channel": "stable", "active_build": "build-a",
                                "policy": "compatible_patch"}},
            "builds": {"build-a": build},
            "bindings": {"legacy-default": {"kind": "legacy", "executable_rel": "env/venv/Scripts/python.exe"},
                         "demo": {"kind": "app", "build_id": "build-a", "env_id": "env-a",
                                  "constraint_ref": "fixture-constraint"}},
            "environments": {"env-a": {"owner": "demo", "generation": 1, "build_id": "build-a",
                                       "root_rel": "AI/apps/demo/envs/env-a", "lock_ref": "fixture-lock"}},
            "external_refs": [], "rollback_refs": [], "vendor_exceptions": []}


@pytest.fixture
def installed(tmp_path):
    root = tmp_path / "_sys"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                       "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    return root


@pytest.mark.parametrize("base,venv,status", [(False, False, "ABSENT"), (False, True, "PARTIAL"),
                                             (True, False, "PARTIAL"), (True, True, "PRESENT")])
def test_legacy_inventory_is_offline_and_pure(tmp_path, base, venv, status, monkeypatch):
    from core import python_registry as reg
    root = tmp_path / "한글 root" / "renamed-system"
    for present, fn in [(base, provisioner.portable_python_exe), (venv, provisioner.venv_python_exe)]:
        if present:
            executable = fn(root)
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_bytes(b"fixture")
    before = snapshot(tmp_path)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("unexpected child"))
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: pytest.fail("unexpected network"))
    result = reg.inventory(root)
    assert result["revision"] == 0
    assert result["legacy"] == {"status": status, "base_rel": "env/python/python.exe",
                                "executable_rel": "env/venv/Scripts/python.exe"}
    assert result["registry"] is None
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("keys,value", [
    (("revision",), True), (("installation_id",), "foreign"), (("schema_version",), "2.0"),
    (("default_binding",), "demo"), (("bindings", "legacy-default", "executable_rel"), "host/python.exe"),
    (("builds", "build-a", "executable_rel"), "../python.exe"),
    (("builds", "build-a", "executable_rel"), "C:/host/python.exe"),
    (("builds", "build-a", "sha256"), "short"), (("builds", "build-a", "arch"), "win32"),
    (("builds", "build-a", "abi"), "cp313"), (("series", "3.14", "active_build"), "absent"),
    (("bindings", "demo", "env_id"), "absent"), (("environments", "env-a", "build_id"), "missing"),
    (("environments", "env-a", "root_rel"), "AI/apps/other/envs/env-a"),
    (("environments", "env-a", "owner"), ".."), (("environments", "env-a", "generation"), True),
    (("external_refs",), ["unverified"]), (("builds", "BUILD-A"), {}),
])
def test_invalid_proposal_leaves_state_untouched(installed, keys, value):
    from core import python_registry as reg
    doc = candidate()
    node = doc
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value
    before = snapshot(installed)
    with pytest.raises(reg.RegistryError):
        reg.publish(installed, 0, doc)
    assert snapshot(installed) == before


def test_commit_conflict_and_immutable_identity(installed):
    from core import python_registry as reg
    doc = candidate()
    assert reg.publish(installed, 0, doc)["phase"] == "COMMITTED"
    before = snapshot(installed)
    with pytest.raises(reg.RegistryError):
        reg.publish(installed, 0, doc)
    change = copy.deepcopy(doc)
    change["revision"] = 2
    change["builds"]["build-a"]["sha256"] = "b" * 64
    with pytest.raises(reg.RegistryError):
        reg.publish(installed, 1, change)
    assert reg.inventory(installed)["registry"] == doc
    assert snapshot(installed) == before


@pytest.mark.parametrize("old_revision,mode,torn", [(0, "resume", False), (0, "rollback", False),
                                                   (1, "resume", True), (1, "rollback", True)])
def test_recover_after_replace_before_ack(installed, monkeypatch, old_revision, mode, torn):
    from core import python_registry as reg
    doc = candidate()
    path = installed / "data/state/python-registry.json"
    if old_revision:
        reg.publish(installed, 0, doc)
    before = path.read_bytes() if path.exists() else None
    doc["revision"] += old_revision
    write = env_manifest._atomic_write_text
    def interrupt(path, text):
        write(path, text[:25] if torn else text)
        raise env_ops.SimulatedCrash()
    with monkeypatch.context() as m:
        m.setattr(env_manifest, "_atomic_write_text", interrupt)
        with pytest.raises(env_ops.SimulatedCrash):
            reg.publish(installed, old_revision, doc)
    with env_ops.journal_path(installed).open("ab") as f:
        f.write(b'{"incomplete"')
    if os.name == "nt":
        from core import repair
        result = repair.repair_main({"sys_dir": installed, "base_dir": installed.parent,
                                     "args": ["--" + mode, "--json"]})
        assert result["exit_code"] == 0, result
    else:
        result = getattr(env_ops, mode)(installed, lambda active: reg.recovery_steps(installed, active, mode))
        assert result["phase"] == ("COMMITTED" if mode == "resume" else "ROLLED_BACK")
    assert env_ops.active_journal(installed) is None
    if mode == "resume":
        assert reg.inventory(installed)["registry"] == doc
    else:
        assert (path.read_bytes() if path.exists() else None) == before


def test_corrupt_registry_never_adopted_on_read_or_publish(installed):
    from core import python_registry as reg
    path = installed / "data/state/python-registry.json"
    path.write_bytes(b'{"schema')
    before = snapshot(installed)
    for action in [lambda: reg.inventory(installed), lambda: reg.publish(installed, 0, candidate())]:
        with pytest.raises(reg.RegistryError):
            action()
    assert snapshot(installed) == before


def test_cross_process_stale_proposal(installed):
    from core import python_registry as reg
    # Both independent planners observed revision zero. Only one may publish.
    script = """
import json, sys
from pathlib import Path
from core import python_registry as reg
try:
    result = reg.publish(Path(sys.argv[1]), 0, json.load(sys.stdin))
except reg.RegistryError:
    sys.exit(11)
sys.exit(result["exit_code"])
"""
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(installed)], stdin=subprocess.PIPE,
                                  env={**os.environ, "PYTHONPATH": str(Path(provisioner.__file__).parents[1])})
                 for _ in range(2)]
    for proc in processes:
        proc.stdin.write(json.dumps(candidate()).encode("utf-8"))
        proc.stdin.close()
    assert sorted(proc.wait(30) for proc in processes) == [0, 11]
    assert reg.inventory(installed)["registry"] == candidate()


def test_public_doctor_only_reports_existing_registry(installed, capsys):
    from core import doctor, python_registry as reg
    ctx = {"sys_dir": installed, "base_dir": installed.parent, "args": ["--json"], "env": {}}
    def inspect():
        doctor.run(ctx)
        return [c for c in json.loads(capsys.readouterr().out)["checks"] if c["name"] == "python_registry"]
    before = snapshot(installed)
    assert inspect() == []
    assert snapshot(installed) == before
    reg.publish(installed, 0, candidate())
    before = snapshot(installed)
    assert inspect()[0]["ok"]
    assert snapshot(installed) == before
    (installed / "data/state/python-registry.json").write_bytes(b"{")
    assert inspect()[0]["level"] == "error"


def test_managed_path_reparse_denied(installed, tmp_path):
    from core import python_registry as reg
    other = tmp_path / "outside"
    other.mkdir()
    alias = installed / "env"
    if os.name == "nt":
        # Directory junctions work with a standard account on NTFS.
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(other)],
                       check=True, capture_output=True)
    else:
        alias.symlink_to(other, target_is_directory=True)
    with pytest.raises(reg.RegistryError):
        reg.publish(installed, 0, candidate())
    assert list(other.iterdir()) == []


def test_directory_case_collision(installed):
    from core import python_registry as reg
    (installed / "ai").mkdir()
    with pytest.raises(reg.RegistryError):
        reg.publish(installed, 0, candidate())
    assert not env_ops.journal_path(installed).exists()


def test_foreign_change_during_interrupted_operation_preserved(installed, monkeypatch):
    from core import python_registry as reg
    def crash(path, text):
        raise env_ops.SimulatedCrash()
    with monkeypatch.context() as m:
        m.setattr(env_manifest, "_atomic_write_text", crash)
        with pytest.raises(env_ops.SimulatedCrash):
            reg.publish(installed, 0, candidate())
    path = installed / "data/state/python-registry.json"
    path.write_bytes(b'{"unrelated":true}')
    result = env_ops.resume(installed, lambda active: reg.recovery_steps(installed, active, "resume"))
    assert result["phase"] == "ROLLBACK_FAILED"
    assert env_ops.active_journal(installed)
    assert path.read_bytes() == b'{"unrelated":true}'


def test_duplicate_disk_keys_are_rejected(installed):
    from core import python_registry as reg
    raw = json.dumps(candidate()).replace('"revision": 1', '"revision": 2, "revision": 1')
    (installed / "data/state/python-registry.json").write_text(raw, encoding="utf-8")
    with pytest.raises(reg.RegistryError, match="duplicate"):
        reg.inventory(installed)


def test_interrupted_undo_can_repeat_from_old_image_prefix(installed, monkeypatch):
    from core import python_registry as reg
    doc = candidate()
    reg.publish(installed, 0, doc)
    path = reg.registry_path(installed)
    # Older writers can use other valid UTF-8 whitespace. Rollback restores exact bytes.
    previous = (json.dumps(doc, indent=4) + "\r\n").encode("utf-8")
    path.write_bytes(previous)
    doc["revision"] = 2
    write = env_manifest._atomic_write_text
    def stop_after(path, text):
        write(path, text)
        raise env_ops.SimulatedCrash()
    with monkeypatch.context() as m:
        m.setattr(env_manifest, "_atomic_write_text", stop_after)
        with pytest.raises(env_ops.SimulatedCrash):
            reg.publish(installed, 1, doc)
    def torn_undo(path, text):
        write(path, text[:100])
        raise env_ops.SimulatedCrash()
    def rebuild(active):
        return reg.recovery_steps(installed, active, "rollback")
    with monkeypatch.context() as m:
        m.setattr(env_manifest, "_atomic_write_text", torn_undo)
        with pytest.raises(env_ops.SimulatedCrash):
            env_ops.rollback(installed, rebuild)
    assert env_ops.rollback(installed, rebuild)["phase"] == "ROLLED_BACK"
    assert path.read_bytes() == previous


def test_lost_intent_before_first_effect_can_roll_back(installed, monkeypatch):
    from core import python_registry as reg
    append_fn = env_ops._append_record_fn
    def interrupt_before_data(*args):
        append = append_fn(*args)
        def write(event, **fields):
            if event == "DATA":
                raise env_ops.SimulatedCrash()
            return append(event, **fields)
        return write
    with monkeypatch.context() as m:
        m.setattr(env_ops, "_append_record_fn", interrupt_before_data)
        with pytest.raises(env_ops.SimulatedCrash):
            reg.publish(installed, 0, candidate())
    assert not reg.registry_path(installed).exists()
    active = env_ops.active_journal(installed)
    assert active["phase"] == "PLANNED"
    with pytest.raises(env_ops.JournalError):
        env_ops.resume(installed, lambda a: reg.recovery_steps(installed, a, "resume"))
    assert env_ops.rollback(installed, lambda a: reg.recovery_steps(installed, a, "rollback"))["phase"] == "ROLLED_BACK"
    assert not reg.registry_path(installed).exists()


@pytest.mark.parametrize("prior", [0, 1], ids=["create", "update"])
@pytest.mark.parametrize("mode", ["resume", "rollback"])
@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("boundary", ["PLANNED", "PATHS", "DATA", "POSTS", "STEPS_RUNNING",
                                     "started", "done", "COMMITTED"])
def test_every_publication_journal_boundary(installed, monkeypatch, prior, mode, side, boundary):
    from core import python_registry as reg
    doc = candidate()
    if prior:
        assert reg.publish(installed, 0, doc)["phase"] == "COMMITTED"
    doc["revision"] = prior + 1
    factory = env_ops._append_record_fn

    def interrupt(*args):
        append = factory(*args)
        def record(event, **fields):
            label = fields.get("state") or fields.get("name") or event
            if label == boundary and side == "before":
                raise env_ops.SimulatedCrash()
            append(event, **fields)
            if label == boundary and side == "after":
                raise env_ops.SimulatedCrash()
        return record

    with monkeypatch.context() as m:
        m.setattr(env_ops, "_append_record_fn", interrupt)
        with pytest.raises(env_ops.SimulatedCrash):
            reg.publish(installed, prior, doc)

    active = env_ops.active_journal(installed)
    if active:
        if not active["data"] and mode == "resume":
            with pytest.raises(env_ops.JournalError):
                env_ops.resume(installed, lambda a: reg.recovery_steps(installed, a, "resume"))
        recovery = mode if active["data"] else "rollback"
        rebuild = lambda a: reg.recovery_steps(installed, a, recovery)
        result = getattr(env_ops, recovery)(installed, rebuild)
        committed = recovery == "resume"
        assert result["phase"] == ("COMMITTED" if committed else "ROLLED_BACK")
    else:
        # Before the first record or after durable commit, there is nothing to recover.
        committed = boundary == "COMMITTED" and side == "after"
    assert not env_ops.active_journal(installed)
    assert reg.inventory(installed)["revision"] == prior + int(committed)
