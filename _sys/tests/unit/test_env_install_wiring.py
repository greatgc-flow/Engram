"""Wiring of the fresh-install manifest commit into the `install` pipeline (design section 3)."""
import json
import sys
from pathlib import Path

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))


def _dispatch():
    return json.loads((SYS_DIR / "dispatch.json").read_text(encoding="utf-8"))


def test_install_pipeline_commits_manifest_before_state_is_written():
    pipeline = _dispatch()["pipelines"]["install"]
    assert pipeline == ["provision.deploy", "env.commit_install", "venv.snapshot", "state.write"]
    # order matters: state.write creates install.state.json, which is exactly what
    # commit_install uses to recognise a non-fresh install
    assert pipeline.index("env.commit_install") < pipeline.index("state.write")


def test_commit_install_operation_is_declared_and_importable():
    op = _dispatch()["operations"]["env.commit_install"]
    assert op["module"] == "core.env_manifest"
    assert op["method"] == "commit_install"
    # a manifest write problem must never abort an otherwise successful install
    assert op["failure_policy"] == "warn"
    import importlib
    assert callable(getattr(importlib.import_module(op["module"]), op["method"]))


def test_only_install_runs_the_fresh_install_commit():
    pipelines = _dispatch()["pipelines"]
    holders = [name for name, ops in pipelines.items() if "env.commit_install" in ops]
    assert holders == ["install"]


def test_venv_snapshot_operation_is_declared_warn_only_and_runs_after_install_and_update():
    d = _dispatch()
    op = d["operations"]["venv.snapshot"]
    assert op["module"] == "core.venv_manager" and op["method"] == "snapshot_op"
    assert op["failure_policy"] == "warn"  # a snapshot problem must never fail an install/update
    assert d["pipelines"]["update"][-1] == "venv.snapshot"
    assert d["pipelines"]["install"].index("venv.snapshot") > d["pipelines"]["install"].index("provision.deploy")


def test_snapshots_pipeline_is_wired_to_the_registry_front_end():
    d = _dispatch()
    assert d["pipelines"]["snapshots"] == ["backups.snapshots"]
    op = d["operations"]["backups.snapshots"]
    assert op["module"] == "core.backups" and op["method"] == "snapshots_main"
    import importlib
    assert callable(getattr(importlib.import_module("core.backups"), "snapshots_main"))
