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
