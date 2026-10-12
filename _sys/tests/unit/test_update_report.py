"""Update report with deterministic discovery and readiness; no applies."""
import pytest
import textwrap
from types import SimpleNamespace

from core import repair, updater, version_resolver, version, layout_migration
from checks import check_tool_updates


@pytest.fixture
def report(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, "_python_fetch", lambda *a, **k: None)
    monkeypatch.setattr(repair.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    discovery = {
        "status": "ok", "latest_version": "3.14.8",
        "latest_minor_cycle": "3.14",
        "latest_patch_by_cycle": {"3.13": "3.13.9"},
    }
    payload = {"artifact_dir": "mock-proposal", "updates_discovered": [],
               "not_checked": [], "notices": []}
    monkeypatch.setattr(updater, "_SYS_DIR", tmp_path / "_sys")
    monkeypatch.setattr(updater, "_PORTABLE_ROOT", tmp_path)
    monkeypatch.setattr(layout_migration, "supported_layout", lambda *a: True)
    monkeypatch.setattr(updater.provisioner, "load_json_with_fallback", lambda *a: {})
    monkeypatch.setattr(updater, "check_components", lambda *a: {})
    monkeypatch.setattr(version, "load_version_info", lambda *a: {"version": "3.9.0"})
    monkeypatch.setattr(version_resolver, "resolve_latest", lambda *a, **k:
                        discovery if a else {"status": "ok", "latest_version": "3.9.0"})
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.13.7")
    monkeypatch.setattr(repair, "_python_pin", lambda *a:
                        {"version": "3.13.7", "url": "", "sha256": None})
    monkeypatch.setattr(check_tool_updates, "run", lambda **k: payload)
    monkeypatch.setattr(check_tool_updates, "apply_proposal", lambda *a, **k:
                        pytest.fail("report must not apply"))
    return discovery, payload


@pytest.mark.parametrize("flags", [[], ["--check"], ["--dry-run"]])
def test_report_python_only_updates_never_prompt_or_apply(report, monkeypatch, capsys, flags):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("Python needs its own invocation"))
    if "--check" in flags:
        with pytest.raises(SystemExit) as exc:
            updater.run({"args": flags})
        assert exc.value.code == 0
    else:
        assert updater.run({"args": flags})["status"] == "success"
    output = capsys.readouterr().out
    assert "Installed: 3.13.7" in output
    assert "Latest patch (same minor): 3.13.9" in output
    assert "Latest minor: 3.14 (3.14.8)" in output
    assert "Patch update: engram update -o python -y" in output
    assert ("Python 3.14 dependency readiness verified.\n"
            "  Next: engram update -o python --latest -y\n") in output
    footer = output.split("Next steps:\n")[1].strip().splitlines()
    assert footer == ["engram update -o python -y",
                      "  engram update -o python --latest -y"]
    assert "Everything is up to date." not in output
    assert "bootstrap.bat" not in output
    assert all(line.isascii() and len(line) <= 80 for line in output.splitlines())


def test_report_current_python_and_everything_current(report, capsys):
    discovery, _ = report
    discovery.update(latest_version="3.13.7", latest_minor_cycle="3.13",
                     latest_patch_by_cycle={"3.13": "3.13.7"})
    updater.run({"args": ["--dry-run"]})
    output = capsys.readouterr().out
    assert "Python: 3.13.7 is up to date." in output
    assert output.count("Everything is up to date.") == 1
    assert "Next steps:" not in output
    assert "Latest patch" not in output


@pytest.mark.parametrize("patch,minor,latest,expected", [
    ("3.13.9", "3.13", "3.13.9", ["engram update -o python -y"]),
    ("3.13.7", "3.14", "3.14.8", ["engram update -o python --latest -y"]),
    ("3.13.6", "3.12", "3.12.9", []),
])
def test_python_summary_commands_only_for_newer_versions(report, monkeypatch, patch, minor, latest, expected):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    discovery, _ = report
    discovery.update(latest_version=latest, latest_minor_cycle=minor,
                     latest_patch_by_cycle={"3.13": patch})
    status = repair.python_update_status(updater._SYS_DIR, discovery=discovery)
    assert status["checked"]
    assert status["commands"] == expected


