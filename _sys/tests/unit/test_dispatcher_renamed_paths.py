"""Issue #95: physical _sys folder is the SSOT for all derived aliases.

Pure tmp_path test: no installed runtime, network, registry, or user files.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

_SYS = find_root(__file__)
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

from core import dispatcher  # noqa: E402


@pytest.mark.parametrize("sys_name", ["_sys", "_sys_custom", "_sys 한글 (test)"])
def test_dispatcher_paths_and_exports_follow_physical_sys(tmp_path, monkeypatch, sys_name):
    root = tmp_path / "Portable 한글 (A) & B"
    physical_sys = root / sys_name
    config = physical_sys / "config" / "environment.json"
    config.parent.mkdir(parents=True)
    shutil.copy2(_SYS / "config" / "environment.json", config)

    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["paths"]["sys"] = "{base}/configured-sys"
    config.write_text(json.dumps(cfg), encoding="utf-8")
    for key in cfg["env_vars"]:
        # Track all exported variables so the fixture restores the process
        # environment after this test even when _resolve_paths applies them.
        monkeypatch.setenv(key, "before-" + key)

    paths = dispatcher._resolve_paths(root, physical_sys)

    assert paths["base"] == root
    assert paths["root"] == root
    assert paths["sys"] == physical_sys
    assert paths["shared"] == root / "_shared"
    for key in ("env", "nodejs", "python", "venv", "data",
                "state", "generated", "logs", "temp", "tools"):
        assert paths[key].is_relative_to(physical_sys), (key, paths[key])

    assert Path(os.environ["PIP_CACHE_DIR"]) == paths["python"] / "pip-cache"
    assert Path(os.environ["PYTHONUSERBASE"]) == paths["python"] / "userbase"
    assert Path(os.environ["NPM_CONFIG_PREFIX"]) == paths["nodejs"] / "npm-global"
    assert Path(os.environ["BAT_CACHE_PATH"]) == paths["tools"] / "bat" / "cache"


def test_explicit_external_state_is_not_overwritten_by_sys_override(tmp_path, monkeypatch):
    root = tmp_path / "root with spaces"
    physical_sys = root / "_sys_custom"
    config = physical_sys / "config" / "environment.json"
    config.parent.mkdir(parents=True)
    cfg = json.loads((_SYS / "config" / "environment.json").read_text(encoding="utf-8"))
    cfg["paths"]["state"] = str(tmp_path / "external-state")
    config.write_text(json.dumps(cfg), encoding="utf-8")
    for key in cfg["env_vars"]:
        monkeypatch.setenv(key, "before-" + key)

    paths = dispatcher._resolve_paths(root, physical_sys)

    assert paths["state"] == tmp_path / "external-state"
    assert paths["python"] == physical_sys / "env" / "python"
    assert paths["shared"] == root / "_shared"


def test_missing_config_fails_without_mutations(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_bytes(b"unchanged")
    before_env = dict(os.environ)
    before_tree = {p.relative_to(tmp_path): p.read_bytes() if p.is_file() else None
                   for p in tmp_path.rglob("*")}

    with pytest.raises(FileNotFoundError):
        dispatcher._resolve_paths(root, root / "_sys_custom")

    assert dict(os.environ) == before_env
    assert {p.relative_to(tmp_path): p.read_bytes() if p.is_file() else None
            for p in tmp_path.rglob("*")} == before_tree
    assert not (root / "_sys_custom").exists()
