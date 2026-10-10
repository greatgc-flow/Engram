"""Offline contract tests; FakeProvider is deliberately test-only."""
import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest

from _sys.core.isolation import (
    Availability, Capabilities, EvidenceValidationError, ExecResult,
    ExposureWarning, Handle, IsolationProvider, ProfileValidationError,
    collect_guest_evidence, load_profile, probe_availability,
)


CONFIG = Path(__file__).resolve().parents[2] / "config"


def profile_data(name="clean-room"):
    return json.loads((CONFIG / "isolation-profiles" / f"{name}.json").read_text())


def write_profile(tmp_path, data):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("name,network", [
    ("clean-room", False), ("online-test", True), ("dev", False),
])
def test_shipped_profiles(name, network):
    profile = load_profile(CONFIG / "isolation-profiles" / f"{name}.json")
    assert profile.name == name
    assert profile.network is network
    assert not profile.clipboard and not profile.vgpu
    assert profile.input_read_only and profile.evidence_writable
    assert profile.workspace_access == "none"
    assert not profile.warnings
    with pytest.raises(FrozenInstanceError):
        profile.network = True


@pytest.mark.parametrize("name,changes", [
    ("clean-room", {"network": True}),
    ("online-test", {"network": False}),
    ("clean-room", {"workspace_access": "read-only"}),
    ("online-test", {"workspace_access": "read-write", "allow_writable_share": True}),
    ("dev", {"workspace_access": "read-write"}),
    ("dev", {"allow_writable_share": True}),
    ("dev", {"clipboard": True}),
    ("dev", {"vgpu": True}),
    ("dev", {"input_read_only": False}),
    ("dev", {"evidence_writable": False}),
    ("dev", {"network": 1}),
    ("dev", {"schema_version": True}),
    ("dev", {"schema_version": 2}),
    ("dev", {"name": "unknown"}),
    ("dev", {"workspace_access": "unknown"}),
    ("dev", {"extra": False}),
])
def test_invalid_profiles_fail_closed(tmp_path, name, changes):
    data = profile_data(name)
    data.update(changes)
    with pytest.raises(ProfileValidationError):
        load_profile(write_profile(tmp_path, data))


def test_profile_missing_malformed_and_duplicate_fields(tmp_path):
    path = tmp_path / "profile.json"
    for text in ('{', '[]', '{"name":"dev","name":"clean-room"}'):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ProfileValidationError):
            load_profile(path)
    data = profile_data()
    del data["network"]
    with pytest.raises(ProfileValidationError):
        load_profile(write_profile(tmp_path, data))
    with pytest.raises(ProfileValidationError):
        load_profile(tmp_path / "absent.json")


def test_dev_explicit_overrides_and_exposure_warning():
    path = CONFIG / "isolation-profiles" / "dev.json"
    profile = load_profile(path, overrides={"network": True, "workspace_access": "read-only"})
    assert profile.network and profile.workspace_access == "read-only"
    with pytest.raises(ProfileValidationError):
        load_profile(path, overrides={"workspace_access": "read-write"})
    with pytest.warns(ExposureWarning, match="host workspace"):
        profile = load_profile(path, overrides={
            "workspace_access": "read-write", "allow_writable_share": True,
        })
    assert profile.warnings
    with pytest.raises(ProfileValidationError):
        load_profile(path, overrides={"clipboard": False})
    with pytest.raises(ProfileValidationError):
        load_profile(CONFIG / "isolation-profiles" / "clean-room.json", overrides={"network": True})


def guest_result(handle, execution_id):
    return {
        "schema_version": 1, "handle_id": handle.id, "execution_id": execution_id,
        "complete": True, "outcome": "passed", "exit_code": 0, "log_refs": ["stdout.log"],
    }


def publish(handle, execution_id, data):
    directory = handle.evidence_root / execution_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "stdout.log").write_text("guest output\n", encoding="utf-8")
    pending = directory / "result.json.tmp"
    pending.write_text(json.dumps(data), encoding="utf-8")
    os.replace(pending, directory / "result.json")


@pytest.fixture
def handle(tmp_path):
    return Handle("handle-1", tmp_path / "evidence")


def test_canonical_atomic_guest_result(handle):
    publish(handle, "exec-1", guest_result(handle, "exec-1"))
    evidence = collect_guest_evidence(handle, "exec-1")
    assert evidence.reference == handle.evidence_root / "exec-1" / "result.json"
    assert evidence.outcome == "passed" and evidence.exit_code == 0
    assert evidence.log_refs == (handle.evidence_root / "exec-1" / "stdout.log",)
    with pytest.raises(FrozenInstanceError):
        evidence.outcome = "failed"


@pytest.mark.parametrize("changes", [
    {"execution_id": "old-exec"}, {"handle_id": "old-handle"},
    {"complete": False}, {"complete": 1}, {"schema_version": 2},
    {"exit_code": True}, {"exit_code": None}, {"exit_code": 3},
    {"outcome": "failed"}, {"outcome": "unknown"}, {"extra": 1},
    {"log_refs": "stdout.log"}, {"log_refs": [1]},
])
def test_invalid_stale_or_incomplete_evidence(handle, changes):
    data = guest_result(handle, "exec-1")
    data.update(changes)
    publish(handle, "exec-1", data)
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, "exec-1")


