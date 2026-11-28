"""Patch selection stays in the installed series and leaves exact references intact."""

import pytest

from core import env_manifest, python_install, python_provider, python_registry
from test_python_registry import candidate


@pytest.fixture
def existing(tmp_path):
    root = tmp_path / "portable"
    env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "fixture-install",
                                        "root": {"physical": str(tmp_path), "logical": str(tmp_path)}})
    doc = candidate()
    artifact = next(a for a in python_install.offline_artifacts() if a.version.startswith("3.14."))
    doc["builds"]["build-a"].update({**artifact.identity(), "version": "3.14.9", "sha256": "a" * 64})
    assert python_registry.publish(root, 0, doc)["phase"] == "COMMITTED"
    executable = root / doc["builds"]["build-a"]["executable_rel"]
    executable.parent.mkdir(parents=True)
    executable.touch()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / python_provider.asset_name(artifact)).touch()
    return root, cache, doc


def test_update_retains_existing_exact_app_and_old_build(existing, monkeypatch):
    root, cache, old = existing
    preview = python_install.plan_update(root, [], True, cache)
    assert len(preview.staged) == 1 and preview.rows[0]["series"] == "3.14"
    assert preview.rows[0]["installed"] == "3.14.9"
    def stage(root, destination, artifact, source, offline):
        destination.mkdir(parents=True)
        (destination / "python.exe").touch()
    monkeypatch.setattr(python_install, "_stage", stage)
    result = python_install.apply(root, preview)
    assert result["exit_code"] == 0 and result["plan"][0]["status"] == "UPDATED"
    doc = python_registry.inventory(root)["registry"]
    assert doc["revision"] == 2 and doc["builds"]["build-a"]["state"] == "RETAINED"
    assert doc["bindings"] == old["bindings"] and doc["environments"] == old["environments"]
    assert doc["builds"][doc["series"]["3.14"]["active_build"]]["version"] == "3.14.10"
    again = python_install.plan_update(root, [], True, cache)
    assert not again.staged
    assert python_install.apply(root, again)["revision"] == 2


def test_missing_or_failed_update_keeps_exact_preimage(existing, monkeypatch):
    root, cache, _ = existing
    with pytest.raises(ValueError, match="installed"):
        python_install.plan_update(root, ["3.13"], True, cache)
    before = python_registry.registry_path(root).read_bytes()
    preview = python_install.plan_update(root, [], True, cache)
    def stage(*args):
        raise ValueError("fixture postcheck failed")
    monkeypatch.setattr(python_install, "_stage", stage)
    with pytest.raises(ValueError, match="postcheck"):
        python_install.apply(root, preview)
    assert python_registry.registry_path(root).read_bytes() == before


def test_unified_extra_scope_matches_existing_offline_preview(existing, monkeypatch, capsys):
    import json
    from core import python_cli, updater

    root, cache, _ = existing
    standard_cache = root / "data/setup-files/python-archives"
    standard_cache.parent.mkdir(parents=True)
    cache.rename(standard_cache)

    def forbidden(*args, **kwargs):
        pytest.fail("Scoped read-only update reached unrelated discovery or application.")

    monkeypatch.setattr(updater.check_tool_updates, "run", forbidden)
    monkeypatch.setattr(python_install, "apply", forbidden)
    before = python_registry.registry_path(root).read_bytes()
    direct = python_cli.run({"sys_dir": root, "args": ["update", "--check", "--offline", "--json"]})
    capsys.readouterr()
    result = updater.run({"sys_dir": root, "args": [
        "--only", "python-versions", "--offline", "--dry-run", "--yes", "--json",
    ]})
    assert result == direct
    assert json.loads(capsys.readouterr().out)["plan"] == direct["plan"]
    assert [row["series"] for row in result["plan"]] == ["3.14"]
    assert result["plan"][0]["status"] == "READY"
    assert python_registry.registry_path(root).read_bytes() == before


@pytest.mark.parametrize("arguments", [
    ["--only", "python-versions,python"], ["--only", "python-versions", "codex"],
    ["--only", "python-versions", "--latest"], ["--only", "python-versions", "--to", "3.14.10"],
    ["--only", "python-versions", "--force"], ["--only", "python-versions", "--all-packages"],
    ["--only", "python-versions", "--refresh", "--offline"],
    ["--only", "python-versions", "--allow-major-runtime-upgrade"],
])
def test_unified_extra_scope_rejects_other_components_and_unsupported_flags(existing, monkeypatch, arguments):
    from core import python_cli, updater

    root, _, _ = existing

    def forbidden(*args, **kwargs):
        pytest.fail("An invalid update scope entered a lifecycle or discovery handler.")

    monkeypatch.setattr(python_cli, "run", forbidden)
    monkeypatch.setattr(updater.check_tool_updates, "run", forbidden)
    assert updater.run({"sys_dir": root, "args": arguments})["exit_code"] == 2
