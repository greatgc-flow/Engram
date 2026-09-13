import json
import logging
from pathlib import Path
import pytest
from unittest.mock import patch

from _sys.core.layout_migration import merge_declarations_impl

@pytest.fixture
def migration_env(tmp_path):
    # Setup mock paths inside tmp_path
    live_dir = tmp_path / "_sys"
    live_dir.mkdir()
    
    defaults_dir = tmp_path / "_sys" / "defaults"
    defaults_dir.mkdir(parents=True)
    
    base_state_dir = tmp_path / "_sys" / "data" / "state" / "defaults-base"
    base_state_dir.mkdir(parents=True)
    
    manifest_base_dir = tmp_path / "_sys" / "core" / "release-manifests" / "3.2.6-defaults"
    manifest_base_dir.mkdir(parents=True)
    
    return {
        "live": live_dir,
        "defaults": defaults_dir,
        "base_state": base_state_dir,
        "manifest": manifest_base_dir
    }

def test_merge_declarations_runtimes(migration_env, caplog):
    caplog.set_level(logging.INFO)
    
    # 1. ours == base -> take theirs
    # 2. ours advanced -> ours != base, keep ours, reported
    # 3. component added upstream -> added
    # 4. component removed upstream with ours == base -> removed
    # 5. component removed upstream with ours != base -> kept, reported
    # 6. _comment taken from theirs
    
    base_json = {
        "_comment": "old comment",
        "runtimes": {
            "python": {"version": "3.13"}, # ours == base
            "nodejs": {"version": "20.0"}, # ours != base (advanced)
            "go": {"version": "1.20"} # removed upstream, ours == base
        },
        "tools": {
            "rg": {"version": "12.0"} # removed upstream, ours != base
        }
    }
    
    ours_json = {
        "_comment": "old comment",
        "runtimes": {
            "python": {"version": "3.13"},
            "nodejs": {"version": "20.1"}, # advanced locally
            "go": {"version": "1.20"}
        },
        "tools": {
            "rg": {"version": "13.0"} # advanced locally, removed upstream
        }
    }
    
    theirs_json = {
        "_comment": "new comment", # taken from theirs
        "runtimes": {
            "python": {"version": "3.14"}, # ours == base, take theirs
            "nodejs": {"version": "22.0"}, # ours != base, keep ours
            "rust": {"version": "1.70"} # added upstream
        },
        "tools": {}
    }
    
    with open(migration_env["base_state"] / "runtimes.json", "w") as f:
        json.dump(base_json, f)
    with open(migration_env["live"] / "runtimes.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "runtimes.json", "w") as f:
        json.dump(theirs_json, f)
        
    merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
    
    # Assertions
    with open(migration_env["live"] / "runtimes.json") as f:
        merged = json.load(f)
        
    assert merged["_comment"] == "new comment"
    assert merged["runtimes"]["python"]["version"] == "3.14" # take theirs
    assert merged["runtimes"]["nodejs"]["version"] == "20.1" # keep ours
    assert merged["runtimes"]["rust"]["version"] == "1.70" # added
    assert "go" not in merged["runtimes"] # removed
    assert merged["tools"]["rg"]["version"] == "13.0" # kept, reported
    
    assert "kept local modifications instead of taking upstream update" in caplog.text
    assert "kept local modifications despite upstream removal" in caplog.text
    
    # Assert backups
    assert (migration_env["base_state"] / "runtimes.json.pre-merge.bak").exists()
    
    # Assert base updated
    with open(migration_env["base_state"] / "runtimes.json") as f:
        new_base = json.load(f)
    assert new_base["runtimes"]["python"]["version"] == "3.14"


def test_merge_declarations_tool_catalog(migration_env):
    base_json = {
        "$schema": "old",
        "tools": [
            {"tool_id": "a", "v": "1"}, # ours == base
            {"tool_id": "b", "v": "1"}, # ours != base
            {"tool_id": "c", "v": "1"}, # removed, ours == base
            {"tool_id": "d", "v": "1"}  # removed, ours != base
        ]
    }
    
    ours_json = {
        "$schema": "old",
        "tools": [
            {"tool_id": "a", "v": "1"},
            {"tool_id": "b", "v": "2"},
            {"tool_id": "c", "v": "1"},
            {"tool_id": "d", "v": "2"}
        ]
    }
    
    theirs_json = {
        "$schema": "new",
        "tools": [
            {"tool_id": "a", "v": "3"},
            {"tool_id": "b", "v": "3"},
            {"tool_id": "e", "v": "1"}
        ]
    }
    
    with open(migration_env["base_state"] / "tool-catalog.v1.json", "w") as f:
        json.dump(base_json, f)
    with open(migration_env["live"] / "tool-catalog.v1.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "tool-catalog.v1.json", "w") as f:
        json.dump(theirs_json, f)
        
    merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
    
    with open(migration_env["live"] / "tool-catalog.v1.json") as f:
        merged = json.load(f)
        
    assert merged["$schema"] == "new"
    
    tools = {t["tool_id"]: t["v"] for t in merged["tools"]}
    assert tools["a"] == "3"
    assert tools["b"] == "2"
    assert "c" not in tools
    assert tools["d"] == "2"
    assert tools["e"] == "1"

def test_atomic_write_exception(migration_env, monkeypatch):
    ours_json = {"runtimes": {}}
    theirs_json = {"runtimes": {}}
    
    with open(migration_env["live"] / "runtimes.json", "w") as f:
        json.dump(ours_json, f)
    with open(migration_env["defaults"] / "runtimes.json", "w") as f:
        json.dump(theirs_json, f)
        
    # Inject exception during _atomic_write_json
    def mock_atomic_write(*args, **kwargs):
        raise OSError("Disk full")
        
    monkeypatch.setattr("_sys.core.layout_migration._atomic_write_json", mock_atomic_write)
    
    with pytest.raises(SystemExit) as excinfo:
        merge_declarations_impl(migration_env["defaults"], migration_env["live"], migration_env["base_state"], migration_env["manifest"], ["runtimes.json", "tool-catalog.v1.json"])
        
    assert excinfo.value.code == 1
    
    # Verify live file is intact
    with open(migration_env["live"] / "runtimes.json") as f:
        assert json.load(f) == ours_json

from _sys.core.layout_migration import m0_preflight, m1_retire_shipped_files

def test_m0_preflight_refusal(tmp_path, capsys):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    
    state_file = state_dir / "register.state.json"
    state_file.write_text(json.dumps({
        "subst_drive": "W",
        "junctions": [{"host": "C:\\some_host"}]
    }))
    
    # Snapshot before
    before = list(tmp_path.rglob("*"))
    
    assert not m0_preflight(base_dir, sys_dir)
    
    captured = capsys.readouterr().out
    assert "subst W: /D" in captured
    assert "rmdir \"C:\\some_host\"" in captured
    assert "Delete 'subst_drive' and 'junctions' entries from" in captured
    assert "register.state.json" in captured
    
    # Snapshot after
    after = list(tmp_path.rglob("*"))
    assert before == after

def test_m0_preflight_clean(tmp_path, capsys):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    # absent state file -> proceeds
    assert m0_preflight(base_dir, sys_dir)
    
    # clean state file
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "register.state.json"
    state_file.write_text(json.dumps({"subst_drive": None, "junctions": []}))
    
    assert m0_preflight(base_dir, sys_dir)

def test_m1_retire_identical_file(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    content = b"old file content"
    sha = hashlib.sha256(content).hexdigest().upper()
    
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": {"foo/bar.txt": sha}
    }))
    
    # layout file pointing to 3.2.6
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "layout.json").write_text(json.dumps({"engram_version": "3.2.6"}))
    
    target_dir = base_dir / "foo"
    target_dir.mkdir()
    target_file = target_dir / "bar.txt"
    target_file.write_bytes(content)
    
    ok, report = m1_retire_shipped_files(base_dir, sys_dir)
    assert ok
    assert report["retired"] == ["foo/bar.txt"]
    assert report["kept_modified"] == []
    
    assert not target_file.exists()
    assert not target_dir.exists()

