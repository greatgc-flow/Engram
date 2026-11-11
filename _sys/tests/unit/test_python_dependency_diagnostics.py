"""Dependency refusals identify the blocker without exposing noisy pip output."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import python_manager, repair


PREFIX = "no compatible dependency set"


def _readiness(output, *, returncode=1):
    return repair._python_minor_preflight(
        "3.15.2", "https://www.python.org/example.zip",
        managed_python=Path("managed/python.exe"),
        specs=("filelock", "pywinpty==3.0.2", "psutil", "pydantic"),
        fetch=lambda *a, **k: None,
        run=lambda *a, **k: SimpleNamespace(
            returncode=returncode, stdout="", stderr=output),
    )


@pytest.mark.parametrize("output,blocker", [
    (
        "Looking in indexes: https://example.invalid/simple\n"
        "Collecting filelock\nDownloading filelock.whl (1 MB)\n"
        "ERROR: Could not find a version that satisfies the requirement "
        "pywinpty==3.0.2 (from versions: 3.1.0, 3.1.1)\n"
        "ERROR: No matching distribution found for pywinpty==3.0.2\n",
        "pywinpty==3.0.2",
    ),
    (
        "ERROR: Could not find a version that satisfies the requirement "
        "pydantic-core==2.40.1 (from versions: none)",
        "pydantic-core==2.40.1",
    ),
    (
        "ERROR: Package 'psutil' requires a different Python: "
        "3.15.2 not in '<3.15'",
        "psutil",
    ),
])
def test_readiness_preserves_specific_dependency_blocker(output, blocker):
    result = _readiness(output)
    assert result.state == "blocked"
    assert result.reason.startswith(PREFIX)
    assert blocker in result.reason
    assert "Looking in indexes" not in result.reason
    assert "Downloading" not in result.reason


def test_conflicting_versions_survive_generic_resolutionimpossible_footer():
    output = (
        "Collecting pydantic==2.14.2\n"
        "ERROR: Cannot install pydantic==2.14.2 and pydantic-core==2.40.1 "
        "because these package versions have conflicting dependencies.\n\n"
        "The conflict is caused by:\n"
        "    The user requested pydantic-core==2.40.1\n"
        "    pydantic 2.14.2 depends on pydantic-core==2.50.3\n\n"
        "To fix this you could try to:\n"
        "1. loosen the range of package versions you have specified\n\n"
        "ERROR: ResolutionImpossible: for help visit "
        "https://pip.pypa.io/en/latest/topics/dependency-resolution/\n"
    )
    result = _readiness(output)
    assert result.state == "blocked"
    assert "pydantic" in result.reason and "pydantic-core" in result.reason
    assert "2.40.1" in result.reason
    assert "pip.pypa.io" not in result.reason


@pytest.mark.parametrize("output", ["", "ERROR: ResolutionImpossible"])
def test_unavailable_specific_cause_keeps_stable_generic_reason(output):
    assert python_manager.dependency_failure_reason(output) == PREFIX


def test_dependency_reason_redacts_url_credentials_and_sensitive_query():
    output = (
        "ERROR: No matching distribution found for private-lib @ "
        "https://private-user:private-password@example.invalid/private.whl"
        "?access_token=private-token#private-fragment"
    )
    reason = python_manager.dependency_failure_reason(output)
    assert "private-lib" in reason
    for secret in ("private-user", "private-password", "private-token",
                   "private-fragment"):
        assert secret not in reason


def test_dependency_reason_does_not_disclose_url_fragment_without_query():
    output = (
        "ERROR: No matching distribution found for private-lib @ "
        "https://example.invalid/private.whl#private-fragment"
    )
    reason = python_manager.dependency_failure_reason(output)
    assert "private-lib" in reason
    assert "private-fragment" not in reason


def test_dependency_reason_omits_unneeded_nonsecret_url_query_values():
    output = (
        "ERROR: No matching distribution found for private-lib @ "
        "https://example.invalid/private.whl?build=internal-build-id"
    )
    reason = python_manager.dependency_failure_reason(output)
    assert "private-lib" in reason
    assert "internal-build-id" not in reason and "?build=" not in reason


@pytest.mark.parametrize("terminal_control", [
    "\x07",
    "\x7f",
    "\x1b]0;osc-payload\x07",
    "\x1b]0;osc-payload\x1b\\",
], ids=["bell", "delete", "osc-bell", "osc-string-terminator"])
def test_dependency_reason_removes_terminal_controls_and_osc_payload(terminal_control):
    output = (
        "ERROR: No matching distribution found for pywinpty==3.0.2"
        + terminal_control
    )
    reason = python_manager.dependency_failure_reason(output)
    assert reason.startswith(PREFIX) and "pywinpty==3.0.2" in reason
    assert reason.isascii() and reason.isprintable()
    assert "osc-payload" not in reason


def test_dependency_reason_is_bounded_printable_ascii_without_terminal_codes():
    output = (
        "\x1b[31mERROR: Package 'pywinpty' requires a different Python: "
        "3.15.2 not in '<3.15' \uac00 " + "x" * 400 + "\x1b[0m\n"
    )
    reason = python_manager.dependency_failure_reason(output)
    assert reason.startswith(PREFIX)
    assert "pywinpty" in reason
    assert len(reason) <= 240
    assert reason.isascii() and reason.isprintable()
    assert "\x1b" not in reason and "\n" not in reason


def test_network_failure_remains_unverifiable_even_with_distribution_error():
    result = _readiness(
        "WARNING: Retrying after connection broken by ProxyError\n"
        "ERROR: No matching distribution found for pywinpty==3.0.2"
    )
    assert result.state == "unverifiable"
    assert result.reason == "network unavailable"


def test_successful_resolution_does_not_report_ignored_candidate_as_blocker():
    result = _readiness(
        "Ignored versions that require a different Python: <3.15\n"
        "Would install pywinpty-3.1.2",
        returncode=0,
    )
    assert result.state == "ok" and not result.reason


@pytest.mark.parametrize("offline", [False, True])
def test_target_interpreter_restore_reports_blocker_and_cleans_probe(tmp_path, offline):
    snapshot = {"packages": [
        {"name": "pydantic", "version": "2.12", "requested": True},
    ]}
    calls = []

    def runner(argv, timeout):
        calls.append(argv)
        if "virtualenv" in argv:
            executable = Path(argv[-1]) / "Scripts" / "python.exe"
            executable.parent.mkdir(parents=True)
            executable.write_text("disposable probe", encoding="utf-8")
            return 0, ""
        assert "--dry-run" in argv and "--ignore-installed" in argv
        assert "pydantic==2.12" in argv
        return 1, "ERROR: No matching distribution found for pydantic-core==2.40.1"

    with pytest.raises(RuntimeError) as exc:
        python_manager.preflight_restore(
            tmp_path / "staged-python.exe", snapshot,
            runner=runner, parent=tmp_path, offline=offline,
        )
    reason = str(exc.value)
    if offline:
        assert reason == "required artifacts unavailable offline"
    else:
        assert reason.startswith(PREFIX) and "pydantic-core==2.40.1" in reason
    assert len(calls) == 2
    assert list(tmp_path.iterdir()) == []


def test_status_names_blocking_installed_pin_without_upgrade_advice(tmp_path, monkeypatch):
    monkeypatch.setattr(repair.venv_manager, "build_snapshot", lambda *a, **k: {
        "packages": [{"name": "pywinpty", "version": "3.0.2", "requested": True}],
    })
    calls = []

    def resolver(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(
            returncode=1, stdout="",
            stderr="ERROR: No matching distribution found for pywinpty==3.0.2",
        )

    status = repair.python_update_status(
        tmp_path, installed="3.14.10",
        pin={"version": "3.15.2", "url": "https://www.python.org/example.zip",
             "sha256": None},
        discovery={"status": "ok", "latest_version": "3.15.2",
                   "latest_minor_cycle": "3.15",
                   "latest_patch_by_cycle": {"3.14": "3.14.10"}},
        seams={"fetch": lambda *a, **k: None, "resolver_run": resolver},
    )
    report = "\n".join(status["report_lines"])
    assert "Python 3.15 blocked" in report
    assert "pywinpty==3.0.2" in report
    assert "Latest minor: 3.15 (3.15.2)" in report
    assert "up to date" not in report
    assert "engram update -o python --latest -y" not in report
    assert status["commands"] == []
    assert len(calls) == 1 and "pywinpty==3.0.2" in calls[0]
    assert all(line.isascii() and len(line) <= 80 for line in status["report_lines"])
