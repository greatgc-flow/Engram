"""Behavioral regressions and two-way option parity for the public CLI."""
import argparse
import ast
import inspect
import json
import re
import runpy
import sys
import textwrap
from unittest.mock import Mock
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from core import cli_help, dispatcher, launcher, provisioner, repair


SYS = dispatcher.sys_dir
ROOT = SYS.parent


@pytest.mark.parametrize("verb", ["repair", "relocate"])
@pytest.mark.parametrize("recovery", ["--resume", "--rollback"])
@pytest.mark.parametrize("json_mode", [False, True])
def test_recovery_rejects_dry_run_before_mutation(
    tmp_path, monkeypatch, capsys, verb, recovery, json_mode
):
    monkeypatch.setattr(repair.layout_migration, "supported_layout", lambda *a, **k: True)
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "journal": {"op_id": "pending", "data": {"spec": []}},
    })
    spies = [Mock(return_value={"status": "success", "phase": "COMMITTED"}) for _ in range(3)]
    monkeypatch.setattr(repair.env_ops, "resume", spies[0])
    monkeypatch.setattr(repair.env_ops, "rollback", spies[1])
    monkeypatch.setattr(repair, "_handoff_result", spies[2])
    flags = [recovery, "--dry-run", "--apply", "--yes"]
    if json_mode:
        flags.append("--json")
    result = getattr(repair, verb + "_main")({
        "base_dir": tmp_path, "sys_dir": tmp_path / "_sys",
        "command": verb, "args": flags,
    })
    for spy in spies:
        spy.assert_not_called()
    assert result["exit_code"] == 2 and result["detail"] == "usage"
    output = capsys.readouterr().out
    if json_mode:
        assert json.loads(output)["exit_code"] == 2
    else:
        assert "--dry-run" in output and recovery in output


@pytest.mark.parametrize("verb,flag,declared", [
    ("repair", "--j", "--json"), ("update", "--y", "--yes"),
])
def test_shared_parser_rejects_abbreviations(verb, flag, declared):
    parser = cli_help.CliParser(verb)
    parser.add_argument(declared, action="store_true")
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([flag])
    assert exc.value.code == 2


def test_dispatcher_json_survives_corrupt_env(tmp_path, monkeypatch, capsys):
    target_sys = tmp_path / "_sys"
    target_sys.mkdir()
    (target_sys / "config").mkdir()
    (target_sys / "config" / "environment.json").write_text("{}", encoding="utf-8")
    (target_sys / "env.json").write_text("{bad", encoding="utf-8")
    (target_sys / "dispatch.json").write_text(json.dumps({
        "pipelines": {"snapshots": ["backups.snapshots"]},
        "operations": {"backups.snapshots": {
            "module": "core.backups", "method": "snapshots_main", "failure_policy": "abort",
        }},
    }), encoding="utf-8")
    # Keep real _resolve_paths and the real snapshots operation; isolate OS env setup.
    from core.env_loader import EnvironmentLoader
    monkeypatch.setattr(EnvironmentLoader, "apply_to_os", lambda self: None)
    monkeypatch.setattr(EnvironmentLoader, "get_paths", lambda self: {})
    monkeypatch.setattr(dispatcher, "sys_dir", target_sys)
    monkeypatch.setattr(dispatcher, "base_dir", tmp_path)
    assert dispatcher.main(["dispatcher.py", "snapshots", "list", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert "Failed to load env.json" in captured.err


@pytest.mark.parametrize("failure", ["missing", "spawn"])
def test_explicit_folder_open_fails_if_editor_cannot_launch(tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher, "build_env", lambda *a: {})
    monkeypatch.setattr(launcher, "_note_root_drift", lambda *a: None)
    editor = tmp_path / "Code.exe"
    if failure == "spawn":
        editor.touch()
    monkeypatch.setattr(launcher.provisioner, "vscode_exe", lambda *a: editor)
    monkeypatch.setattr(launcher.provisioner, "seed_vscode_default_settings", lambda *a: None)
    spawn = Mock(side_effect=OSError("cannot start editor"))
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as exc:
        launcher.main({"base_dir": tmp_path, "sys_dir": tmp_path / "_sys", "args": [str(tmp_path)]})
    assert exc.value.code == 1
    assert spawn.call_count == (failure == "spawn")


@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_snapshots_list_rejects_surplus_before_scanning(tmp_path, monkeypatch, flags):
    from core import backups
    scan = Mock(return_value=SimpleNamespace(valid=[], invalid=[], unmarked=[]))
    monkeypatch.setattr(backups, "scan", scan)
    result = backups.snapshots_main({"sys_dir": tmp_path, "args": ["list", "surplus", *flags]})
    scan.assert_not_called()
    assert result["exit_code"] == 2


@pytest.mark.parametrize("result,expected", [
    ({"status": "success"}, 0), ({"status": "failed"}, 1),
    ({"status": "failed", "detail": "Checksum mismatch"}, 2),
    ({"status": "in_use_deferred"}, 3), (RuntimeError("deploy failed"), 1),
])
def test_legacy_setup_executes_deploy_and_maps_exit(tmp_path, monkeypatch, result, expected):
    calls = []

    def deploy(ctx):
        calls.append(ctx)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(provisioner, "deploy", deploy)
    monkeypatch.setattr(sys, "argv", ["setup.py", "--legacy-arg"])
    # setup.py maintains import paths for legacy execution; restore them after runpy.
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SYS / "core" / "setup.py"), run_name="__main__")
    assert exc.value.code == expected
    assert calls == [{
        "base_dir": ROOT, "sys_dir": SYS,
        "paths": {"state": SYS / "data" / "state", "generated": SYS / "data" / "generated"},
        "args": ["--legacy-arg"], "state": {},
    }]