def test_m1_retire_modified_file(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    content = b"old file content"
    sha = hashlib.sha256(content).hexdigest().upper()
    
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": {"foo/modified.txt": sha}
    }))
    
    target_dir = base_dir / "foo"
    target_dir.mkdir()
    target_file = target_dir / "modified.txt"
    target_file.write_bytes(b"modified content")
    
    ok, report = m1_retire_shipped_files(base_dir, sys_dir)
    assert ok
    assert report["retired"] == []
    assert report["kept_modified"] == ["foo/modified.txt"]
    
    assert target_file.exists()

def test_m1_retire_no_current_manifest(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    
    ok, report = m1_retire_shipped_files(base_dir, sys_dir)
    assert ok
    assert report["retired"] == []
    assert report["kept_modified"] == []

def test_m1_retire_protected_paths(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    content = b"protected"
    sha = hashlib.sha256(content).hexdigest().upper()
    
    protected_files = [
        "_sys/runtimes.json",
        "_sys/tool-catalog.v1.json",
        ".engram/foo",
        "workspace/bar",
        "_sys/env/baz",
        "_sys/tools/qux",
        "_sys/data/state"
    ]
    
    files_map = {p: sha for p in protected_files}
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": files_map
    }))
    
    for p in protected_files:
        f = base_dir / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)
        
    ok, report = m1_retire_shipped_files(base_dir, sys_dir)
    assert ok
    assert report["retired"] == []
    assert report["kept_modified"] == []
    
    for p in protected_files:
        assert (base_dir / p).exists()

