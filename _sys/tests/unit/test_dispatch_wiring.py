import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).parent.parent.parent
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from core import dispatcher  # noqa: E402

def test_actual_dispatch_wiring():
    """
    Verify the actual runtime delegation contract for installation/provisioning.
    Asserts reality, not a wished-for design:
    - dispatch.json routes 'install' to 'provision.deploy' (core.provisioner.deploy)
    - setup.py delegates to core.provisioner.deploy directly (legacy compat)
    """
    root_dir = Path(__file__).parent.parent.parent.parent
    sys_dir = root_dir / "_sys"
    
    # 1. Assert modern wiring (dispatcher.py -> dispatch.json -> core.provisioner.deploy)
    dispatch_file = sys_dir / "dispatch.json"
    assert dispatch_file.exists()
    dispatch_data = json.loads(dispatch_file.read_text(encoding="utf-8"))
    
    install_pipeline = dispatch_data["pipelines"]["install"]
    assert install_pipeline[0] == "provision.deploy", "install pipeline must start with provision.deploy"
    
    provision_op = dispatch_data["operations"]["provision.deploy"]
    assert provision_op["module"] == "core.provisioner", "provision.deploy must map to core.provisioner"
    assert provision_op["method"] == "deploy", "provision.deploy must call deploy method"

    # 2. Assert legacy wiring (setup.py -> core.provisioner.deploy)
    setup_file = sys_dir / "core" / "setup.py"
    assert setup_file.exists()
    setup_content = setup_file.read_text(encoding="utf-8")
    assert "from core.provisioner import deploy" in setup_content, "setup.py must import deploy from core.provisioner"
    assert "deploy(ctx)" in setup_content, "setup.py must call deploy(ctx)"


def test_dispatcher_propagates_failed_result_and_skips_success_state(monkeypatch, tmp_path):
    fake_sys = tmp_path / "_sys"
    state_dir = fake_sys / "data" / "state"
    fake_sys.mkdir()
    (fake_sys / "dispatch.json").write_text(json.dumps({
        "operations": {
            "provision.deploy": {
                "module": "fake.provisioner",
                "method": "deploy",
                "failure_policy": "abort",
            }
        },
        "pipelines": {"install": ["provision.deploy", "state.write"]},
    }), encoding="utf-8")
    ctx = {
        "base_dir": tmp_path,
        "sys_dir": fake_sys,
        "paths": {"state": state_dir},
        "args": [],
        "command": "install",
        "state": {},
    }
    fake_module = SimpleNamespace(deploy=lambda _ctx: {
        "status": "failed", "failed": [{"component": "nodejs"}],
    })
    monkeypatch.setattr(dispatcher, "sys_dir", fake_sys)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *_args: ctx)
    monkeypatch.setattr(dispatcher.importlib, "import_module", lambda _name: fake_module)

    with pytest.raises(RuntimeError, match="operation 'provision.deploy' failed"):
        dispatcher.run_pipeline("install", [])

    assert not (state_dir / "install.state.json").exists()


def test_dispatcher_treats_deferred_result_as_success(monkeypatch, tmp_path):
    fake_sys = tmp_path / "_sys"
    state_dir = fake_sys / "data" / "state"
    fake_sys.mkdir()
    (fake_sys / "dispatch.json").write_text(json.dumps({
        "operations": {
            "provision.deploy": {
                "module": "fake.provisioner",
                "method": "deploy",
                "failure_policy": "abort",
            }
        },
        "pipelines": {"install": ["provision.deploy", "state.write"]},
    }), encoding="utf-8")
    ctx = {
        "base_dir": tmp_path,
        "sys_dir": fake_sys,
        "paths": {"state": state_dir},
        "args": [],
        "command": "install",
        "state": {"deferred": [{"component": "nodejs"}]},
    }
    fake_module = SimpleNamespace(deploy=lambda _ctx: {"status": "deferred"})
    monkeypatch.setattr(dispatcher, "sys_dir", fake_sys)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *_args: ctx)
    monkeypatch.setattr(dispatcher.importlib, "import_module", lambda _name: fake_module)

    dispatcher.run_pipeline("install", [])

    state = json.loads((state_dir / "install.state.json").read_text(encoding="utf-8"))
    assert state["deferred"] == [{"component": "nodejs"}]


def test_dispatcher_continues_unregister_but_preserves_state_on_failure(monkeypatch, tmp_path):
    fake_sys = tmp_path / "_sys"
    state_dir = fake_sys / "data" / "state"
    state_dir.mkdir(parents=True)
    register_state = state_dir / "register.state.json"
    register_state.write_text("{}", encoding="utf-8")
    (fake_sys / "dispatch.json").write_text(json.dumps({
        "operations": {
            "registry.remove": {
                "module": "fake.registrar",
                "method": "remove",
                "failure_policy": "continue",
            },
            "virtual.unmount": {
                "module": "fake.virtualizer",
                "method": "unmount",
                "failure_policy": "continue",
            },
        },
        "pipelines": {
            "unregister": ["registry.remove", "virtual.unmount", "state.prune"],
        },
    }), encoding="utf-8")
    ctx = {
        "base_dir": tmp_path,
        "sys_dir": fake_sys,
        "paths": {"state": state_dir},
        "args": [],
        "command": "unregister",
        "state": {},
    }
    modules = {
        "fake.registrar": SimpleNamespace(remove=lambda _ctx: {
            "status": "failed", "operation": "registry.remove",
        }),
        "fake.virtualizer": SimpleNamespace(unmount=lambda _ctx: {"status": "success"}),
    }
    monkeypatch.setattr(dispatcher, "sys_dir", fake_sys)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *_args: ctx)
    monkeypatch.setattr(dispatcher.importlib, "import_module", modules.__getitem__)

    with pytest.raises(RuntimeError, match="pipeline 'unregister' incomplete"):
        dispatcher.run_pipeline("unregister", [])

    assert register_state.exists()


def test_install_python_update_cannot_rewrite_pin_while_interpreter_exists():
    root_dir = Path(__file__).parent.parent.parent.parent
    content = (root_dir / "INSTALL.bat").read_text(encoding="utf-8")

    assert content.index('set "PY_EXE=%PY_DIR%\\python.exe"') < content.index(
        "Checking for latest stable Python"
    )
    assert "Python consistency check failed" in content
    assert "Not auto-applied: safe in-place Python replacement is not implemented" in content
    assert "New Python version available for first install" in content
    assert 'set "_PY_BUMP=1"' in content
    assert content.count("runtimes.python.version='!PY_VER!'") == 1
    assert "Python bootstrap postcondition failed" in content
    assert content.index("Python bootstrap postcondition failed") < content.index(
        "runtimes.python.version='!PY_VER!'"
    )
    assert "rolling back the bootstrap" in content
