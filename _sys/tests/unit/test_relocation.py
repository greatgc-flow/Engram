import json
import os
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

from core import relocation, env_ops, env_manifest

class FakeRegistry(relocation.RegistryOps):
    def __init__(self):
        self.removed = []
        self.exported = False
        self.reimported = False
        self.menu_enabled = False
        self.entries = [{"key_name": "SandboxRun_D_old"}]
        
    def entries_for_root(self, old_root, localappdata):
        return self.entries
        
    def export(self, entries, dest_file):
        self.exported = True
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(json.dumps(entries))
        
    def remove(self, entries):
        self.removed.extend(entries)
        self.entries = []
        
    def reimport(self, export_file):
        self.reimported = True
        self.entries = json.loads(export_file.read_text())
        
    def enable_menu(self, ctx):
        self.menu_enabled = True

def test_derive_menu_intent_true(tmp_path):
    sys_dir = tmp_path / "_sys"
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir()
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "register.state.json"
    state_file.write_text(json.dumps({"registry_entries": [{"key_name": "test_key", "reg_keys": ["HKCU\\test"]}]}))
    (localappdata / "test_key.bat").write_text("relay")
    assert relocation.derive_menu_intent(sys_dir, localappdata) == True

def test_derive_menu_intent_false(tmp_path):
    sys_dir = tmp_path / "_sys"
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir()
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "register.state.json"
    state_file.write_text(json.dumps({"registry_entries": [{"key_name": "test_key", "reg_keys": ["HKCU\\test"]}]}))
    assert relocation.derive_menu_intent(sys_dir, localappdata) == False

def test_derive_menu_intent_no_state(tmp_path):
    sys_dir = tmp_path / "_sys"
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir()
    assert relocation.derive_menu_intent(sys_dir, localappdata) == False

def test_entries_for_root_foreign_installs(tmp_path):
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir()
    (localappdata / "SandboxRun_old.root.txt").write_bytes(b"D:\\old_base\r\n")
    (localappdata / "SandboxRun_foreign.root.txt").write_bytes(b"D:\\foreign_base\r\n")
    registry = relocation.RegistryOps()
    entries = registry.entries_for_root("D:\\old_base", localappdata)
    assert len(entries) == 1
    assert entries[0]["key_name"] == "SandboxRun_old"

def test_plan_relocation_move_order(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    drift = env_manifest.RootDrift("moved", "D:\\old_base", "manifest")
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old_base", "physical": "D:\\old_base"}, "install_id": "123"}
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=tmp_path)
    names = [s.name for s in steps]
    assert names == [
        "export-registry-keys",
        "remove-stale-registry-entries",
        "regenerate-state-files",
        "rebase-git-config",
        "write-manifest",
        "write-last-base-dir"
    ]

def test_plan_relocation_copy_order(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    drift = env_manifest.RootDrift("copied", "D:\\old_base", "manifest")
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old_base", "physical": "D:\\old_base"}, "install_id": "123"}
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=tmp_path)
    names = [s.name for s in steps]
    assert names == [
        "regenerate-state-files",
        "rebase-git-config",
        "write-manifest",
        "write-last-base-dir"
    ]

