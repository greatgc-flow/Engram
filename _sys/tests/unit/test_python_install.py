"""Selective install publishes verified series as a single registry generation."""
from pathlib import Path

import pytest

from core import env_manifest, python_registry


@pytest.fixture
def root(tmp_path):
    system = tmp_path / "portable system"
    env_manifest.write_manifest(system, {"schema_version": 1, "install_id": "fixture-install",
                                        "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    return system


def test_preview_and_cancel_have_no_effect(root, tmp_path, monkeypatch):
    from core import python_install
    cache = tmp_path / "cache"
    selected = ["3.14"]
    before = set(root.rglob("*"))
    plan = python_install.plan(root, selected, False, True, cache)
    assert [row["series"] for row in plan.rows] == selected
    assert plan.rows[0]["status"] == "MISSING_CACHE"
    assert set(root.rglob("*")) == before and not cache.exists()
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert python_install.run(root, selected, all_supported=False, offline=True,
                              cache=cache, preview=True, yes=False)["exit_code"] == 1


def test_batch_publishes_only_selected_builds_once(root, tmp_path, monkeypatch):
    from core import python_install
    cache = tmp_path / "cache"
    cache.mkdir()
    for artifact in python_install.offline_artifacts():
        (cache / python_install.python_provider.asset_name(artifact)).touch()
    plan = python_install.plan(root, ["3.14", "3.13"], False, True, cache)
    observed = []
    def stage(root, destination, artifact, source, offline):
        assert source.is_file() and offline
        destination.mkdir()
        (destination / "python.exe").touch()
        observed.append(artifact.version)
    monkeypatch.setattr(python_install, "_stage", stage)
    result = python_install.apply(root, plan)
    assert result["exit_code"] == 0 and len(observed) == 2
    registry = python_registry.inventory(root)["registry"]
    assert registry["revision"] == 1 and set(registry["series"]) == {"3.14", "3.13"}
    assert registry["default_binding"] == "legacy-default"
    assert python_install.apply(root, python_install.plan(root, ["3.14"], False, True, cache))["status"] == "success"
    assert observed == ["3.14.10", "3.13.18"]
    assert python_registry.inventory(root)["revision"] == 1


def test_failed_second_stage_keeps_registry_and_removes_own_first_stage(root, tmp_path, monkeypatch):
    from core import python_install
    cache = tmp_path / "cache"
    cache.mkdir()
    for artifact in python_install.offline_artifacts():
        (cache / python_install.python_provider.asset_name(artifact)).touch()
    parent = root / "env/python-versions/3.14"
    parent.mkdir(parents=True)
    other = parent / "unowned"
    other.mkdir()
    plan = python_install.plan(root, ["3.14", "3.13"], False, True, cache)
    def stage(root, destination, artifact, source, offline):
        if artifact.version.startswith("3.13"):
            raise ValueError("fixture failure")
        destination.mkdir()
        (destination / "python.exe").touch()
    monkeypatch.setattr(python_install, "_stage", stage)
    with pytest.raises(ValueError, match="fixture failure"):
        python_install.apply(root, plan)
    assert python_registry.inventory(root)["revision"] == 0
    assert list(parent.iterdir()) == [other]


def test_cli_offline_dry_run_is_one_json_object(root, tmp_path, capsys):
    import json
    from core import python_cli
    result = python_cli.run({"sys_dir": root, "args": ["install", "3.14", "--offline", "--dry-run",
                                                         "--cache-dir", str(tmp_path / "empty"), "--json"]})
    data = json.loads(capsys.readouterr().out)
    assert result["exit_code"] == 1 and data["plan"][0]["status"] == "MISSING_CACHE"
    assert not (root / "env").exists()