class _ParserCaptured(BaseException):
    """Stop at parsing, before any operation or broad Exception handler."""


def _comparison_flags(fn):
    """Manual parsers declare accepted flags in comparisons, not argparse actions."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    return {
        value.value
        for node in ast.walk(tree) if isinstance(node, ast.Compare)
        for value in ast.walk(node)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
        and re.fullmatch(r"--?[A-Za-z][\w-]*", value.value)
    }


@pytest.mark.parametrize("verb", cli_help.verbs())
def test_public_parser_options_equal_help_options(verb, tmp_path, monkeypatch):
    from core import backups, doctor, isolation_check, tidy_temp, uninstaller, updater
    from checks import backup_personal_data

    ctx = {"base_dir": tmp_path, "sys_dir": tmp_path / "_sys", "command": verb, "args": []}
    entries = {
        "repair": lambda: repair.repair_main(ctx),
        "relocate": lambda: repair.relocate_main(ctx),
        "update": lambda: updater._parse_args([]),
        "tidy": tidy_temp.main,
        "isolation": lambda: isolation_check.run(ctx),
    }
    # These aliases are parsed by engram.cmd before the module runs.
    cmd = (ROOT / "engram.cmd").read_text(encoding="utf-8")
    flags = set(re.findall(r'^if /i "%~2"=="(-[^" ]+)" goto :verb_help_out$', cmd, re.M))
    assert flags == {"-h", "--help"}
    if verb in entries:
        def capture(parser, *a, **k):
            flags.update(option for action in parser._actions for option in action.option_strings
                         if action.help != argparse.SUPPRESS)
            raise _ParserCaptured

        monkeypatch.setattr(cli_help.CliParser, "parse_args", capture)
        with pytest.raises(_ParserCaptured):
            entries[verb]()
    elif verb == "snapshots":
        flags.update(flag for accepted in backups._ACTION_FLAGS.values() for flag in accepted)
    else:
        manual = {
            "open": launcher.main, "doctor": doctor.run, "uninstall": uninstaller.run,
            "backup": backup_personal_data.run_backup,
            "restore": backup_personal_data.run_restore, "reset": backup_personal_data.run_reset,
        }
        if verb in manual:
            flags.update(_comparison_flags(manual[verb]))
        else:
            assert verb in ("menu", "version")  # batch-only commands with help flags only
    documented = cli_help.option_names(verb)
    assert flags == documented, {
        "parser_only": sorted(flags - documented), "help_only": sorted(documented - flags),
    }


def test_sandbox_results_stay_in_supported_layout():
    tests_dir = SYS / "tests"
    config = ElementTree.parse(tests_dir / "sandbox-unit-test.wsb")
    writable = [node.findtext("HostFolder") for node in config.findall("./MappedFolders/MappedFolder")
                if node.findtext("ReadOnly") == "false"]
    assert writable == [r"__PORTABLE_ROOT__\_sys\data\test-results"]
    batch = (tests_dir / "run-sandbox-test.bat").read_text(encoding="utf-8")
    assert r'set "RESULTS_DIR=%BASE_PHYS%\_sys\data\test-results"' in batch
