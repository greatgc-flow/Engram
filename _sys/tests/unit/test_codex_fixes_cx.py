import pytest
from pathlib import Path
from _sys.core import hub, hub_peer

def test_codex_adapter_context_policy():
    adapter = hub_peer.CodexAdapter()
    node = {}
    policy = adapter.context_policy(node)
    
    assert policy.skip_room_context is True
    assert policy.query_first is True

def test_hub_spawn_cwd_resolution(monkeypatch, tmp_path):
    ai_root = tmp_path / "SUBST_DRIVE" / "project" / ".ai"
    ai_root.mkdir(parents=True)
    
    original_resolve = Path.resolve
    def mock_resolve(self, *args, **kwargs):
        if str(self) == str(ai_root.parent):
            return Path("RESOLVED_PATH")
        return original_resolve(self, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", mock_resolve)
    
    pty_cwd = None
    def mock_ask_with_pty(*args, **kwargs):
        nonlocal pty_cwd
        pty_cwd = kwargs.get("cwd")
        class MockRes:
            return_code = 0
            stdout_output = ""
            def __bool__(self): return True
        return MockRes()
    monkeypatch.setattr(hub, "_ask_with_pty", mock_ask_with_pty)

    proc_cwd_val = None
    def mock_spawn_process(*args, **kwargs):
        nonlocal proc_cwd_val
        proc_cwd_val = kwargs.get("cwd")
        class MockProc:
            stdout = None
            stdin = None
            returncode = 0
            def communicate(self, *a, **k): return (b"", b"")
            def wait(self, *a, **k): return 0
        return MockProc()
    monkeypatch.setattr(hub, "_spawn_process", mock_spawn_process)
    monkeypatch.setattr(hub, "_get_logger", lambda: None)
    monkeypatch.setattr(hub, "_ask_health_precheck", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_select_ask_profile", lambda *args, **kwargs: ("cx", {}))
    monkeypatch.setattr(hub, "_get_logger", lambda: None)
    monkeypatch.setattr(hub, "_ask_health_precheck", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_select_ask_profile", lambda *args, **kwargs: ("cx", {}))
    monkeypatch.setattr(hub, "_load_orchestration", lambda *args, **kwargs: {"hub_nodes": [{"node_id": "cx"}], "context_gate": {"enabled": False}})
    monkeypatch.setattr(hub, "_load_nodes", lambda *args, **kwargs: {"cx": {"aliases": [], "node_id": "cx", "adapter": "CodexAdapter"}})
    monkeypatch.setattr(hub, "is_routable", lambda *args, **kwargs: True)
    monkeypatch.setattr(hub, "_terminal_spend_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(hub, "_guard_action", lambda *args, **kwargs: None)
    
    monkeypatch.setattr(hub, "_ContextGate", lambda *args, **kwargs: type("MockGate", (), {"evaluate": lambda *a, **kw: type("MockDec", (), {"is_failover": False, "is_reject": False, "is_yield": False, "recovery_peer": None, "reason_code": None, "message": ""})()})())

    monkeypatch.setattr(hub.snapshot, "pacing_admission_for_profile", lambda *args, **kwargs: "allow")
    import shutil
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: "dummy.exe")
    monkeypatch.setattr(hub, "_resolve_invoke_cli", lambda *args, **kwargs: "dummy.exe")
    
    class ExitException(BaseException): pass
    import sys
    monkeypatch.setattr(sys, "exit", lambda code: (_ for _ in ()).throw(ExitException(f"sys.exit({code})")))
    
    pty_cwd = None
    def mock_ask_with_pty(*args, **kwargs):
        nonlocal pty_cwd
        pty_cwd = kwargs.get("cwd")
        class MockRes:
            return_code = 0
            stdout_output = ""
            elapsed = 1
            text = ""
            lease_id = "test_lease"
            pid = 12345
            def __bool__(self): return True
        return MockRes()
    monkeypatch.setattr(hub, "_ask_with_pty", mock_ask_with_pty)

    proc_cwd_val = None
    def mock_spawn_process(*args, **kwargs):
        nonlocal proc_cwd_val
        proc_cwd_val = kwargs.get("cwd")
        class MockProc:
            stdout = None
            stdin = None
            stderr = None
            returncode = 0
            pid = 12345
            def communicate(self, *a, **k): return (b"", b"")
            def wait(self, *a, **k): return 0
            def poll(self, *a, **k): return 0
        return MockProc()
    monkeypatch.setattr(hub, "_spawn_process", mock_spawn_process)

    # Force subprocess branch
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    
    try:
        hub._action_ask_inner(
            to="cx",
            query="test",
            query_file=None,
            timeout_sec=10,
            ai_root=ai_root,
        )
    except ExitException:
        pass
    
    assert proc_cwd_val == "RESOLVED_PATH", f"subprocess branch cwd not resolved: {proc_cwd_val}"
    
    pass
