"""Offline provider tests; the single live lifecycle test requires explicit opt-in."""
import base64
import json
import os
import subprocess
import threading
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from _sys.core.isolation import EvidenceValidationError, ExposureWarning, IsolationProvider, load_profile
from _sys.extensions.windows_sandbox import WindowsSandboxProvider


CONFIG = Path(__file__).resolve().parents[2] / "config" / "isolation-profiles"


class FakeRunner:
    def __init__(self, *, missing=(), failure=None, output="garbage", timeout=False):
        self.missing = missing
        self.failure = failure
        self.output = output
        self.timeout = timeout
        self.calls = []
        self.ids = []
        self.provider = None
        self.handle = None
        self.stop_fails = False
        self.stays = False
        self.publish = True
        self.raw_list = None
        self.start_timeout = False

    def __call__(self, argv, **kwargs):
        assert kwargs["timeout"] > 0 and kwargs.get("shell") is False
        self.calls.append((argv, kwargs))
        if self.failure:
            raise self.failure
        code, output = 0, ""
        if argv[0] == "wsb.exe":
            command = argv[1]
            if command in self.missing:
                code = 1
            elif "--help" in argv:
                output = "localized help is deliberately ignored"
            elif command == "list":
                output = self.raw_list if self.raw_list is not None else json.dumps({"WindowsSandboxEnvironments": [{"Id": i} for i in self.ids]})
            elif command == "start":
                self.ids.append("11111111-1111-1111-1111-111111111111")
                if self.start_timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                output = json.dumps({"Id": self.ids[-1]})
            elif command == "stop":
                code = int(self.stop_fails)
                if not self.stop_fails and not self.stays:
                    self.ids.remove(argv[3])
            elif command == "exec":
                if self.timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
                if self.publish:
                    self.write_result()
                output = self.output
        elif "Start-Process" in " ".join(argv):
            self.ids.append("11111111-1111-1111-1111-111111111111")
            if self.publish:
                self.write_result()
        return subprocess.CompletedProcess(argv, code, output, "")

    def write_result(self):
        directory = next(p for p in self.handle.evidence_root.iterdir() if p.is_dir())
        for name in ("stdout.log", "stderr.log"):
            (directory / name).write_text("guest log", encoding="utf-8")
        pending = directory / "result.json.tmp"
        pending.write_text(json.dumps({
            "schema_version": 1, "handle_id": self.handle.id,
            "execution_id": directory.name, "complete": True,
            "outcome": "passed", "exit_code": 0,
            "log_refs": ["stdout.log", "stderr.log"],
        }), encoding="utf-8")
        pending.replace(directory / "result.json")


def setup_provider(tmp_path, **kwargs):
    runner = FakeRunner(**kwargs)
    provider = WindowsSandboxProvider(runner=runner, lock_root=tmp_path / "locks",
                                      guest_root=r"C:\EngramSandbox", poll_interval=0.001,
                                      lifecycle_timeout=0.05, lock_timeout=0.03)
    runner.provider = provider
    return provider, runner


def create(provider, runner, tmp_path, name="clean-room", **overrides):
    inputs = tmp_path / "input & ' (safe)"
    inputs.mkdir(exist_ok=True)
    runner.handle = provider.create(load_profile(CONFIG / f"{name}.json", overrides=overrides),
                                    [inputs], tmp_path / "evidence")
    return runner.handle


@pytest.mark.parametrize("failure", [OSError("missing executable"), subprocess.TimeoutExpired("probe", 1), ValueError("bad JSON")])
def test_detection_never_raises(tmp_path, failure):
    provider, _ = setup_provider(tmp_path, failure=failure)
    result = provider.detect()
    assert result.status == "UNAVAILABLE" and result.reason
    assert result.capabilities.concurrency == 0


@pytest.mark.parametrize("missing", [("list",), ("stop",)])
def test_unverifiable_lifecycle_is_unavailable(tmp_path, missing):
    provider, _ = setup_provider(tmp_path, missing=missing)
    assert provider.detect().status == "UNAVAILABLE"


@pytest.mark.parametrize("raw", ["garbage", "{}", '{"WindowsSandboxEnvironments":null}', '{"WindowsSandboxEnvironments":[{"Id":"bad"}]}'])
def test_malformed_raw_detection_is_unavailable(tmp_path, raw):
    provider, runner = setup_provider(tmp_path)
    runner.raw_list = raw
    assert provider.detect().status == "UNAVAILABLE"


