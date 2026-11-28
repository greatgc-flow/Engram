"""Project runtime selection binds the exact build and preserves other pin files."""
import json
from unittest.mock import Mock

import pytest

from core import env_manifest, python_cli, python_registry
from test_python_registry import candidate


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    system = tmp_path / "system"
    env_manifest.write_manifest(system, {"schema_version": 1, "install_id": "fixture-install",
                                        "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    doc = candidate()
    assert python_registry.publish(system, 0, doc)["phase"] == "COMMITTED"
    executable = system / doc["builds"]["build-a"]["executable_rel"]
    executable.parent.mkdir(parents=True)
    executable.touch()
    project = tmp_path / "project 한글"
    (project / ".git").mkdir(parents=True)
    nested = project / "scripts"
    nested.mkdir()
    monkeypatch.setenv("ENGRAM_CALLER_CWD", str(nested))
    return system, project, executable


def invoke(workspace, *argv):
    return python_cli.run({"sys_dir": workspace[0], "args": list(argv)})


def test_project_pin_conflict_and_removal(workspace, monkeypatch, capsys):
    from core import python_pin

    system, project, executable = workspace
    outside = project / ".python-version"
    outside.write_text("3.15\n")
    assert invoke(workspace, "pin", "3.14", "--json")["exit_code"] == 0
    pin = project / python_pin.FILENAME
    content = pin.read_bytes()
    assert json.loads(content)["build_id"] == "build-a"
    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    assert pin.read_bytes() == content
    spawn = Mock(return_value=Mock(returncode=32))
    monkeypatch.setattr(python_cli.subprocess, "run", spawn)
    assert invoke(workspace, "run", "3.13", "--", "--version")["exit_code"] == 1
    spawn.assert_not_called()
    assert invoke(workspace, "run", "--", "--version")["exit_code"] == 32
    assert spawn.call_args.args[0][0] == str(executable)
    capsys.readouterr()
    assert invoke(workspace, "where", "--json")["exit_code"] == 0
    assert json.loads(capsys.readouterr().out)["executable"] == str(executable)
    assert invoke(workspace, "unpin")["exit_code"] == 0
    assert not pin.exists() and outside.read_text() == "3.15\n"


@pytest.mark.parametrize("action", [("pin", "3.14"), ("unpin",), ("where",)])
def test_malformed_pin_is_preserved(workspace, action):
    from core import python_pin

    pin = workspace[1] / python_pin.FILENAME
    pin.write_bytes(b"{user-owned content")
    assert invoke(workspace, *action)["exit_code"] == 1
    assert pin.read_bytes() == b"{user-owned content"


def test_pin_keeps_previous_exact_build_after_active_build_changes(workspace):
    system, _, executable = workspace
    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    doc = python_registry.inventory(system)["registry"]
    old = doc["builds"]["build-a"]
    old["state"] = "RETAINED"
    doc["builds"]["build-b"] = {**old, "version": "3.14.11", "sha256": "b" * 64, "state": "ACTIVE",
                                "executable_rel": "env/python-versions/3.14/build-b/python.exe"}
    doc["series"]["3.14"]["active_build"] = "build-b"
    doc["revision"] += 1
    assert python_registry.publish(system, 1, doc)["phase"] == "COMMITTED"
    assert invoke(workspace, "where", "3.14")["executable"] == str(executable)


def test_foreign_pin_blocks_execution_and_survives_explicit_unpin(workspace, monkeypatch):
    from core import python_pin

    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    path = workspace[1] / python_pin.FILENAME
    document = json.loads(path.read_bytes())
    document["installation_id"] = "foreign-install"
    foreign = json.dumps(document).encode()
    path.write_bytes(foreign)
    spawn = Mock()
    monkeypatch.setattr(python_cli.subprocess, "run", spawn)
    assert invoke(workspace, "run", "--", "--version")["exit_code"] == 1
    assert invoke(workspace, "unpin")["exit_code"] == 1
    assert path.read_bytes() == foreign
    spawn.assert_not_called()


def test_nested_git_root_has_independent_pin(workspace, monkeypatch):
    from core import python_pin

    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    nested = workspace[1] / "scripts"
    (nested / ".git").write_text("gitdir: ../separate-worktree", encoding="utf-8")
    assert invoke(workspace, "where")["exit_code"] == 1
    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    assert (nested / python_pin.FILENAME).is_file()
    assert (workspace[1] / python_pin.FILENAME).is_file()


def test_use_launches_one_cmd_child_with_pinned_runtime(workspace, monkeypatch):
    import os
    from pathlib import Path
    from core import python_cli

    assert invoke(workspace, "pin", "3.14")["exit_code"] == 0
    monkeypatch.setattr(python_cli.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", str(workspace[1] / "Windows"))
    monkeypatch.setenv("PYTHONPATH", "foreign")
    monkeypatch.setenv("COMSPEC", "unapproved.exe")
    monkeypatch.setenv("PATH", str(workspace[1] / "foreign-path"))
    before = os.environ.copy()
    spawn = Mock(return_value=Mock(returncode=47))
    monkeypatch.setattr(python_cli.subprocess, "run", spawn)
    assert invoke(workspace, "use")["exit_code"] == 47
    command, = spawn.call_args.args
    kwargs = spawn.call_args.kwargs
    windows = Path(before["SystemRoot"])
    assert command == [str(windows / "System32/cmd.exe"), "/d", "/q"]
    assert kwargs["cwd"] == workspace[1] / "scripts"
    assert kwargs["env"]["PATH"].split(os.pathsep) == [
        str(workspace[2].parent), str(windows / "System32"), str(windows),
    ]
    assert kwargs["env"]["COMSPEC"] == command[0]
    assert kwargs["env"]["NoDefaultCurrentDirectoryInExePath"] == "1"
    assert "PYTHONPATH" not in kwargs["env"] and dict(os.environ) == before
    spawn.reset_mock()
    assert invoke(workspace, "use", "3.13")["exit_code"] == 1
    spawn.assert_not_called()
