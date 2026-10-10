"""Offline WSL lifecycle tests and one explicitly opted-in live test."""
import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from _sys.core.isolation import EvidenceValidationError, Handle, IsolationProvider, load_profile
from _sys.extensions.wsl2 import WSL2Provider


CONFIG = Path(__file__).resolve().parents[2] / "config" / "isolation-profiles"


class FakeRunner:
    def __init__(self, encoding="utf-16-le"):
        self.encoding = encoding
        self.calls = []
        self.inputs = []
        self.names = {"UserLinux"}
        self.failure = None
        self.stays = False
        self.timeout = False
        self.publish = True
        self.handle = None
        self.unregistered = []
        self.garbage_list = False
        self.import_timeout = False
        self.translation = "/actual mount/evidence ' path"
        self.fail_command = None

    def __call__(self, argv, **kwargs):
        assert kwargs["shell"] is False and kwargs["timeout"] > 0
        assert kwargs["capture_output"] and not kwargs.get("text", False)
        self.calls.append(argv)
        self.inputs.append(kwargs.get("input"))
        if self.failure:
            raise self.failure
        output, code = "", 0
        if argv[1] in ("--version", "--status"):
            output = "arbitrary localized text is ignored"
        elif argv[1:3] == ["-l", "-q"]:
            if self.garbage_list:
                return subprocess.CompletedProcess(argv, 0, b"\xff", b"")
            output = "\r\n".join(sorted(self.names))
        elif argv[1] == "--import":
            assert argv[2] not in self.names
            with tarfile.open(argv[4]) as archive:
                config = archive.extractfile("etc/wsl.conf").read().decode()
                assert "enabled=true" in config and "appendWindowsPath=false" in config
            self.names.add(argv[2])
            if self.import_timeout:
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        elif argv[1] == "--unregister":
            self.unregistered.append(argv[2])
            assert argv[2].startswith("engram-iso-")
            if not self.stays:
                self.names.remove(argv[2])
        elif "wslpath" in argv:
            output = self.translation
        elif argv[1] == "-d" and b"result.json.tmp" in (kwargs.get("input") or b""):
            # Parse the quoted directory assigned by the guest wrapper.
            script = kwargs["input"].decode("utf-8")
            assert argv == ["wsl.exe", "-d", argv[2], "--", "sh"]
            assert b"\r" not in kwargs["input"]
            assert "mv --" in script and script.index("result.json.tmp") < script.index("mv --")
            if self.publish:
                directory = next(p for p in self.handle.evidence_root.iterdir() if p.is_dir())
                for name in ("stdout.log", "stderr.log"):
                    (directory / name).write_text("guest log", encoding="utf-8")
                pending = directory / "result.json.tmp"
                pending.write_text(json.dumps({"schema_version": 1, "handle_id": self.handle.id,
                    "execution_id": directory.name, "complete": True, "outcome": "passed",
                    "exit_code": 0, "log_refs": ["stdout.log", "stderr.log"]}), encoding="utf-8")
                pending.replace(directory / "result.json")
            if self.timeout:
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            output = "garbage execution output is not evidence"
        if argv[1] == self.fail_command:
            code = 1
        return subprocess.CompletedProcess(argv, code, output.encode(self.encoding), b"")


def setup_provider(tmp_path, encoding="utf-16-le", concurrency=1):
    runner = FakeRunner(encoding)
    provider = WSL2Provider(runner=runner, lock_root=tmp_path / "locks",
                            observed_concurrency=concurrency)
    rootfs = tmp_path / "rootfs & ' (test).tar.gz"
    with tarfile.open(rootfs, "w:gz") as archive:
        data = b"supplied rootfs"
        member = tarfile.TarInfo("etc/issue")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    return provider, runner, rootfs