@pytest.mark.parametrize("name,network", [("clean-room", "Disable"), ("online-test", "Enable"), ("dev", "Disable")])
def test_profile_xml_and_cli_lifecycle(tmp_path, name, network):
    provider, runner = setup_provider(tmp_path)
    assert isinstance(provider, IsolationProvider)
    assert provider.detect().capabilities.concurrency == 1
    handle = create(provider, runner, tmp_path, name)
    start = next(argv for argv, _ in runner.calls if argv[:2] == ["wsb.exe", "start"] and "--raw" in argv)
    xml = start[start.index("--config") + 1]
    root = ET.fromstring(xml)
    assert root.findtext("Networking") == network
    assert root.findtext("ClipboardRedirection") == root.findtext("VGpu") == "Disable"
    mounts = root.findall("MappedFolders/MappedFolder")
    assert [m.findtext("ReadOnly") for m in mounts] == ["true", "false"]
    assert mounts[0].findtext("HostFolder").endswith("input & ' (safe)")
    assert "&amp;" in xml
    assert Path(mounts[1].findtext("HostFolder")) == handle.evidence_root
    result = provider.exec(handle, ["powershell.exe", "-NoProfile", "-Command", "exit 0"], 2)
    assert result.exit_code == 0 and result.status == "COMPLETED"
    assert provider.collect_evidence(handle, result.execution_id).outcome == "passed"
    command = next(a[a.index("-c") + 1] for a, _ in runner.calls if a[:2] == ["wsb.exe", "exec"] and "-c" in a)
    script = base64.b64decode(command.split()[-1]).decode("utf-16-le")
    assert "result.json.tmp" in script and "Move-Item" in script
    assert script.index("RedirectStandardOutput") < script.index("Move-Item")
    provider.destroy(handle)
    assert not runner.ids


@pytest.mark.parametrize("missing", [("exec",), ("start",)])
def test_wsb_logon_fallback(tmp_path, missing):
    provider, runner = setup_provider(tmp_path, missing=missing)
    assert provider.detect().status == "AVAILABLE"
    handle = create(provider, runner, tmp_path)
    assert not runner.ids
    result = provider.exec(handle, ["whoami.exe"], 2)
    config = ET.parse(handle.evidence_root / "sandbox.wsb")
    assert "EncodedCommand" in config.findtext("LogonCommand/Command")
    assert provider.collect_evidence(handle, result.execution_id).exit_code == 0
    provider.destroy(handle)


@pytest.mark.parametrize("output", ["", "garbage 999999", "(code: 7)", "\uacb0\uacfc (\ucf54\ub4dc: 7)"])
def test_exec_text_never_overrides_guest_result(tmp_path, output):
    provider, runner = setup_provider(tmp_path, output=output)
    handle = create(provider, runner, tmp_path)
    assert provider.exec(handle, ["whoami.exe"], 2).exit_code == 0
    provider.destroy(handle)


def test_timeout_attempts_verified_destroy(tmp_path):
    provider, runner = setup_provider(tmp_path, timeout=True)
    handle = create(provider, runner, tmp_path)
    result = provider.exec(handle, ["whoami.exe"], 0.01)
    assert result.status == "TIMED_OUT" and result.exit_code is None
    assert not runner.ids
    provider.destroy(handle)


def test_timeout_destroy_failure_is_propagated(tmp_path):
    provider, runner = setup_provider(tmp_path, timeout=True)
    handle = create(provider, runner, tmp_path)
    runner.stop_fails = True
    with pytest.raises(RuntimeError):
        provider.exec(handle, ["whoami.exe"], 0.01)
    assert runner.ids
    runner.stop_fails = False
    provider.destroy(handle)


def test_start_timeout_discovers_and_destroys_instance(tmp_path):
    provider, runner = setup_provider(tmp_path)
    runner.start_timeout = True
    with pytest.raises(subprocess.TimeoutExpired):
        create(provider, runner, tmp_path)
    assert not runner.ids
    runner.start_timeout = False
    handle = create(provider, runner, tmp_path)
    provider.destroy(handle)


def test_fallback_timeout_destroys_instance(tmp_path):
    provider, runner = setup_provider(tmp_path, missing=("exec",))
    handle = create(provider, runner, tmp_path)
    runner.publish = False
    result = provider.exec(handle, ["whoami.exe"], 0.01)
    assert result.status == "TIMED_OUT" and not runner.ids


def test_serialization_across_processes(tmp_path):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    code = """import sys
from pathlib import Path
from _sys.extensions.windows_sandbox import WindowsSandboxProvider
p = WindowsSandboxProvider(lock_root=Path(sys.argv[1]), lock_timeout=0.01)
try:
    lease = p._reserve(1)
except TimeoutError:
    sys.exit(7)
lease.close()
sys.exit(0)
"""
    import sys
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "locks")],
                            timeout=5, shell=False, capture_output=True, text=True)
    assert result.returncode == 7, result.stderr
    provider.destroy(handle)


def test_reservation_consumes_detected_capacity(tmp_path):
    provider, _ = setup_provider(tmp_path)
    provider.observed_concurrency = 2
    capacity = provider.detect().capabilities.concurrency
    assert capacity == 2
    first = provider._reserve(capacity)
    second = provider._reserve(capacity)
    try:
        with pytest.raises(TimeoutError):
            provider._reserve(capacity)
    finally:
        first.close()
        second.close()


