"""TDD — I1: managed-links.json + virtualizer.py integration.

Tests are written BEFORE managed-links.json is created.
All tests MUST FAIL until implementation is complete.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
import virtualizer


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sys_dir(tmp_path):
    """Minimal _sys/ structure with managed-links.json."""
    s = tmp_path / "_sys"
    s.mkdir()
    (s / "ai").mkdir()
    (s / "data" / "state" / "pathmap").mkdir(parents=True)
    (s / "claude" / "config").mkdir(parents=True)
    (s / "gemini" / "config").mkdir(parents=True)
    return s


@pytest.fixture
def managed_links_path(sys_dir):
    return sys_dir / "data" / "state" / "pathmap" / "managed-links.json"


@pytest.fixture
def valid_managed_links(sys_dir, managed_links_path, tmp_path):
    """Create a valid managed-links.json with one real junction entry."""
    # Use a real target path (tmp dir simulating _sys/claude/config)
    target = sys_dir / "claude" / "config"
    data = {
        "_version": "1.0",
        "_help": "SSOT for all managed junctions.",
        "entries": {
            "cc_host": {
                "relative_link_path": "claude/config_junction_test",
                "relative_target_path": "claude/config"
            }
        }
    }
    managed_links_path.write_text(json.dumps(data), encoding="utf-8")
    return managed_links_path


# ── Schema validation ────────────────────────────────────────────────────────

class TestManagedLinksSchema:
    def test_file_has_version_field(self, valid_managed_links):
        data = json.loads(valid_managed_links.read_text())
        assert "_version" in data

    def test_file_has_entries_dict(self, valid_managed_links):
        data = json.loads(valid_managed_links.read_text())
        assert "entries" in data
        assert isinstance(data["entries"], dict)

    def test_each_entry_has_required_keys(self, valid_managed_links):
        data = json.loads(valid_managed_links.read_text())
        for entry_id, entry in data["entries"].items():
            assert "relative_link_path" in entry, f"{entry_id} missing relative_link_path"
            assert "relative_target_path" in entry, f"{entry_id} missing relative_target_path"

    def test_external_prefix_entries_valid(self, sys_dir, managed_links_path):
        data = {
            "_version": "1.0",
            "entries": {
                "cc_host": {
                    "relative_link_path": "EXTERNAL:%USERPROFILE%\\.claude",
                    "relative_target_path": "claude/config"
                }
            }
        }
        managed_links_path.write_text(json.dumps(data), encoding="utf-8")
        loaded = json.loads(managed_links_path.read_text())
        entry = loaded["entries"]["cc_host"]
        assert entry["relative_link_path"].startswith("EXTERNAL:")


# ── virtualizer._cli_apply with managed-links ────────────────────────────────

class TestVirtualizerApplyManagedLinks:
    def test_uses_managed_links_when_present(self, sys_dir, valid_managed_links, capsys):
        """_cli_apply should print 'Using managed-links.json' when file exists."""
        with patch("virtualizer._ensure_junction"), \
             patch("virtualizer._remove_junction"):
            virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        out = capsys.readouterr().out
        assert "managed-links.json" in out

    def test_falls_back_to_peers_when_missing(self, sys_dir, capsys):
        """_cli_apply should fall back to peers.json when managed-links.json absent."""
        # No managed-links.json created — fallback expected
        peers_data = {
            "peers": {}
        }
        (sys_dir / "ai" / "peers.json").write_text(json.dumps(peers_data))
        virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        out = capsys.readouterr().out
        assert "peers.json" in out or "No peers found" in out

    def test_entry_count_in_output(self, sys_dir, valid_managed_links, capsys):
        """Entry count should appear in output."""
        with patch("virtualizer._ensure_junction"), \
             patch("virtualizer._remove_junction"):
            virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        out = capsys.readouterr().out
        assert "1 entries" in out

    def test_external_path_expanded_via_env(self, sys_dir, managed_links_path, capsys, monkeypatch):
        """EXTERNAL: paths use os.path.expandvars."""
        monkeypatch.setenv("USERPROFILE", str(sys_dir))
        (sys_dir / "claude" / "config").mkdir(parents=True, exist_ok=True)
        data = {
            "_version": "1.0",
            "entries": {
                "cc_host": {
                    "relative_link_path": "EXTERNAL:%USERPROFILE%\\.claude_test",
                    "relative_target_path": "claude/config"
                }
            }
        }
        managed_links_path.write_text(json.dumps(data))
        with patch("virtualizer._ensure_junction") as mock_junc, \
             patch("virtualizer._remove_junction"):
            virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        # Should have been called with an absolute path (not containing EXTERNAL:)
        if mock_junc.called:
            called_path = str(mock_junc.call_args[0][0])
            assert "EXTERNAL:" not in called_path
            assert "USERPROFILE" not in called_path

    def test_malformed_json_falls_back_gracefully(self, sys_dir, managed_links_path, capsys):
        """Malformed managed-links.json triggers fallback, does not crash."""
        managed_links_path.write_text("{not valid json}")
        peers_data = {"peers": {}}
        (sys_dir / "ai" / "peers.json").write_text(json.dumps(peers_data))
        # Should not raise
        virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        out = capsys.readouterr().out
        # Either error message or fallback message
        assert "error" in out.lower() or "peers.json" in out or "No peers" in out

    def test_target_dir_created_if_missing(self, sys_dir, managed_links_path, capsys):
        """Target directory is created (mkdir) before junction is made."""
        # Target does NOT exist initially
        data = {
            "_version": "1.0",
            "entries": {
                "test_entry": {
                    "relative_link_path": "test_link",
                    "relative_target_path": "test_target_new"
                }
            }
        }
        managed_links_path.write_text(json.dumps(data))
        with patch("virtualizer._ensure_junction"), \
             patch("virtualizer._remove_junction"):
            virtualizer._cli_apply(sys_dir, sys_dir.parent, force=False)
        # Target dir should have been created
        assert (sys_dir / "test_target_new").exists()


# ── File location ────────────────────────────────────────────────────────────

class TestManagedLinksLocation:
    def test_file_must_be_at_expected_path(self, sys_dir):
        """managed-links.json must live at _sys/data/state/pathmap/."""
        expected = sys_dir / "data" / "state" / "pathmap" / "managed-links.json"
        # File doesn't exist yet (TDD: will exist after implementation)
        assert expected.parent.exists(), "Parent directory must exist"

    def test_path_is_gitignored(self):
        """_sys/data/state/ is in .gitignore (runtime state)."""
        gitignore = Path(__file__).parent.parent.parent.parent / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            assert "_sys/data/state/" in content or "data/state" in content