def create(provider, runner, rootfs, tmp_path):
    runner.handle = provider.create(load_profile(CONFIG / "clean-room.json"), [rootfs], tmp_path / "evidence")
    return runner.handle


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-8", "utf-16"])
def test_detection_and_lifecycle(tmp_path, encoding, monkeypatch):
    provider, runner, rootfs = setup_provider(tmp_path, encoding)
    assert isinstance(provider, IsolationProvider)
    available = provider.detect()
    assert available.status == "AVAILABLE"
    assert available.capabilities.capture and available.capabilities.concurrency == 1
    assert "not security-equivalent" in available.reason and "network" in available.reason
    handle = create(provider, runner, rootfs, tmp_path)
    import_call = next(c for c in runner.calls if c[1] == "--import")
    assert import_call[2].startswith("engram-iso-") and import_call[-2:] == ["--version", "2"]
    collected = []
    original = provider.collect_evidence
    def collect(handle, execution):
        assert not runner.unregistered
        collected.append(execution)
        return original(handle, execution)
    monkeypatch.setattr(provider, "collect_evidence", collect)
    argv = ["sh", "-c", "printf '%s' \"a & b ' c\""]
    result = provider.exec(handle, argv, 2)
    script = next(data.decode("utf-8") for data in runner.inputs if data and b"result.json.tmp" in data)
    assert shlex.join(argv) in script and "/mnt/c" not in script
    assert any("wslpath" in c and handle.evidence_root.as_posix() in c for c in runner.calls)
    assert result.status == "COMPLETED" and collected == [result.execution_id]
    provider.destroy(handle)
    assert runner.names == {"UserLinux"}
    assert original(handle, result.execution_id).reference.is_file()
    provider.destroy(handle)
    assert len(runner.unregistered) == 1


@pytest.mark.parametrize("output", [b"", b"\xff", "localized text".encode("utf-16-le"), b"garbage\x00"])
def test_detection_uses_only_version_and_status_exit_codes(tmp_path, output):
    provider, runner, _ = setup_provider(tmp_path)
    def probe(argv, **kwargs):
        result = runner(argv, **kwargs)
        result.stdout = output
        return result
    provider.runner = probe
    assert provider.detect().status == "AVAILABLE"
    assert runner.calls == [["wsl.exe", "--version"], ["wsl.exe", "--status"]]


@pytest.mark.parametrize("failure", [FileNotFoundError("wsl"), subprocess.TimeoutExpired("probe", 1), RuntimeError("bad")])
def test_probe_never_raises(tmp_path, failure):
    provider, runner, _ = setup_provider(tmp_path)
    runner.failure = failure
    availability = provider.detect()
    assert availability.status == "UNAVAILABLE" and availability.reason


@pytest.mark.parametrize("command", ["--version", "--status"])
def test_probe_exit_codes(tmp_path, command):
    provider, runner, _ = setup_provider(tmp_path)
    def fail(argv, **kwargs):
        result = runner(argv, **kwargs)
        if argv[1] == command:
            result.returncode = 1
        return result
    provider.runner = fail
    availability = provider.detect()
    assert availability.status == "UNAVAILABLE"
    assert command in availability.reason and "process exit 1" in availability.reason
    expected = [["wsl.exe", "--version"]]
    if command == "--status":
        expected.append(["wsl.exe", "--status"])
    assert runner.calls == expected


def test_unique_parallel_names_and_user_protection(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path, concurrency=2)
    first = create(provider, runner, rootfs, tmp_path)
    second = create(provider, runner, rootfs, tmp_path)
    names = [c[2] for c in runner.calls if c[1] == "--import"]
    assert len(set(names)) == 2
    with pytest.raises(ValueError):
        provider.destroy(Handle("UserLinux", first.evidence_root))
    provider.destroy(first)
    provider.destroy(second)
    assert runner.names == {"UserLinux"}


def test_generated_name_collision_never_touches_existing_distro(tmp_path, monkeypatch):
    from _sys.extensions.wsl2 import provider as module
    from uuid import UUID
    fixed = UUID("11111111-1111-1111-1111-111111111111")
    monkeypatch.setattr(module, "uuid4", lambda: fixed)
    provider, runner, rootfs = setup_provider(tmp_path)
    existing = "engram-iso-" + fixed.hex
    runner.names.add(existing)
    with pytest.raises(RuntimeError):
        create(provider, runner, rootfs, tmp_path)
    assert existing in runner.names and not runner.unregistered
    assert not any(c[1] == "--import" for c in runner.calls)


