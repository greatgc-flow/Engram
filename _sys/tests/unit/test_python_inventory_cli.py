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