def test_plan_relocation_menu_disabled_no_reenable_step(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    drift = env_manifest.RootDrift("moved", "D:\\old_base", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path)
    names = [s.name for s in steps]
    assert "re-enable-menu" not in names

def test_remap_ai_state_success(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    localappdata = tmp_path / "local"
    sys_dir.mkdir()
    base_dir.mkdir()
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    claude_dir = base_dir / ".engram" / "claude"
    claude_dir.mkdir(parents=True)
    import re
    old_slug = re.sub(r'[^A-Za-z0-9]', '-', "D:\\old\\proj")
    new_slug = re.sub(r'[^A-Za-z0-9]', '-', str(base_dir / "proj"))
    (claude_dir / "projects" / old_slug).mkdir(parents=True)
    data = {"projects": {"D:\\old\\proj": {"mcpServers": {"test": {"command": "D:\\old\\bin"}}}}}
    (claude_dir / ".claude.json").write_text(json.dumps(data))
    
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=localappdata, remap_ai_state=True, process_running=lambda x: False)
    env_ops.execute(sys_dir, "relocate", steps)
    
    new_data = json.loads((claude_dir / ".claude.json").read_text())
    assert str(base_dir / "proj") in new_data["projects"]
    assert not (claude_dir / "projects" / old_slug).exists()
    assert (claude_dir / "projects" / new_slug).exists()

def test_remap_ai_state_refused_if_claude_running(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path, remap_ai_state=True, process_running=lambda name: name == "claude.exe")
    res = env_ops.execute(sys_dir, "relocate", steps)
    assert res["status"] == "failed"
    assert res["failed_step"] == "remap-ai-state"

def test_remap_ai_state_invalid_json_skipped(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    claude_dir = base_dir / ".engram" / "claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / ".claude.json").write_text("invalid json")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path, remap_ai_state=True, process_running=lambda x: False)
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "remap-ai-state":
            s.do(ctx)
            assert ctx.data.get("ai_state_skipped") is True

def test_remap_ai_state_slug_collision(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    claude_dir = base_dir / ".engram" / "claude"
    claude_dir.mkdir(parents=True)
    import re
    old_slug = re.sub(r'[^A-Za-z0-9]', '-', "D:\\old\\proj")
    new_slug = re.sub(r'[^A-Za-z0-9]', '-', str(base_dir / "proj"))
    (claude_dir / "projects" / old_slug).mkdir(parents=True)
    (claude_dir / "projects" / new_slug).mkdir(parents=True)
    data = {"projects": {"D:\\old\\proj": {}}}
    (claude_dir / ".claude.json").write_text(json.dumps(data))
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path, remap_ai_state=True, process_running=lambda x: False)
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "remap-ai-state":
            s.do(ctx)
            assert old_slug in ctx.data.get("ai_state_slug_collisions", [])
    assert (claude_dir / "projects" / old_slug).exists()
    assert (claude_dir / "projects" / new_slug).exists()

def test_state_regeneration(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "install.state.json").write_text(json.dumps({"base_dir": "D:\\old"}))
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path)
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "regenerate-state-files":
            s.do(ctx)
    assert json.loads((state_dir / "install.state.json").read_text())["base_dir"] == str(base_dir)

def test_git_config_rebase(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    git_dir = base_dir / ".engram" / "git"
    git_dir.mkdir(parents=True)
    (git_dir / ".gitconfig").write_text("[safe]\n\tdirectory = D:\\old\\repo\n")
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path)
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "rebase-git-config":
            s.do(ctx)
    text = (git_dir / ".gitconfig").read_text()
    assert str(base_dir / "repo") in text

def test_manifest_keeps_unknown_keys_on_move(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old", "physical": "D:\\old"}, "install_id": "123", "unknown_key": "val"}
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=tmp_path)
    env_ops.execute(sys_dir, "relocate", steps)
    new_man = env_manifest.read_manifest(sys_dir).data
    assert new_man["unknown_key"] == "val"
    assert new_man["install_id"] == "123"

def test_manifest_install_id_changes_on_copy(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("copied", "D:\\old", "manifest")
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old", "physical": "D:\\old"}, "install_id": "123"}
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=tmp_path)
    env_ops.execute(sys_dir, "relocate", steps)
    new_man = env_manifest.read_manifest(sys_dir).data
    assert new_man["install_id"] != "123"

def test_last_base_dir_only_by_last_step(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path)
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "write-last-base-dir":
            s.do(ctx)
            assert s.done(ctx) is True
    assert (sys_dir / "data" / "last_base_dir.txt").read_text().strip() == str(base_dir)

def test_idempotence(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old", "physical": "D:\\old"}, "install_id": "123"}
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=tmp_path, registry=registry)
    res1 = env_ops.execute(sys_dir, "relocate", steps)
    assert res1["status"] == "success"
    res2 = env_ops.execute(sys_dir, "relocate", steps)
    assert res2["status"] == "success"

def _hash_tree(p: Path):
    out = {}
    for root, _, files in os.walk(p):
        for f in files:
            path = Path(root) / f
            rel = path.relative_to(p).as_posix()
            if "env-op.journal" in rel or "data/backups" in rel:
                continue
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out

def _setup_rollback_env(tmp_path):
    sys_dir = tmp_path / "env" / "_sys"
    base_dir = tmp_path / "env"
    localappdata = tmp_path / "localappdata"
    localappdata.mkdir(parents=True)
    sys_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    manifest = {"schema_version": "1.0", "root": {"logical": "D:\\old", "physical": "D:\\old"}, "install_id": "123"}
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "install.state.json").write_text(json.dumps({"base_dir": "D:\\old"}))
    git_dir = base_dir / ".engram" / "git"
    git_dir.mkdir(parents=True)
    (git_dir / ".gitconfig").write_bytes(b'[safe]\r\n\tdirectory = D:\\old\\repo\r\n')
    claude_dir = base_dir / ".engram" / "claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / ".claude.json").write_bytes(json.dumps({"projects": {"D:\\old\\proj": {}}}).encode("utf-8"))
    import re
    old_slug = re.sub(r'[^A-Za-z0-9]', '-', "D:\\old\\proj")
    (claude_dir / "projects" / old_slug).mkdir(parents=True)
    (claude_dir / "auth.json").write_text('{"secret": 1}')
    return sys_dir, base_dir, localappdata, drift, manifest