def test_external_instance_is_never_stopped(tmp_path):
    provider, runner = setup_provider(tmp_path)
    runner.ids.append("22222222-2222-2222-2222-222222222222")
    with pytest.raises(RuntimeError, match="occupied"):
        create(provider, runner, tmp_path)
    assert not any(a[:2] == ["wsb.exe", "stop"] and "--id" in a for a, _ in runner.calls)


def test_invalid_guest_result_during_exec_triggers_cleanup(tmp_path):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    original = runner.write_result
    def publish_stale():
        original()
        path = next(handle.evidence_root.glob("*/result.json"))
        data = json.loads(path.read_text())
        data["handle_id"] = "stale"
        path.write_text(json.dumps(data), encoding="utf-8")
    runner.write_result = publish_stale
    with pytest.raises(EvidenceValidationError, match="stale"):
        provider.exec(handle, ["whoami.exe"], 2)
    assert not runner.ids


@pytest.mark.parametrize("failure", ["stop_fails", "stays"])
def test_destroy_failure_retains_reservation(tmp_path, failure):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    setattr(runner, failure, True)
    with pytest.raises(RuntimeError):
        provider.destroy(handle)
    other, other_runner = setup_provider(tmp_path)
    with pytest.raises(TimeoutError):
        create(other, other_runner, tmp_path)
    setattr(runner, failure, False)
    provider.destroy(handle)


def test_serialization_across_provider_objects_and_threads(tmp_path):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    other, other_runner = setup_provider(tmp_path)
    errors = []
    def compete():
        try:
            create(other, other_runner, tmp_path)
        except TimeoutError as exc:
            errors.append(exc)
    thread = threading.Thread(target=compete)
    thread.start()
    thread.join(3)
    assert not thread.is_alive() and len(errors) == 1
    provider.destroy(handle)
    second = create(other, other_runner, tmp_path)
    assert second.id != handle.id
    other.destroy(second)


@pytest.mark.parametrize("text", ["{", "{}", '{"complete":true,"complete":false}'])
def test_malformed_result_uses_existing_validator(tmp_path, text):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    result = provider.exec(handle, ["whoami.exe"], 2)
    path = handle.evidence_root / result.execution_id / "result.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(EvidenceValidationError):
        provider.collect_evidence(handle, result.execution_id)
    provider.destroy(handle)


def test_stale_result_and_missing_canonical_result(tmp_path):
    provider, runner = setup_provider(tmp_path)
    handle = create(provider, runner, tmp_path)
    result = provider.exec(handle, ["whoami.exe"], 2)
    path = handle.evidence_root / result.execution_id / "result.json"
    data = json.loads(path.read_text())
    data["execution_id"] = "stale"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EvidenceValidationError):
        provider.collect_evidence(handle, result.execution_id)
    runner.publish = False
    with pytest.raises(EvidenceValidationError):
        provider.exec(handle, ["whoami.exe"], 0.01)
    provider.destroy(handle)


def test_dev_share_warns_and_mount_overlap_rejected(tmp_path):
    provider, runner = setup_provider(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider.workspace = workspace
    with pytest.warns(ExposureWarning):
        handle = create(provider, runner, tmp_path, "dev", workspace_access="read-write", allow_writable_share=True)
    xml = next(a[a.index("--config") + 1] for a, _ in runner.calls if "--config" in a)
    assert ET.fromstring(xml).findall("MappedFolders/MappedFolder")[-1].findtext("ReadOnly") == "false"
    provider.destroy(handle)
    with pytest.raises(ValueError, match="overlap"):
        provider.create(load_profile(CONFIG / "clean-room.json"), [tmp_path], tmp_path / "evidence")


@pytest.mark.parametrize("path", ["bad\npath", "bad\x00path", "bad?path", "bad|path", "bad\"path"])
def test_unsafe_mapped_paths_rejected(tmp_path, path):
    provider, _ = setup_provider(tmp_path)
    with pytest.raises(ValueError):
        provider.create(load_profile(CONFIG / "clean-room.json"), [tmp_path / path], tmp_path / "evidence")


@pytest.mark.skipif(os.name != "nt" or os.environ.get("ENGRAM_WINDOWS_SANDBOX_LIVE") != "1" or bool(os.environ.get("CI")),
                    reason="Requires Windows, ENGRAM_WINDOWS_SANDBOX_LIVE=1 and a non-CI host")
def test_live_clean_room_lifecycle(tmp_path):
    provider = WindowsSandboxProvider()
    availability = provider.detect()
    assert availability.status == "AVAILABLE", availability.reason
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    handle = provider.create(load_profile(CONFIG / "clean-room.json"), [inputs], tmp_path / "evidence")
    try:
        result = provider.exec(handle, ["powershell.exe", "-NoProfile", "-Command", "Write-Output 'clean-room'; exit 0"], 120)
        evidence = provider.collect_evidence(handle, result.execution_id)
        assert evidence.outcome == "passed" and evidence.exit_code == 0
        assert "clean-room" in evidence.log_refs[0].read_text(encoding="utf-8-sig")
    finally:
        provider.destroy(handle)
