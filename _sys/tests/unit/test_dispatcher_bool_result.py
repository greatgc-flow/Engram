import pytest
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Import the module to test
from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core.dispatcher import _run_operation, run_pipeline

# Create a dummy module that returns False
dummy_mod = types.ModuleType("dummy_mod")
def dummy_main(ctx):
    return False
dummy_mod.main = dummy_main
sys.modules["dummy_mod"] = dummy_mod

def test_run_operation_false_result():
    # Setup
    op_id = "test_op"
    op_cfg = {"module": "dummy_mod", "failure_policy": "continue"}
    ctx = {}
    
    # Execution
    try:
        result = _run_operation(op_id, op_cfg, ctx)
        
        # Verify result is well-formed to not crash run_pipeline
        assert isinstance(result, dict), "Result should be normalized to a dict"
        assert result.get("status") == "failed"
        assert result.get("operation") == "test_op"
        assert result.get("detail") is False
    except AttributeError as e:
        pytest.fail(f"AttributeError raised: {e}")

def test_run_pipeline_false_result(monkeypatch):
    # Setup for run_pipeline
    monkeypatch.setattr("core.dispatcher._load_json", lambda path: {
        "pipelines": {"testcmd": ["op1"]},
        "operations": {"op1": {"module": "dummy_mod", "failure_policy": "continue"}}
    })
    monkeypatch.setattr("core.dispatcher._build_ctx", lambda cmd, args: {})
    
    # Path mocking for sys.exit or Path.exists()
    dispatch_path_mock = MagicMock()
    dispatch_path_mock.exists.return_value = True
    monkeypatch.setattr("core.dispatcher.sys_dir", dispatch_path_mock / "sys_dir")
    monkeypatch.setattr("pathlib.Path.exists", lambda s: True)
    
    # Expected to raise RuntimeError because pipeline is incomplete (due to failures)
    # But it should NOT raise AttributeError
    with pytest.raises(RuntimeError, match="pipeline 'testcmd' incomplete; failed operations: op1"):
        try:
            # sys.argv needs to be faked or run_pipeline just called directly
            run_pipeline("testcmd", [])
        except AttributeError as e:
            pytest.fail(f"AttributeError raised: {e}")


def test_build_ctx_menu_disable_preloads_prior_state(tmp_path, monkeypatch):
    import json
    from core.dispatcher import _build_ctx
    state_dir = tmp_path / "_sys" / "data" / "state"
    state_dir.mkdir(parents=True)
    reg_state = state_dir / "register.state.json"
    reg_state.write_text(json.dumps({"test_entry": "present"}), encoding="utf-8")

    monkeypatch.setattr("core.dispatcher._resolve_paths", lambda b, s: {"state": state_dir})

    ctx_disable = _build_ctx("menu-disable", [])
    assert "prior_state" in ctx_disable
    assert ctx_disable["prior_state"] == {"test_entry": "present"}

    ctx_unregister = _build_ctx("unregister", [])
    assert "prior_state" in ctx_unregister
    assert ctx_unregister["prior_state"] == {"test_entry": "present"}

