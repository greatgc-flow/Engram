"""Offline WP2 inventory through the runtime entry point."""
import json
from pathlib import Path
import pytest


def call(root, args, capsys):
    from core import python_cli
    result = python_cli.run({"sys_dir": root, "args": [*args, "--json"]})
    return result, json.loads(capsys.readouterr().out)


def test_empty_inventory_creates_nothing(tmp_path, capsys):
    root = tmp_path / "portable system"
    result, data = call(root, ["list"], capsys)
    assert result["exit_code"] == 0
    assert data["legacy"]["status"] == "ABSENT" and data["series"] == {}
    assert data["revision"] == 0 and not root.exists()


@pytest.mark.parametrize("args", [["where"], ["where", "3.14"]])
def test_missing_interpreter_never_falls_back(tmp_path, capsys, args):
    result, data = call(tmp_path, args, capsys)
    assert result["exit_code"] == 1 and data["status"] == "failed"
    assert not list(tmp_path.iterdir())


def test_legacy_where_uses_physical_system_directory(tmp_path, capsys):
    exe = tmp_path / "env/venv/Scripts/python.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    result, data = call(tmp_path, ["where"], capsys)
    assert result["exit_code"] == 0 and Path(data["executable"]) == exe


def test_unknown_option_is_usage(tmp_path, capsys):
    from core import python_cli
    with pytest.raises(SystemExit) as exc:
        python_cli.run({"sys_dir": tmp_path, "args": ["--aply"]})
    assert exc.value.code == 2 and "--aply" in capsys.readouterr().out


def test_run_reuses_registered_selection_and_forwards_child_status(tmp_path, monkeypatch, capsys):
    import os
    from subprocess import CompletedProcess
    from unittest.mock import Mock

    from core import env_manifest, python_cli, python_registry
    from test_python_registry import candidate

    root = tmp_path / "portable root" / "system"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                       "root": {"physical": str(root.parent), "logical": str(root.parent)}})
    doc = candidate()
    assert python_registry.publish(root, 0, doc)["phase"] == "COMMITTED"
    exe = root / doc["builds"]["build-a"]["executable_rel"]
    exe.parent.mkdir(parents=True)
    exe.touch()
    cwd = tmp_path / "working 한글"
    cwd.mkdir()
    legacy = root / "env" / "venv"
    external = tmp_path / "external-env"
    tools = tmp_path / "tools"
    for key, value in {
        "ENGRAM_CALLER_CWD": str(cwd),
        "VIRTUAL_ENV": str(external),
        "PYTHONPATH": "bad-import-path",
        "PYTHONHOME": "wrong-python-home",
        "PIP_TARGET": "wrong-install-target",
        "UV_PYTHON": "wrong-python",
        "NPM_CONFIG_PREFIX": "wrong-prefix",
        "PATH": os.pathsep.join(map(str, [legacy / "Scripts", external / "Scripts", tools])),
    }.items():
        monkeypatch.setenv(key, value)
    before = dict(os.environ)
    spawn = Mock(return_value=CompletedProcess([], 75))
    monkeypatch.setattr("subprocess.run", spawn)
    child_args = ["-c", "fixture", "", "--help", "--", "한글 space", "&|!"]
    result = python_cli.run({"sys_dir": root, "args": ["run", "3.14", "--", *child_args]})
    assert result["exit_code"] == 75
    argv, = spawn.call_args.args
    kwargs = spawn.call_args.kwargs
    assert argv == [str(exe), *child_args]
    assert kwargs["cwd"] == cwd
    assert kwargs["env"]["PATH"].split(os.pathsep) == [str(exe.parent), str(tools)]
    assert kwargs["env"]["PYTHONNOUSERSITE"] == "1"
    assert not ({"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "PIP_TARGET", "UV_PYTHON",
                 "NPM_CONFIG_PREFIX"} & kwargs["env"].keys())
    assert dict(os.environ) == before and capsys.readouterr().out == ""


def test_run_refuses_unknown_series_without_starting_a_child(tmp_path, monkeypatch):
    from core import python_cli
    def unexpected(*args, **kwargs):
        pytest.fail("unregistered series must never start a child")
    monkeypatch.setattr("subprocess.run", unexpected)
    assert python_cli.run({"sys_dir": tmp_path, "args": ["run", "3.14", "--", "--version"]})["exit_code"] == 1


@pytest.mark.parametrize("args", [["run"], ["run", "--"], ["run", "3.14", "-m", "pip"],
                                  ["run", "3.14.10", "--", "-V"], ["run", "--json", "--", "-V"]])
def test_run_requires_unambiguous_selector_and_child_boundary(tmp_path, args):
    from core import python_cli
    with pytest.raises(SystemExit) as exc:
        python_cli.run({"sys_dir": tmp_path, "args": args})
    assert exc.value.code == 2
