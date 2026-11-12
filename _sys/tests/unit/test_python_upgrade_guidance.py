"""Dependency guidance is advisory and never authorizes a Python swap."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import python_manager, repair, updater


EXPLANATION = (
    "The new Python is not broken; the currently installed package versions "
    "could not be carried over."
)
COMMANDS = [
    "engram update -o packages -y",
    "engram update -o python --latest --refresh --check",
    "engram update -o python --latest -y",
    "engram doctor",
]
CASES = [
    ("ERROR: No matching distribution found for pywinpty==3.0.2",
     "no_wheel_for_target", "blocked"),
    ("ERROR: Could not find a version that satisfies the requirement psutil==7.0",
     "no_wheel_for_target", "blocked"),
    ("ERROR: Package 'psutil' requires a different Python: 3.15.2 not in '<3.15'",
     "requires_different_python", "blocked"),
    ("ERROR: Cannot install a==1 and b==2 because these package versions "
     "have conflicting dependencies.\nERROR: ResolutionImpossible",
     "dependency_conflict", "blocked"),
    ("WARNING: Retrying after connection broken by ProxyError",
     "network_or_index", "unverifiable"),
    ("ERROR: Could not fetch URL https://example.invalid/simple: 403 Client Error",
     "network_or_index", "unverifiable"),
    ("ERROR: ResolutionTooDeep: dependency tree is too deep",
     "resolver_failure", "unverifiable"),
    ("WARNING: Retrying after connection broken by ProxyError\n"
     "ERROR: No matching distribution found for psutil==7.0",
     "unknown", "unverifiable"),
    ("ERROR: Package 'a' requires a different Python: 3.15 not in '<3.15'\n"
     "ERROR: No matching distribution found for a==1",
     "unknown", "blocked"),
    ("ERROR: ResolutionTooDeep\nERROR: No matching distribution found for a==1",
     "unknown", "blocked"),
    ("ERROR: Ignored the following versions that require a different python version: "
     "1.0 Requires-Python <3.15\n"
     "ERROR: Could not find a version that satisfies the requirement a==1.0 (from versions: none)\n"
     "ERROR: No matching distribution found for a==1.0", "unknown", "blocked"),
    ("ERROR: Packages require a different Python. 3.15.2 not in:\n"
     "'<3.15' (required by a 1.0)\n'<3.14' (required by b 2.0)",
     "requires_different_python", "unverifiable"),
    ("ERROR: Packages require a different Python. 3.15.2 not in:\n"
     "'<3.15' (required by a 1.0)\n'<3.14' (required by b 2.0)\n"
     "ERROR: No matching distribution found for a==1.0", "unknown", "blocked"),
    ("ERROR: Exception:\nTraceback (most recent call last):\n"
     '  File "pip/_vendor/urllib3/response.py", line 438, in _error_catcher\n'
     "pip._vendor.urllib3.exceptions.ReadTimeoutError: "
     "HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.",
     "unknown", "unverifiable"),
    ("Collecting network-tools\nDownloading resolver_failure.whl", "unknown", "unverifiable"),
    ("", "unknown", "unverifiable"),
    ("ERROR: ResolutionImpossible", "unknown", "blocked"),
]


def preflight(output, returncode=1):
    return repair._python_minor_preflight(
        "3.15.2", "https://www.python.org/example.zip",
        managed_python=Path("managed/python.exe"), specs=("pywinpty==3.0.2",),
        fetch=lambda *a, **k: None,
        run=lambda *a, **k: SimpleNamespace(returncode=returncode, stdout="", stderr=output),
    )


@pytest.mark.parametrize("output,kind,state", CASES)
def test_python_blocker_classification_never_changes_readiness(output, kind, state):
    assert python_manager.dependency_failure_kind(output) == kind
    result = preflight(output)
    assert result.state == state
    assert result.kind == kind


def test_python_success_ignores_failure_diagnostics():
    result = preflight(CASES[0][0], returncode=0)
    assert result.state == "ok" and result.kind == "unknown"


@pytest.mark.parametrize("output,kind,state", CASES)
def test_python_kind_handles_indented_crlf_and_color(output, kind, state):
    formatted = "\r\n".join("  \x1b[31m" + line + "\x1b[0m" for line in output.splitlines())
    assert python_manager.dependency_failure_kind(formatted) == kind


def test_python_kind_does_not_mistake_a_package_name_for_network_failure():
    assert python_manager.dependency_failure_kind(
        "ERROR: No matching distribution found for ProxyError==1") == "no_wheel_for_target"


@pytest.fixture
def blocked_python(tmp_path, monkeypatch):
    monkeypatch.setattr(repair.layout_migration, "supported_layout", lambda *a, **k: True)
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"journal": None})
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.10")
    monkeypatch.setattr(repair, "_python_pin", lambda *a: {
        "version": "3.15.2", "url": "https://www.python.org/example.zip", "sha256": None,
    })
    monkeypatch.setattr(repair.venv_manager, "build_snapshot", lambda *a, **k: {"packages": []})
    discovery = {"status": "ok", "latest_version": "3.15.2", "latest_minor_cycle": "3.15",
                 "latest_patch_by_cycle": {"3.14": "3.14.10"}}
    monkeypatch.setattr(repair.env_ops, "execute", lambda *a, **k: pytest.fail("must not apply"))
    return {"sys_dir": tmp_path / "_sys", "base_dir": tmp_path, "command": "update",
            "seams": {"resolve_python": lambda *a, **k: discovery,
                      "fetch": lambda *a, **k: None,
                      "resolver_run": lambda *a, **k: SimpleNamespace(
                          returncode=1, stdout="", stderr=CASES[0][0])}}


@pytest.mark.parametrize("flags,code", [(["--check"], 1), ([], 11), (["-y"], 11)])
def test_python_blocked_cli_and_plan_recovery_order(blocked_python, capsys, flags, code):
    result = updater.run({**blocked_python, "args": ["-o", "python", "--latest", *flags]})
    assert result["exit_code"] == code
    output = capsys.readouterr().out
    assert "[Warning] Python 3.15 blocked:" in output
    assert "pywinpty==3.0.2" in output
    assert EXPLANATION in " ".join(output.split())
    assert [output.index(command) for command in COMMANDS] == sorted(
        output.index(command) for command in COMMANDS)
    assert output.index("Only if that check passes:") < output.index(COMMANDS[2])
    assert "--force" not in output + result["detail"]
    assert all(line.isascii() and len(line) <= 80 for line in output.splitlines())


@pytest.mark.parametrize("output,kind,state", CASES)
def test_python_check_json_guidance_shape(blocked_python, capsys, output, kind, state):
    blocked_python["seams"]["resolver_run"] = lambda *a, **k: SimpleNamespace(
        returncode=1, stdout="", stderr=output)
    result = updater.run({**blocked_python, "args": [
        "-o", "python", "--latest", "--check", "--json"]})
    payload = json.loads(capsys.readouterr().out)
    assert payload["exit_code"] == result["exit_code"] == 1
    readiness = payload["readiness"]
    assert readiness["state"] == state and readiness["kind"] == kind
    assert readiness["blocker"]
    if state == "blocked":
        assert readiness["advice"] == EXPLANATION
        assert [item["command"] for item in readiness["next_commands"]] == COMMANDS
        assert [item["when"] for item in readiness["next_commands"]] == [
            "now", "after_package_update", "only_if_check_passes", "only_if_check_passes"]
    else:
        assert readiness["advice"] == "" and readiness["next_commands"] == []


@pytest.mark.parametrize("json_output", [False, True])
def test_python_explicit_target_recovery_preserves_target(blocked_python, capsys, json_output):
    commands = [command.replace("--latest", "--to 3.15.1") for command in COMMANDS]
    result = updater.run({**blocked_python, "args": [
        "-o", "python", "--to", "3.15.1", "--check", *(["--json"] if json_output else [])]})
    output = capsys.readouterr().out
    assert result["exit_code"] == 1
    assert result["readiness"]["state"] == "blocked"
    assert [item["command"] for item in result["readiness"]["next_commands"]] == commands
    if json_output:
        assert json.loads(output)["readiness"] == result["readiness"]
    else:
        assert [output.index(command) for command in commands] == sorted(
            output.index(command) for command in commands)
        assert output.index("Only if that check passes:") < output.index(commands[2])
    assert "--latest" not in output and "--force" not in output


def test_python_json_blocker_is_sanitized_and_bounded(blocked_python, capsys):
    output = ("\x1b[31mERROR: No matching distribution found for private-lib @ "
              "https://user:password@example.invalid/lib.whl?token=secret#fragment "
              "\x1b]0;hidden\x07" + "x" * 400)
    blocked_python["seams"]["resolver_run"] = lambda *a, **k: SimpleNamespace(
        returncode=1, stdout="", stderr=output)
    updater.run({**blocked_python, "args": ["-o", "python", "--latest", "--check", "--json"]})
    payload = json.loads(capsys.readouterr().out)
    encoded = json.dumps(payload)
    for secret in ("user", "password", "secret", "fragment", "hidden", "\\u001b", "\\u0007"):
        assert secret not in encoded
    assert len(payload["readiness"]["blocker"]) <= 240
    assert payload["readiness"]["blocker"].isascii()


def test_python_status_report_uses_the_same_recovery(blocked_python):
    status = repair.python_update_status(blocked_python["sys_dir"], seams=blocked_python["seams"])
    for key in ("lines", "report_lines"):
        output = "\n".join(status[key])
        assert EXPLANATION in " ".join(output.split())
        assert [output.index(command) for command in COMMANDS] == sorted(
            output.index(command) for command in COMMANDS)
        assert output.index("Only if that check passes:") < output.index(COMMANDS[2])
        assert "--force" not in output
    assert status["commands"] == []  # No unconditional apply advice in the footer.


def test_python_block_without_diagnostic_says_so(blocked_python, monkeypatch, capsys):
    monkeypatch.setattr(repair, "_minor_readiness", lambda *a, **k: repair.PythonReadiness(
        "3.15.2", "https://www.python.org/example.zip", (), "blocked",
        "no compatible dependency set"))
    result = updater.run({**blocked_python, "args": ["-o", "python", "--latest", "--check"]})
    assert "pip supplied no specific dependency diagnostic" in capsys.readouterr().out
    assert result["readiness"]["kind"] == "unknown"
    assert "no specific dependency diagnostic" in result["readiness"]["blocker"]


def test_python_archive_block_does_not_claim_dependency_failure(blocked_python, monkeypatch, capsys):
    import urllib.error

    def missing(*a, **k):
        raise urllib.error.HTTPError("embed", 404, "missing", {}, None)

    blocked_python["seams"]["fetch"] = missing
    result = updater.run({**blocked_python, "args": ["-o", "python", "--latest", "--check"]})
    assert "embed archive unavailable" in capsys.readouterr().out
    assert result["readiness"]["kind"] == "unknown"
    assert result["readiness"]["advice"] == ""
    assert result["readiness"]["next_commands"] == []
