"""Offline guidance, dispatch, and provider diagnosis contracts."""
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from _sys.core.isolation import Availability, Capabilities, probe_availability
from _sys.core import isolation_check
from _sys.core import dispatcher
from _sys.extensions.windows_sandbox import WindowsSandboxProvider
from _sys.extensions.windows_sandbox.provider import SandboxLifecycleError
from _sys.extensions.wsl2 import WSL2Provider
from _sys.extensions.wsl2.provider import WSLLifecycleError


SYS = Path(__file__).resolve().parents[2]
CODES = {"OK", "WSB_CLI_MISSING", "WSB_FEATURE_DISABLED", "WSB_UNSUPPORTED_EDITION",
         "WSL_NOT_INSTALLED", "WSL_PROBE_FAILED", "PROBE_ERROR", "UNKNOWN"}


def test_guidance_schema_and_code_coverage():
    data = json.loads((SYS / "config/isolation-guidance.json").read_text())
    schema = json.loads((SYS / "config/isolation-guidance.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(data, schema)
    assert set(data["codes"]) == CODES
    for path in (SYS / "core/isolation.py", SYS / "extensions/windows_sandbox/provider.py",
                 SYS / "extensions/wsl2/provider.py"):
        emitted_codes = set(re.findall(r'"((?:WSB_|WSL_|PROBE_)[A-Z_]+|OK)"', path.read_text()))
        assert emitted_codes <= data["codes"].keys()
    for mutate in (lambda d: d["codes"].pop("OK"),
                   lambda d: d["codes"]["OK"].update(admin_needed="yes"),
                   lambda d: d["codes"]["OK"].update(steps=[]),
                   lambda d: d.update(extra=True)):
        invalid = json.loads(json.dumps(data))
        mutate(invalid)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)


def fake_providers(monkeypatch, sandbox, wsl, code=None):
    for name, backend, status in (("WindowsSandboxProvider", "windows-sandbox", sandbox),
                                 ("WSL2Provider", "wsl2", wsl)):
        availability = Availability(status, "fake reason " + backend,
                                    Capabilities(backend, True, int(status == "AVAILABLE")),
                                    code or ("OK" if status == "AVAILABLE" else "PROBE_ERROR"))
        monkeypatch.setattr(isolation_check, name, lambda a=availability: SimpleNamespace(detect=lambda: a))


@pytest.mark.parametrize("sandbox", ["AVAILABLE", "UNAVAILABLE"])
@pytest.mark.parametrize("wsl", ["AVAILABLE", "UNAVAILABLE"])
@pytest.mark.parametrize("json_output", [False, True])
def test_all_availability_combinations(monkeypatch, capsys, tmp_path, sandbox, wsl, json_output):
    fake_providers(monkeypatch, sandbox, wsl)
    # Keep the dispatch real while replacing only probes and context paths.
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *a: {
        "sys_dir": SYS, "base_dir": tmp_path, "args": ["check"] + (["--json"] if json_output else [])})
    # The dispatcher imports the canonical core namespace.
    monkeypatch.setattr(dispatcher.importlib, "import_module", lambda name: isolation_check)
    assert dispatcher.main(["dispatcher.py", "isolation", "check"]) == 0
    output = capsys.readouterr().out
    if json_output:
        report = json.loads(output)
        assert report["status"] == "success"
        assert [p["status"] for p in report["providers"]] == [sandbox, wsl]
        for provider in report["providers"]:
            assert set(provider) == {"provider", "status", "reason", "capabilities", "code", "guidance"}
            assert provider["code"] in CODES
            assert provider["guidance"]["steps"]
    else:
        assert f"windows-sandbox: {sandbox}" in output
        assert f"wsl2: {wsl}" in output
        assert output.count("Reason: fake reason") == 2
        assert output.count("Without it:") == 2
        assert "  - " in output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("code", [None, "FUTURE_CODE"])
def test_unknown_code_gets_generic_guidance(monkeypatch, capsys, code):
    availability = Availability("UNAVAILABLE", "unknown", Capabilities("fake", False, 0), code)
    for name in ("WindowsSandboxProvider", "WSL2Provider"):
        monkeypatch.setattr(isolation_check, name, lambda: SimpleNamespace(detect=lambda: availability))
    result = isolation_check.run({"sys_dir": SYS, "args": ["check", "--json"]})
    assert result["status"] == "success"
    assert result["providers"][0]["code"] == code
    assert "Optional provider unavailable" in capsys.readouterr().out


def test_unexpected_probe_exception_is_normal(monkeypatch):
    def fail():
        raise ValueError("transient failure")
    monkeypatch.setattr(isolation_check, "WindowsSandboxProvider", lambda: SimpleNamespace(detect=fail))
    monkeypatch.setattr(isolation_check, "WSL2Provider", lambda: SimpleNamespace(detect=fail))
    result = isolation_check.run({"sys_dir": SYS, "args": ["check"]})
    assert result["status"] == "success"
    assert all(p["code"] == "PROBE_ERROR" for p in result["providers"])


@pytest.mark.parametrize("args", [[], ["wrong"], ["check", "--bad"], ["check", "extra"]])
def test_usage_errors(args):
    assert isolation_check.run({"args": args})["exit_code"] == 2


@pytest.mark.parametrize("json_output", [False, True])
def test_internal_error_exit_one(tmp_path, capsys, monkeypatch, json_output):
    args = ["check"] + (["--json"] if json_output else [])
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *a: {"sys_dir": tmp_path, "args": args})
    monkeypatch.setattr(dispatcher.importlib, "import_module", lambda name: isolation_check)
    assert dispatcher.main(["dispatcher.py", "isolation", *args]) == 1
    output = capsys.readouterr().out
    if json_output:
        assert json.loads(output)["exit_code"] == 1
    assert "internal error" in output and "Traceback" not in output


