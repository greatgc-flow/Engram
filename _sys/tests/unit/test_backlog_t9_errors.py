import sys
from pathlib import Path

def test_config_loader_error_handling(monkeypatch, tmp_path):
    """Ensure get_runtimes_config and get_env_config surface IO errors via stderr."""
    sys_dir = Path(__file__).parent.parent.parent.resolve()
    if str(sys_dir) not in sys.path:
        sys.path.insert(0, str(sys_dir))
    
    from core.config import ConfigManager
    
    class MockStderr:
        def __init__(self):
            self.written = []
        def write(self, s):
            self.written.append(s)
        def flush(self): pass
        
    # Files must exist so the .exists() guard lets us reach the try/except
    # around open() - only open() itself is mocked to fail.
    (tmp_path / "runtimes.json").write_text("{}", encoding="utf-8")
    (tmp_path / "env.json").write_text("{}", encoding="utf-8")

    mock_stderr = MockStderr()
    monkeypatch.setattr(sys, "stderr", mock_stderr)
    monkeypatch.setattr(ConfigManager, "get_sys_dir", lambda: tmp_path)

    def mock_open(*args, **kwargs):
        raise PermissionError("Access Denied Test")

    monkeypatch.setattr("builtins.open", mock_open)
    
    assert ConfigManager.get_runtimes_config() == {}
    assert ConfigManager.get_env_config() == {}
    
    stderr_out = "".join(mock_stderr.written)
    assert "get_runtimes_config error" in stderr_out
    assert "get_env_config error" in stderr_out

def test_log_p2p_ask_surfaces_error(monkeypatch, tmp_path):
    """Ensure _append_ask_history surfaces IO errors via action_report_error."""
    from core import hub
    
    reported_errors = []
    def mock_report_error(ai_root, peer, pattern, detail="", severity="warn"):
        reported_errors.append((pattern, detail))
        
    monkeypatch.setattr(hub, "action_report_error", mock_report_error)
    
    def mock_open(*args, **kwargs):
        raise PermissionError("Disk Full Test")
        
    monkeypatch.setattr("builtins.open", mock_open)
    
    hub._append_ask_history(tmp_path, "test_peer", "query.txt", "output.txt", 1, True, None)
    
    assert len(reported_errors) == 1
    assert reported_errors[0][0] == "ask_history_append_failed"
    assert "Disk Full Test" in reported_errors[0][1]

def test_real_arbiter_invoker_uses_timeout(monkeypatch):
    """Ensure _real_arbiter_invoker uses invocation_timeout_sec from config."""
    from core import hub
    import subprocess
    
    invoker_func = hub._real_arbiter_invoker(None)
    monkeypatch.setattr(hub, "_final_arbiter_config", lambda: {"invocation_timeout_sec": 42})
    
    captured_timeout = []
    class MockResult:
        stdout = "test_reply\n"
    
    def mock_run(*args, **kwargs):
        captured_timeout.append(kwargs.get("timeout"))
        return MockResult()
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    reply = invoker_func("test_arbiter", "hello")
    assert reply == "test_reply"
    assert captured_timeout == [42]