def test_serialized_default(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    other = WSL2Provider(runner=runner, lock_root=tmp_path / "locks")
    with pytest.raises(TimeoutError):
        other.create(load_profile(CONFIG / "clean-room.json"), [rootfs], tmp_path / "other")
    provider.destroy(handle)


@pytest.mark.parametrize("garbage", [False, True])
def test_destroy_postcondition_failure_and_retry(tmp_path, garbage):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    runner.stays = True
    runner.garbage_list = garbage
    with pytest.raises(RuntimeError):
        provider.destroy(handle)
    runner.stays = runner.garbage_list = False
    provider.destroy(handle)


@pytest.mark.parametrize("publish", [False, True])
def test_timeout_attempts_destroy_preserves_host_evidence(tmp_path, publish):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    runner.timeout, runner.publish = True, publish
    result = provider.exec(handle, ["sleep", "60"], 0.1)
    assert result.status == "TIMED_OUT" and runner.unregistered
    if publish:
        assert provider.collect_evidence(handle, result.execution_id).reference.is_file()


def test_missing_evidence_is_not_host_success(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    runner.publish = False
    with pytest.raises(EvidenceValidationError):
        provider.exec(handle, ["true"], 1)
    assert runner.unregistered


def test_uncertain_import_never_unregisters_unowned_name(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    runner.import_timeout = True
    with pytest.raises(RuntimeError) as caught:
        create(provider, runner, rootfs, tmp_path)
    assert not runner.unregistered
    assert caught.value.handle.id


@pytest.mark.parametrize("output", [b"2\x00\x00", b"2", "2\x00", "Linux".encode("utf-16-le")])
def test_defensive_output_decoding(output):
    assert WSL2Provider._decode(output) in ("2", "Linux")


@pytest.mark.parametrize("translation", ["garbage", "", "/path\nextra"])
def test_bad_translation_cleans_up_private_distro(tmp_path, translation):
    provider, runner, rootfs = setup_provider(tmp_path)
    original = rootfs.read_bytes()
    runner.translation = translation
    with pytest.raises(ValueError):
        create(provider, runner, rootfs, tmp_path)
    assert runner.names == {"UserLinux"} and runner.unregistered
    assert rootfs.read_bytes() == original


def test_timeout_cleanup_failure_never_reports_success(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    runner.timeout, runner.stays = True, True
    with pytest.raises(RuntimeError):
        provider.exec(handle, ["sleep", "60"], 0.1)
    assert runner.unregistered
    runner.stays = False
    provider.destroy(handle)


def test_unregister_exit_failure_and_retry(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    runner.stays, runner.fail_command = True, "--unregister"
    with pytest.raises(RuntimeError):
        provider.destroy(handle)
    runner.stays, runner.fail_command = False, None
    provider.destroy(handle)


def test_overlapping_paths_rejected_without_import(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    with pytest.raises(ValueError):
        provider.create(load_profile(CONFIG / "clean-room.json"), [rootfs], tmp_path)
    assert not runner.calls


def test_readonly_input_bind_uses_translation_and_quoting(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    input_dir = tmp_path / "input space \ud55c\uae00"
    input_dir.mkdir()
    handle = provider.create(load_profile(CONFIG / "clean-room.json"), [rootfs, input_dir], tmp_path / "evidence")
    script = next(data.decode("utf-8") for data in runner.inputs if data and b"mount --bind" in data)
    assert shlex.quote(runner.translation) in script
    assert "mount -o remount,bind,ro /engram/input-0" in script
    assert any("wslpath" in c and input_dir.as_posix() in c for c in runner.calls)
    provider.destroy(handle)


def test_wslpath_normalizes_windows_separators_and_accepts_spaces_and_letters(tmp_path):
    provider, runner, _ = setup_provider(tmp_path)
    path = PureWindowsPath("D:/PkgDev/a b/\ud55c\uae00/x_1.2-3")
    assert provider._guest_path(SimpleNamespace(name="engram-iso-test"), path) == runner.translation
    assert runner.calls == [["wsl.exe", "-d", "engram-iso-test", "--", "wslpath",
                             "-a", "-u", "D:/PkgDev/a b/\ud55c\uae00/x_1.2-3"]]


@pytest.mark.parametrize("character", list("'\"$&();|`<>*?[]{}!#%+=,@~^") + ["\n", "\r", "\t", "\x00", "\u2603"])
def test_unsafe_guest_host_path_rejected_before_any_wsl_call(tmp_path, character):
    provider, runner, rootfs = setup_provider(tmp_path)
    with pytest.raises(ValueError) as caught:
        provider.create(load_profile(CONFIG / "clean-room.json"), [rootfs],
                        tmp_path / ("evidence" + character))
    assert repr(character) in str(caught.value)
    assert "wsl.exe passes arguments through a shell" in str(caught.value)
    assert not runner.calls
    with pytest.raises(ValueError):
        provider._guest_path(SimpleNamespace(name="engram-iso-test"), Path("bad" + character))
    assert not runner.calls


@pytest.mark.parametrize("destination", ["input", "workspace"])
def test_unsafe_mount_path_rejected_before_any_wsl_call(tmp_path, destination):
    from dataclasses import replace
    provider, runner, rootfs = setup_provider(tmp_path)
    unsafe = tmp_path / "unsafe$HOME"
    unsafe.mkdir()
    profile = load_profile(CONFIG / "clean-room.json")
    inputs = [rootfs]
    if destination == "input":
        inputs.append(unsafe)
    else:
        provider.workspace = unsafe
        profile = replace(profile, name="dev", workspace_access="read-only")
    with pytest.raises(ValueError, match="wsl.exe passes arguments through a shell"):
        provider.create(profile, inputs, tmp_path / "evidence")
    assert not runner.calls


def test_direct_import_paths_are_not_subject_to_guest_shell_allowlist(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    provider.lock_root = tmp_path / "import & ' (test) $HOME"
    handle = create(provider, runner, rootfs, tmp_path)
    call = next(c for c in runner.calls if c[1] == "--import")
    assert all(str(provider.lock_root) in p for p in call[3:5])
    provider.destroy(handle)


def test_wrong_execution_identity_is_rejected(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    result = provider.exec(handle, ["true"], 1)
    with pytest.raises(EvidenceValidationError):
        provider.collect_evidence(handle, "unknown")
    path = handle.evidence_root / result.execution_id / "result.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["handle_id"] = "other"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(EvidenceValidationError):
        provider.collect_evidence(handle, result.execution_id)
    with pytest.raises(EvidenceValidationError):
        provider.destroy(handle)
    assert runner.names == {"UserLinux"}


@pytest.mark.skipif(os.environ.get("ENGRAM_WSL2_LIVE") != "1" or bool(os.environ.get("CI")),
                    reason="Opt-in only; never run in CI")
def test_live_lifecycle(tmp_path):
    rootfs = Path(os.environ["ENGRAM_WSL2_ROOTFS"])
    provider = WSL2Provider(lock_root=tmp_path / "locks", lifecycle_timeout=120)
    assert provider.detect().status == "AVAILABLE"
    handle = provider.create(load_profile(CONFIG / "clean-room.json"), [rootfs], tmp_path / "evidence")
    name = provider._job(handle).name
    try:
        result = provider.exec(handle, ["sh", "-c", "printf 'live guest evidence\\n'"], 30)
        evidence = provider.collect_evidence(handle, result.execution_id)
        assert evidence.outcome == "passed" and evidence.exit_code == 0
        assert "live guest evidence" in evidence.log_refs[0].read_text(encoding="utf-8")
    finally:
        provider.destroy(handle)
    assert provider.collect_evidence(handle, result.execution_id).reference.is_file()
    assert name.casefold() not in provider._names()


def test_guest_scripts_use_utf8_lf_stdin_and_preserve_shell_characters(tmp_path):
    provider, runner, rootfs = setup_provider(tmp_path)
    handle = create(provider, runner, rootfs, tmp_path)
    argv = ["printf", "%s", "quotes ' \" $HOME & (parentheses) \ud55c\uae00"]
    provider.exec(handle, argv, 2)
    scripts = [(call, data) for call, data in zip(runner.calls, runner.inputs) if data is not None]
    assert len(scripts) == 2  # Evidence mount check and execution wrapper.
    for call, data in scripts:
        assert call == ["wsl.exe", "-d", provider._job(handle).name, "--", "sh"]
        assert isinstance(data, bytes) and b"\r" not in data
    assert shlex.join(argv) in scripts[-1][1].decode("utf-8")
    provider._shell(provider._job(handle), "printf 'first'\r\nprintf '$HOME & ()'\r", 2)
    assert runner.inputs[-1] == b"printf 'first'\nprintf '$HOME & ()'\n"
    provider.destroy(handle)


def test_runner_without_stdin_keyword_remains_supported_for_probes(tmp_path):
    def runner(argv, *, timeout, shell, capture_output, check):
        return subprocess.CompletedProcess(argv, 0, b"", b"")
    assert WSL2Provider(runner=runner, lock_root=tmp_path).detect().status == "AVAILABLE"