def test_m1_retire_empty_directory_removal(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    content = b"deep"
    sha = hashlib.sha256(content).hexdigest().upper()
    
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": {"deep/dir/structure/file.txt": sha}
    }))
    
    target_dir = base_dir / "deep" / "dir" / "structure"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "file.txt"
    target_file.write_bytes(content)
    
    ok, report = m1_retire_shipped_files(base_dir, sys_dir)
    assert ok
    assert report["retired"] == ["deep/dir/structure/file.txt"]
    
    assert not (base_dir / "deep" / "dir" / "structure").exists()
    assert not (base_dir / "deep" / "dir").exists()
    assert not (base_dir / "deep").exists()


from _sys.core.layout_migration import m2_move_engram_state

def test_m2_tttt_shaped(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    ai_dir = base_dir / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").write_text("{}")
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    assert report["moved"] == [".ai/tool_discovery_cache.json"]
    assert report["external_left"] == []
    assert report["conflicts"] == []
    
    assert not ai_dir.exists()
    assert (sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json").exists()

def test_m2_t2_shaped(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    assert report["moved"] == []
    assert report["external_left"] == []
    assert report["conflicts"] == []

def test_m2_mixed_ai(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    ai_dir = base_dir / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").write_text("{}")
    (ai_dir / "some_other_hub_state.json").write_text("{}")
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    assert report["moved"] == [".ai/tool_discovery_cache.json"]
    assert report["external_left"] == [".ai/some_other_hub_state.json"]
    assert report["conflicts"] == []
    
    assert ai_dir.exists()
    assert (ai_dir / "some_other_hub_state.json").exists()
    assert not (ai_dir / "tool_discovery_cache.json").exists()
    assert (sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json").exists()

def test_m2_archive_both(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    archive_dir = base_dir / "_archive"
    logs_dir = archive_dir / "logs"
    updates_dir = archive_dir / "tool-updates"
    
    logs_dir.mkdir(parents=True)
    updates_dir.mkdir(parents=True)
    
    (logs_dir / "start_20260101.log").write_text("log")
    
    update_sub = updates_dir / "2026-01-01"
    update_sub.mkdir()
    (update_sub / "proposal.json").write_text("{}")
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    
    assert set(report["moved"]) == {
        "_archive/logs/start_20260101.log",
        "_archive/tool-updates/2026-01-01/proposal.json"
    }
    assert report["external_left"] == []
    assert report["conflicts"] == []
    
    assert not archive_dir.exists()
    assert (sys_dir / "data" / "logs" / "launcher" / "start_20260101.log").exists()
    assert (sys_dir / "data" / "state" / "update" / "proposals" / "2026-01-01" / "proposal.json").exists()

def test_m2_destination_conflict(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    ai_dir = base_dir / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").write_text("src")
    
    dst = sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json"
    dst.parent.mkdir(parents=True)
    dst.write_text("dst")
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    assert report["moved"] == []
    assert report["external_left"] == []
    assert report["conflicts"] == [".ai/tool_discovery_cache.json"]
    
    assert ai_dir.exists()
    assert (ai_dir / "tool_discovery_cache.json").read_text() == "src"
    assert dst.read_text() == "dst"

def test_m2_untouched_dirs(tmp_path):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    engram_dir = base_dir / ".engram"
    engram_dir.mkdir()
    (engram_dir / "some_file").write_text("keep")
    
    workspace_dir = base_dir / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "project").write_text("keep2")
    
    archive_dir = base_dir / "_archive"
    archive_dir.mkdir()
    (archive_dir / "keep3").write_text("keep3")
    
    import hashlib
    def get_snapshot():
        snap = {}
        for p in base_dir.rglob("*"):
            if p.is_file():
                snap[p.relative_to(base_dir).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return snap
        
    before = get_snapshot()
    
    ok, report = m2_move_engram_state(base_dir, sys_dir)
    assert ok
    
    assert report["moved"] == []
    assert report["external_left"] == ["_archive/keep3"]
    assert report["conflicts"] == []
    
    after = get_snapshot()
    assert before == after
from _sys.core.layout_migration import migrate_layout

def test_migrate_layout_m0_refusal(tmp_path, capsys):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "register.state.json"
    state_file.write_text(json.dumps({
        "subst_drive": "W",
        "junctions": [{"host": "C:\\some_host"}]
    }))
    
    import hashlib
    def get_snapshot():
        snap = {}
        for p in base_dir.rglob("*"):
            if p.is_file():
                snap[p.relative_to(base_dir).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return snap
        
    before = get_snapshot()
    
    result = migrate_layout(base_dir, sys_dir)
    assert result == 1
    
    after = get_snapshot()
    assert before == after
    
    captured = capsys.readouterr().out
    assert "subst W: /D" in captured
    assert "Layout Migration Summary" not in captured

def test_migrate_layout_success_and_idempotency(tmp_path, capsys, monkeypatch):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    monkeypatch.chdir(base_dir)
    
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    retirable_content = b"old file content"
    sha = hashlib.sha256(retirable_content).hexdigest().upper()
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": {"foo/bar.txt": sha}
    }))
    
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "layout.json").write_text(json.dumps({"engram_version": "3.2.6"}))
    
    target_dir = base_dir / "foo"
    target_dir.mkdir()
    target_file = target_dir / "bar.txt"
    target_file.write_bytes(retirable_content)
    
    ai_dir = base_dir / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").write_text("{}")
    
    defaults_dir = sys_dir / "defaults"
    defaults_dir.mkdir(parents=True)
    
    # No base_state exists yet, so ours != base: the merge keeps ours and
    # reports it, exercising the "merged" report path.
    with open(sys_dir / "runtimes.json", "w") as f:
        json.dump({"runtimes": {"python": {"version": "3.13"}}}, f)
        
    with open(defaults_dir / "runtimes.json", "w") as f:
        json.dump({"runtimes": {"python": {"version": "3.14"}}}, f)
        
    with open(sys_dir / "tool-catalog.v1.json", "w") as f:
        json.dump({"tools": []}, f)
        
    with open(defaults_dir / "tool-catalog.v1.json", "w") as f:
        json.dump({"tools": []}, f)
        
    result = migrate_layout(base_dir, sys_dir)
    assert result == 0
    
    layout_data = json.loads((state_dir / "layout.json").read_text())
    assert layout_data["layout_version"] == 2
    assert layout_data["report"]["retired"] == ["foo/bar.txt"]
    assert layout_data["report"]["moved"] == [".ai/tool_discovery_cache.json"]
    assert len(layout_data["report"]["merged"]) > 0
    
    assert not target_file.exists()
    assert not ai_dir.exists()
    
    with open(sys_dir / "runtimes.json") as f:
        merged_runtimes = json.load(f)
    assert merged_runtimes["runtimes"]["python"]["version"] == "3.13"
    
    def get_snapshot():
        snap = {}
        for p in base_dir.rglob("*"):
            if p.is_file() and not p.name.endswith(".bak"):
                snap[p.relative_to(base_dir).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return snap
        
    end_of_run_1_snap = get_snapshot()
    
    result2 = migrate_layout(base_dir, sys_dir)
    assert result2 == 0
    
    layout_data2 = json.loads((state_dir / "layout.json").read_text())
    assert layout_data2["report"]["retired"] == []
    assert layout_data2["report"]["moved"] == []
    
    end_of_run_2_snap = get_snapshot()
    del end_of_run_1_snap["_sys/data/state/layout.json"]
    del end_of_run_2_snap["_sys/data/state/layout.json"]
    
    assert end_of_run_1_snap == end_of_run_2_snap


def test_migrate_layout_dry_run(tmp_path, capsys, monkeypatch):
    base_dir = tmp_path
    sys_dir = base_dir / "_sys"
    sys_dir.mkdir()
    
    monkeypatch.chdir(base_dir)
    
    core_dir = sys_dir / "core"
    core_dir.mkdir(parents=True)
    manifest_dir = core_dir / "release-manifests"
    manifest_dir.mkdir(parents=True)
    
    current = core_dir / "release-manifest.json"
    current.write_text(json.dumps({"files": {}}))
    
    import hashlib
    retirable_content = b"old file content"
    sha = hashlib.sha256(retirable_content).hexdigest().upper()
    old_manifest = manifest_dir / "3.2.6.json"
    old_manifest.write_text(json.dumps({
        "version": "3.2.6",
        "files": {"foo/bar.txt": sha}
    }))
    
    state_dir = sys_dir / "data" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "layout.json").write_text(json.dumps({"engram_version": "3.2.6"}))
    
    target_dir = base_dir / "foo"
    target_dir.mkdir()
    target_file = target_dir / "bar.txt"
    target_file.write_bytes(retirable_content)
    
    ai_dir = base_dir / ".ai"
    ai_dir.mkdir()
    (ai_dir / "tool_discovery_cache.json").write_text("{}")
    
    defaults_dir = sys_dir / "defaults"
    defaults_dir.mkdir(parents=True)
    
    with open(sys_dir / "runtimes.json", "w") as f:
        json.dump({"runtimes": {"python": {"version": "3.13"}}}, f)
        
    with open(defaults_dir / "runtimes.json", "w") as f:
        json.dump({"runtimes": {"python": {"version": "3.14"}}}, f)
        
    with open(sys_dir / "tool-catalog.v1.json", "w") as f:
        json.dump({"tools": []}, f)
        
    with open(defaults_dir / "tool-catalog.v1.json", "w") as f:
        json.dump({"tools": []}, f)
    
    def get_snapshot():
        snap = {}
        for p in base_dir.rglob("*"):
            if p.is_file():
                snap[p.relative_to(base_dir).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return snap
        
    before = get_snapshot()
    
    result = migrate_layout(base_dir, sys_dir, dry_run=True)
    assert result == 0
    
    after = get_snapshot()
    assert before == after
    
    layout_data = json.loads((state_dir / "layout.json").read_text())
    assert "layout_version" not in layout_data
    
    captured = capsys.readouterr().out
    assert "[DRY RUN]" in captured
    assert "Retired shipped files: 1" in captured
    assert "Moved engram state files: 1" in captured