@pytest.mark.parametrize("failure,reason", [
    ("offline", "discovery failed: offline"),
    ("error", "discovery failed: network unavailable"),
    ("missing_patch", "installed minor 3.13 not in release list"),
    ("exception", "discovery failed: offline"),
    ("offline_flag", "offline mode (--offline)"),
    ("missing_minor", "discovery failed: release list missing latest minor"),
    ("missing_latest", "discovery failed: release list missing latest version"),
])
def test_report_python_unchecked_fails_check(
        report, monkeypatch, capsys, failure, reason):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    discovery, _ = report
    flags = ["--check"]
    if failure == "missing_patch":
        discovery["latest_patch_by_cycle"] = {}
    elif failure == "missing_minor":
        discovery.pop("latest_minor_cycle")
    elif failure == "missing_latest":
        discovery.pop("latest_version")
    elif failure == "exception":
        def resolve(*a, **k):
            if a:
                raise OSError("offline")
            return {"status": "ok", "latest_version": "3.9.0"}
        monkeypatch.setattr(version_resolver, "resolve_latest", resolve)
    elif failure == "offline_flag":
        flags.append("--offline")
        def resolve(*a, **k):
            assert not a, "offline Python must not resolve online"
            return {"status": "ok", "latest_version": "3.9.0"}
        monkeypatch.setattr(version_resolver, "resolve_latest", resolve)
    else:
        discovery["status"] = failure
        if failure == "error":
            discovery["detail"] = "network unavailable"
    with pytest.raises(SystemExit) as exc:
        updater.run({"args": flags})
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "\n".join(textwrap.wrap(
        f"Python: {reason}", width=80, subsequent_indent="  ")) in output
    assert "\n".join(textwrap.wrap(
        f"- Python ({reason})", width=80, initial_indent="  ",
        subsequent_indent="    ")) in output
    assert "Not checked:" in output
    assert "Everything is up to date." not in output
    assert "engram update -o python" not in output
    assert all(line.isascii() and len(line) <= 80
               for line in output.splitlines())


@pytest.mark.parametrize("flags", [["--check"], ["--dry-run"],
                                    ["--check", "--offline"],
                                    ["--dry-run", "--offline"]])
@pytest.mark.parametrize("reuse_status", [False, True])
def test_report_missing_python_is_informational(
        report, monkeypatch, capsys, flags, reuse_status):
    discovery, payload = report
    monkeypatch.setattr(repair, "_installed_python", lambda *a: None)
    discovery.update(status="error", detail="network unavailable")
    if reuse_status:
        payload["python_status"] = repair.python_update_status(
            updater._SYS_DIR, discovery=discovery)
    payload["not_checked"] = [{"component": "python", "reason": "manual"}]
    payload["could_not_check"] = [{"component": "python", "detail": "offline"}]
    if "--check" in flags:
        with pytest.raises(SystemExit) as exc:
            updater.run({"args": flags})
        assert exc.value.code == 0
    else:
        assert updater.run({"args": flags})["status"] == "success"
    output = capsys.readouterr().out
    notice = f"Python: not installed under {updater._SYS_DIR / 'env' / 'python'}."
    assert "\n".join(textwrap.wrap(
        notice, width=80, subsequent_indent="  ")) in output
    assert "  Next: _sys\\core\\bootstrap.bat" in output.splitlines()
    assert "Not checked:" not in output
    assert "provider failures" not in output
    assert "engram update -o python" not in output


def test_python_unchecked_discovery_detail_is_short_ascii(report):
    discovery, _ = report
    discovery.update(status="error", detail="HTTP 503\n\uac00 " + "x" * 100)
    status = repair.python_update_status(updater._SYS_DIR,
                                         discovery=discovery)
    assert status["reason"].startswith("discovery failed: HTTP 503 \\uac00 ")
    assert status["reason"].endswith("...")
    assert status["commands"] == []
    assert all(line.isascii() and len(line) <= 80
               for line in status["report_lines"])


def test_python_offline_overrides_supplied_discovery(report):
    discovery, _ = report
    status = repair.python_update_status(
        updater._SYS_DIR, discovery=discovery, offline=True)
    assert not status["checked"]
    assert status["reason"] == "offline mode (--offline)"
    assert status["report_lines"] == ["Python: offline mode (--offline)"]
    assert status["commands"] == []


@pytest.mark.parametrize("flags", [[], ["--check"], ["--dry-run"]])
def test_report_tool_and_python_footer_before_prompt(report, monkeypatch, capsys, flags):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    _, payload = report
    payload["updates_discovered"] = [{"tool": "rg", "section": "tools",
                                      "current_version": "1", "latest_version": "2"}]
    def assert_output():
        output = capsys.readouterr().out
        assert "rg: 1 -> 2" in output
        assert "Core/tools apply here; python/venv/packages need -o, without tool names." in output
        footer = output.split("Next steps:\n")[1].split("\n\n", 1)[0].strip().splitlines()
        assert len(footer) <= 7
        assert "engram update     Apply core + tools after confirmation" in footer[0]
        assert "engram update -y  Apply core + tools without prompting" in footer[1]
        assert "engram update -o packages -y" not in output
        assert all(line.isascii() and len(line) <= 80 for line in footer)
    def decline(*a):
        assert_output()
        return "n"
    monkeypatch.setattr("builtins.input", decline)
    if flags == ["--dry-run"]:
        assert updater.run({"args": flags})["status"] == "success"
        assert_output()
    else:
        with pytest.raises(SystemExit) as exc:
            updater.run({"args": flags})
        assert exc.value.code == (0 if flags else 3)
        if flags:
            assert_output()