@pytest.mark.parametrize("reference", [
    "../outside.log", "nested/../../outside.log", "..\\outside.log",
    "/outside.log", "C:\\outside.log", "C:outside.log", "\\\\host\\share\\log",
    "stdout.log:stream", "./stdout.log", "missing.log", "",
])
def test_evidence_rejects_unsafe_log_paths(handle, reference):
    data = guest_result(handle, "exec-1")
    data["log_refs"] = [reference]
    publish(handle, "exec-1", data)
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, "exec-1")


@pytest.mark.parametrize("execution_id", ["../exec-1", "..\\exec-1", "/exec-1", "C:exec-1", ""])
def test_evidence_rejects_execution_traversal(handle, execution_id):
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, execution_id)


def test_missing_malformed_partial_and_temporary_results(handle):
    directory = handle.evidence_root / "exec-1"
    directory.mkdir(parents=True)
    (directory / "result.json.tmp").write_text(json.dumps(guest_result(handle, "exec-1")))
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, "exec-1")
    for text in ('{', '[]', '{}', '{"complete":true,"complete":false}'):
        (directory / "result.json").write_text(text, encoding="utf-8")
        with pytest.raises(EvidenceValidationError):
            collect_guest_evidence(handle, "exec-1")


def test_evidence_rejects_symlink_escape(handle, tmp_path):
    publish(handle, "exec-1", guest_result(handle, "exec-1"))
    outside = tmp_path / "outside.log"
    outside.write_text("outside")
    log = handle.evidence_root / "exec-1" / "stdout.log"
    log.unlink()
    try:
        log.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Host does not permit symlink creation: {exc}")
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, "exec-1")


@pytest.mark.parametrize("target", ["execution", "result", "log"])
def test_resolved_paths_cannot_escape_mount(handle, tmp_path, monkeypatch, target):
    """Exercise junction/symlink resolution even on hosts denying symlink creation."""
    publish(handle, "exec-1", guest_result(handle, "exec-1"))
    directory = handle.evidence_root / "exec-1"
    selected = {"execution": directory, "result": directory / "result.json",
                "log": directory / "stdout.log"}[target]
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == selected:
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(EvidenceValidationError):
        collect_guest_evidence(handle, "exec-1")


@pytest.mark.parametrize("outcome,exit_code", [
    ("failed", 7), ("timed-out", None), ("cancelled", None),
])
def test_completed_nonpassing_guest_outcomes(handle, outcome, exit_code):
    data = guest_result(handle, "exec-1")
    data.update(outcome=outcome, exit_code=exit_code)
    publish(handle, "exec-1", data)
    evidence = collect_guest_evidence(handle, "exec-1")
    assert evidence.outcome == outcome and evidence.exit_code == exit_code


class FakeProvider:
    def __init__(self, *, fail_probe=False, fail_destroy=False):
        self.fail_probe = fail_probe
        self.fail_destroy = fail_destroy
        self.destroyed = False

    def detect(self):
        def probe():
            if self.fail_probe:
                raise OSError("probe failed")
            return Availability("AVAILABLE", "test-only", Capabilities("fake", True, 1))
        return probe_availability(probe, backend="fake")

    def create(self, profile, inputs, evidence_root):
        return Handle(uuid4().hex, evidence_root)

    def exec(self, handle, argv, timeout):
        execution_id = uuid4().hex
        publish(handle, execution_id, guest_result(handle, execution_id))
        # Host completion alone is not evidence.
        return ExecResult(0, execution_id, "COMPLETED")

    def collect_evidence(self, handle, execution_id):
        return collect_guest_evidence(handle, execution_id)

    def destroy(self, handle):
        if self.fail_destroy:
            raise OSError("destroy failed")
        self.destroyed = True


def test_fake_provider_protocol_lifecycle(tmp_path):
    provider = FakeProvider()
    assert isinstance(provider, IsolationProvider)
    assert provider.detect().status == "AVAILABLE"
    profile = load_profile(CONFIG / "isolation-profiles" / "clean-room.json")
    handle = provider.create(profile, (), tmp_path / "evidence")
    result = provider.exec(handle, ["test"], 10)
    assert provider.collect_evidence(handle, result.execution_id).outcome == "passed"
    provider.destroy(handle)
    assert provider.destroyed


def test_detect_failed_probe_is_unavailable():
    availability = FakeProvider(fail_probe=True).detect()
    assert availability.status == "UNAVAILABLE"
    assert "probe failed" in availability.reason
    assert availability.capabilities.backend == "fake"
    assert availability.capabilities.concurrency == 0


def test_probe_rejects_invalid_return():
    assert probe_availability(lambda: None, backend="fake").status == "UNAVAILABLE"


def test_probe_with_unreadable_exception_is_unavailable():
    class ProbeError(Exception):
        def __str__(self):
            raise ValueError("unreadable")

    def probe():
        raise ProbeError()

    assert probe_availability(probe, backend="fake").status == "UNAVAILABLE"


def test_destroy_failure_is_not_success(tmp_path):
    provider = FakeProvider(fail_destroy=True)
    assert isinstance(provider, IsolationProvider)
    with pytest.raises(OSError, match="destroy failed"):
        provider.destroy(Handle("handle-1", tmp_path))
    assert not provider.destroyed