@pytest.mark.parametrize("diagnostic,expected", [(0, "WSB_CLI_MISSING"), (20, "WSB_UNSUPPORTED_EDITION"),
                                               (21, "WSB_FEATURE_DISABLED"), (22, "WSB_CLI_MISSING")])
def test_sandbox_missing_cli_and_structured_diagnosis(diagnostic, expected, tmp_path):
    def runner(argv, **kwargs):
        if argv[0] == "wsb.exe":
            raise FileNotFoundError("localized message")
        return subprocess.CompletedProcess(argv, diagnostic, "localized text", "")
    availability = WindowsSandboxProvider(runner=runner, lock_root=tmp_path).detect()
    assert availability.code == expected
    assert availability.status == "UNAVAILABLE"


def test_sandbox_transient_diagnostic_failure(tmp_path):
    def runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)
    assert WindowsSandboxProvider(runner=runner, lock_root=tmp_path).detect().code == "PROBE_ERROR"


@pytest.mark.parametrize("exit_code,expected", [(0x8007019e, "WSL_NOT_INSTALLED"),
                                             (0x8007019e - 2**32, "WSL_NOT_INSTALLED"),
                                             (1, "WSL_PROBE_FAILED"), (0, "OK")])
@pytest.mark.parametrize("command", ["--version", "--status"])
def test_wsl_exit_code_mapping(exit_code, expected, command, tmp_path):
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, exit_code if argv[1] == command else 0,
                                           b"translated text is ignored", b"")
    result = WSL2Provider(runner=runner, lock_root=tmp_path).detect()
    assert result.code == expected
    assert "interop" in result.reason


@pytest.mark.parametrize("failure,expected", [(FileNotFoundError("missing"), "WSL_NOT_INSTALLED"),
                                           (OSError("access denied"), "WSL_PROBE_FAILED"),
                                           (subprocess.TimeoutExpired("wsl", 1), "WSL_PROBE_FAILED"),
                                           (subprocess.CalledProcessError(0x8007019e, "wsl"), "WSL_NOT_INSTALLED"),
                                           (ValueError("bad runner"), "PROBE_ERROR")])
def test_wsl_exception_codes(failure, expected, tmp_path):
    def runner(*a, **kw):
        raise failure
    assert WSL2Provider(runner=runner, lock_root=tmp_path).detect().code == expected


@pytest.mark.parametrize("provider_type", [WindowsSandboxProvider, WSL2Provider])
@pytest.mark.parametrize("failure", [FileNotFoundError(2, "missing"),
                                   subprocess.TimeoutExpired("tool", 1),
                                   subprocess.CalledProcessError(1, "tool")])
def test_external_launch_hint_preserves_exception_type(provider_type, failure, tmp_path):
    def runner(*a, **kw):
        raise failure
    provider = provider_type(runner=runner, lock_root=tmp_path)
    with pytest.raises(type(failure), match="run `engram isolation check`"):
        provider._checked(["tool", "command"], 1)


@pytest.mark.parametrize("backend", ["sandbox", "wsl"])
@pytest.mark.parametrize("action", ["create", "exec", "destroy"])
def test_lifecycle_external_error_hint(backend, action, tmp_path):
    from _sys.tests.unit import test_windows_sandbox_provider as sandbox_tests
    from _sys.tests.unit import test_wsl2_provider as wsl_tests

    if backend == "sandbox":
        provider, runner = sandbox_tests.setup_provider(tmp_path)
        make_handle = lambda: sandbox_tests.create(provider, runner, tmp_path)
    else:
        provider, runner, rootfs = wsl_tests.setup_provider(tmp_path)
        make_handle = lambda: wsl_tests.create(provider, runner, rootfs, tmp_path)
    assert provider.detect().status == "AVAILABLE"
    handle = None if action == "create" else make_handle()
    original = provider.runner

    def fail(argv, **kwargs):
        # Fail one external operation while allowing cleanup to finish.
        if (action == "create" and argv[1] in ("start", "--import") or
                action == "exec" and (argv[1] == "exec" or argv[1] == "-d") or
                action == "destroy" and argv[1] in ("stop", "--terminate")):
            raise FileNotFoundError(2, "tool disappeared")
        return original(argv, **kwargs)

    provider.runner = fail
    try:
        with pytest.raises((FileNotFoundError, RuntimeError), match="run `engram isolation check`") as error:
            if action == "create":
                make_handle()
            elif action == "exec":
                provider.exec(handle, ["echo", "hello"], 1)
            else:
                provider.destroy(handle)
        if action == "create":
            assert type(error.value) is (WSLLifecycleError if backend == "wsl" else SandboxLifecycleError)
        else:
            assert type(error.value) is FileNotFoundError
    finally:
        provider.runner = original
        for job in provider._jobs.values():
            if action == "create":
                job.lease.close()
            else:
                provider.destroy(job.handle)


def test_availability_backward_compatibility_and_probe_error():
    old = Availability("AVAILABLE", "ready", Capabilities("old", False, 1))
    assert old.code is None
    assert probe_availability(lambda: None, backend="bad").code == "PROBE_ERROR"


def test_isolation_documentation_links():
    assert "docs/isolation_guide.md" in (SYS.parent / "README.md").read_text()
    assert "(isolation_guide.md)" in (SYS.parent / "docs/cli_reference.md").read_text()
    assert (SYS.parent / "docs/isolation_guide.md").is_file()