def test_report_reuses_discovered_python_status(report, monkeypatch, capsys):
    discovery, payload = report
    resolver_calls = []
    monkeypatch.setattr(repair.subprocess, "run", lambda argv, **k:
                        resolver_calls.append(argv) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    payload["python_status"] = repair.python_update_status(
        updater._SYS_DIR, installed="3.13.7", discovery=discovery)
    assert payload["python_status"]["readiness"].state == "ok"
    payload["notices"] = [{"component": "python", "detail":
                           "Python cannot be updated in-place while Engram is running; "
                           "run 'bootstrap.bat' to update."}]
    payload["not_checked"] = [{"component": "python", "reason": "manual"}]
    monkeypatch.setattr(repair, "python_update_status", lambda *a, **k:
                        pytest.fail("must reuse discovery"))
    updater.run({"args": ["--dry-run"]})
    assert len(resolver_calls) == 1
    output = capsys.readouterr().out
    assert "Installed: 3.13.7" in output
    assert "bootstrap.bat" not in output
    assert "cannot be updated in-place" not in output
    assert "Not checked:" not in output


def test_report_reuses_unchecked_python_reason(report, monkeypatch, capsys):
    discovery, payload = report
    discovery.update(status="error", detail="HTTP 503")
    payload["python_status"] = repair.python_update_status(
        updater._SYS_DIR, discovery=discovery)
    monkeypatch.setattr(repair, "python_update_status", lambda *a, **k:
                        pytest.fail("must reuse discovery"))
    updater.run({"args": ["--dry-run"]})
    output = capsys.readouterr().out
    assert "Python: discovery failed: HTTP 503" in output
    assert "  - Python (discovery failed: HTTP 503)" in output


def test_report_scoped_tools_do_not_check_python(report, monkeypatch, capsys):
    monkeypatch.setattr(repair, "python_update_status", lambda *a, **k:
                        pytest.fail("scoped tools should not discover Python"))
    updater.run({"args": ["--dry-run", "-o", "core"]})
    assert "Python:" not in capsys.readouterr().out


@pytest.mark.parametrize("component", ["python", "venv", "packages"])
def test_report_environment_components_cannot_mix_with_tools(report, capsys, component):
    result = updater.run({"args": ["--dry-run", "-o", component, "core"]})
    assert result["status"] == "failed" and result["exit_code"] == 2
    assert "cannot be combined with tool names" in capsys.readouterr().out


@pytest.mark.parametrize("state,reason", [
    ("ok", ""), ("blocked", "no compatible dependency set"),
    ("unverifiable", "network unavailable"),
])
def test_minor_readiness_controls_headline_and_next_steps(
        report, monkeypatch, capsys, state, reason):
    discovery, _ = report
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    discovery.update(latest_version="3.15.0", latest_minor_cycle="3.15",
                     latest_patch_by_cycle={"3.14": "3.14.8"})
    readiness = repair.PythonReadiness("3.15.0", "url", (), state, reason)
    monkeypatch.setattr(repair, "_minor_readiness", lambda *a, **k: readiness)
    status = repair.python_update_status(updater._SYS_DIR, discovery=discovery)
    assert status["readiness"] is readiness
    assert bool(status["commands"]) == (state == "ok")
    updater.run({"args": ["--dry-run"]})
    output = capsys.readouterr().out
    if state == "ok":
        assert ("Python 3.15 dependency readiness verified.\n"
                "  Next: engram update -o python --latest -y\n") in output
        assert "engram update -o python --latest -y" in output.split("Next steps:")[1]
    else:
        assert "Python: 3.14.8 is up to date." in output
        label = "blocked" if state == "blocked" else "readiness unverifiable"
        assert f"[Warning] Python 3.15 {label}: {reason}." in output
        assert "Next steps:" not in output
        assert "engram update -o python --latest -y" not in output
    assert all(line.isascii() and len(line) <= 80 for line in output.splitlines())


@pytest.mark.parametrize("count", [1, 2])
def test_prompt_change_count(report, monkeypatch, count):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    _, payload = report
    payload["updates_discovered"] = [
        {"tool": f"tool{i}", "section": "tools",
         "current_version": "1", "latest_version": "2"} for i in range(count)]
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "n")
    with pytest.raises(SystemExit) as exc:
        updater.run({"args": []})
    assert exc.value.code == 3
    noun = "change" if count == 1 else "changes"
    assert prompts == [f"\nApply {count} {noun}? [y/N] "]


@pytest.mark.parametrize("kind", ["not_checked", "could_not_check"])
def test_check_fails_for_unchecked_requested_tool(report, kind):
    _, payload = report
    payload[kind] = [{"component": "core", "reason": "offline"}]
    with pytest.raises(SystemExit) as exc:
        updater.run({"args": ["--check", "-o", "core"]})
    assert exc.value.code == 1


def test_unverifiable_readiness_fails_check(report, monkeypatch):
    monkeypatch.setattr(repair, "_minor_readiness", lambda *a, **k:
                        repair.PythonReadiness("3.14.8", "url", (), "unverifiable",
                                               "network unavailable"))
    with pytest.raises(SystemExit) as exc:
        updater.run({"args": ["--check"]})
    assert exc.value.code == 1