def test_rollback_export_registry_keys(tmp_path):
    sys_dir, base_dir, localappdata, drift, manifest = _setup_rollback_env(tmp_path)
    before = _hash_tree(tmp_path)
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False)
    try:
        env_ops.execute(sys_dir, "relocate", steps, crash_after="export-registry-keys")
    except env_ops.SimulatedCrash:
        pass
    env_ops.rollback(sys_dir, lambda active: relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False))
    assert _hash_tree(tmp_path) == before

def test_rollback_remove_stale_registry_entries(tmp_path):
    sys_dir, base_dir, localappdata, drift, manifest = _setup_rollback_env(tmp_path)
    before = _hash_tree(tmp_path)
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False)
    try:
        env_ops.execute(sys_dir, "relocate", steps, crash_after="remove-stale-registry-entries")
    except env_ops.SimulatedCrash:
        pass
    env_ops.rollback(sys_dir, lambda active: relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False))
    assert _hash_tree(tmp_path) == before

def test_rollback_regenerate_state_files(tmp_path):
    sys_dir, base_dir, localappdata, drift, manifest = _setup_rollback_env(tmp_path)
    before = _hash_tree(tmp_path)
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False)
    try:
        env_ops.execute(sys_dir, "relocate", steps, crash_after="regenerate-state-files")
    except env_ops.SimulatedCrash:
        pass
    env_ops.rollback(sys_dir, lambda active: relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False))
    assert _hash_tree(tmp_path) == before

def test_rollback_rebase_git_config(tmp_path):
    sys_dir, base_dir, localappdata, drift, manifest = _setup_rollback_env(tmp_path)
    before = _hash_tree(tmp_path)
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False)
    try:
        env_ops.execute(sys_dir, "relocate", steps, crash_after="rebase-git-config")
    except env_ops.SimulatedCrash:
        pass
    env_ops.rollback(sys_dir, lambda active: relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False))
    assert _hash_tree(tmp_path) == before

def test_rollback_remap_ai_state(tmp_path):
    sys_dir, base_dir, localappdata, drift, manifest = _setup_rollback_env(tmp_path)
    before = _hash_tree(tmp_path)
    registry = FakeRegistry()
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False)
    try:
        env_ops.execute(sys_dir, "relocate", steps, crash_after="remap-ai-state")
    except env_ops.SimulatedCrash:
        pass
    env_ops.rollback(sys_dir, lambda active: relocation.plan_relocation(sys_dir, base_dir, manifest=manifest, drift=drift, localappdata=localappdata, registry=registry, remap_ai_state=True, process_running=lambda x: False))
    assert _hash_tree(tmp_path) == before

def test_plan_relocation_no_psutil_import_when_remap_ai_state_false(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    drift = env_manifest.RootDrift("moved", "D:\\old_base", "manifest")
    monkeypatch.setitem(sys.modules, "psutil", None)
    
    # Should not raise ImportError
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path, remap_ai_state=False)
    assert len(steps) > 0

def test_remap_ai_state_fallback_tasklist(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    localappdata = tmp_path / "local"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    claude_dir = base_dir / ".engram" / "claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / ".claude.json").write_text(json.dumps({"projects": {}}))
    
    monkeypatch.setitem(sys.modules, "psutil", None)
    
    def fake_runner(argv):
        if "tasklist" in argv and "claude.exe" in argv[-2]:
            return 0, "claude.exe      1234 Console      1      50,000 K"
        return -1, ""
        
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=localappdata, remap_ai_state=True, runner=fake_runner)
    
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    for s in steps:
        if s.name == "remap-ai-state":
            with pytest.raises(RuntimeError, match="claude.exe is running"):
                s.do(ctx)

def test_regenerate_state_files_crash_resumption(tmp_path):
    sys_dir = tmp_path / "_sys"
    base_dir = tmp_path / "new_base"
    sys_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    
    (state_dir / "install.state.json").write_text(json.dumps({"base_dir": "D:\\old"}))
    (state_dir / "register.state.json").write_text(json.dumps({"some_path": "D:\\old\\path"}))
    
    drift = env_manifest.RootDrift("moved", "D:\\old", "manifest")
    steps = relocation.plan_relocation(sys_dir, base_dir, manifest=None, drift=drift, localappdata=tmp_path)
    
    ctx = env_ops.OpContext(sys_dir, "op", "kind", {}, {})
    regen_step = next(s for s in steps if s.name == "regenerate-state-files")
    
    # Simulate partial execution
    (state_dir / "install.state.json").write_text(json.dumps({"base_dir": str(base_dir)}))
    
    assert regen_step.done(ctx) is False
    
    regen_step.do(ctx)
    assert regen_step.done(ctx) is True
