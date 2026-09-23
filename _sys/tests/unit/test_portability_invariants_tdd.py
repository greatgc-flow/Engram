"""
TDD Tests for Zero-Host Portability Invariants & Full Lifecycle Scenarios.

Verifies:
1. VS Code portable mode:
   - data/ directory is created on fresh install
   - data/ directory and user extensions/settings are preserved across upgrades
   - launcher ensures data/ directory exists prior to executing Code.exe
2. Relocation & Drive Migration resilience:
   - Engram dynamically computes all environment variables relative to current base_dir
   - Zero hardcoded drive letters in runtime, tool, or dotdir paths
   - _relocate tracks current base_dir in last_base_dir.txt
3. Strict Zero-SUBST & Zero-Junction invariant:
   - Doctor never recommends mounting via SUBST
   - All paths resolved via physical paths and dynamic root detection
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)

from core import doctor, launcher, provisioner


class TestVSCodePortableMode:
    """VS Code Portable Mode Invariant: all extensions and user-data reside in _sys/env/vscode/data."""

    def test_vscode_install_creates_data_directory(self, monkeypatch, tmp_path):
        """Fresh install of VS Code must create data/ directory for portable mode."""
        sys_dir = tmp_path / "_sys"
        sys_dir.mkdir(parents=True)
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {
                "vscode": {
                    "version": "1.100.2",
                    "url": "https://example/vscode.zip",
                    "install_mechanism": "zip_tool",
                    "archive_layout": "preserve_tree",
                    "strip_components": 0,
                    "preserve_paths": ["data"],
                }
            },
            "tools": {},
        }), encoding="utf-8")

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("Code.exe", b"fake binary")
                zf.writestr("resources/app/package.json", b"{}")

        monkeypatch.setattr(provisioner, "_secure_download", fake_download)

        res = provisioner.ensure_runtime("vscode", sys_dir=sys_dir)
        assert res["status"] == "success"

        vscode_dir = sys_dir / "env" / "vscode"
        assert (vscode_dir / "Code.exe").exists()
        # Verify portable data/ directory exists immediately after install
        data_dir = vscode_dir / "data"
        assert data_dir.is_dir(), "VS Code portable mode requires data/ directory to exist upon install"

    def test_vscode_upgrade_preserves_data_directory(self, monkeypatch, tmp_path):
        """Upgrading VS Code must preserve existing data/ contents (user-data, extensions)."""
        sys_dir = tmp_path / "_sys"
        vscode_dir = sys_dir / "env" / "vscode"
        data_dir = vscode_dir / "data"
        user_data = data_dir / "user-data" / "User"
        user_data.mkdir(parents=True)
        settings_file = user_data / "settings.json"
        settings_file.write_text('{"editor.fontSize": 14}', encoding="utf-8")

        extensions_dir = data_dir / "extensions"
        extensions_dir.mkdir(parents=True)
        ext_file = extensions_dir / "test.ext"
        ext_file.write_text("ext_payload", encoding="utf-8")

        manifest_path = vscode_dir / ".install_manifest.json"
        manifest_path.write_text(json.dumps({
            "runtime": "vscode",
            "declared_version": "1.99.0",
            "source_config_hash": "old_hash",
        }), encoding="utf-8")

        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {
                "vscode": {
                    "version": "1.100.2",
                    "url": "https://example/vscode_new.zip",
                    "install_mechanism": "zip_tool",
                    "archive_layout": "preserve_tree",
                    "strip_components": 0,
                    "preserve_paths": ["data"],
                }
            },
            "tools": {},
        }), encoding="utf-8")

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("Code.exe", b"fake binary v2")

        monkeypatch.setattr(provisioner, "_secure_download", fake_download)

        # Force upgrade
        res = provisioner.ensure_runtime("vscode", sys_dir=sys_dir, force=True)
        assert res["status"] == "success"

        # Verify new binary
        assert (vscode_dir / "Code.exe").read_bytes() == b"fake binary v2"
        # Verify preserved data/ -- settings.json's own content is preserved
        # and merged (not replaced): seed_vscode_default_settings() adds
        # update.mode=none to an existing file that lacks it (2026-09-23 fix
        # for existing installs, not just fresh ones), so the original key
        # survives alongside the merged one rather than the file staying
        # byte-identical.
        settings = json.loads((user_data / "settings.json").read_text(encoding="utf-8"))
        assert settings == {"editor.fontSize": 14, "update.mode": "none"}
        assert (extensions_dir / "test.ext").read_text(encoding="utf-8") == "ext_payload"

    def test_launcher_creates_data_directory_if_missing(self, tmp_path, monkeypatch):
        """Launcher ensures data/ directory exists before launching VS Code."""
        base_dir = tmp_path / "Engram"
        sys_dir = base_dir / "_sys"
        vscode_dir = sys_dir / "env" / "vscode"
        vscode_dir.mkdir(parents=True)
        code_exe = vscode_dir / "Code.exe"
        code_exe.write_bytes(b"fake")

        (sys_dir / "env.json").write_text(json.dumps({
            "env_vars": {},
            "tool_env_vars": {},
            "path_entries": [],
        }), encoding="utf-8")

        popen_calls = []
        def mock_popen(args, env=None, **kw):
            popen_calls.append(args)
            proc = MagicMock()
            proc.poll.return_value = None
            return proc

        monkeypatch.setattr("subprocess.Popen", mock_popen)
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

        data_dir = vscode_dir / "data"
        assert not data_dir.exists()

        ctx = {
            "base_dir": base_dir,
            "sys_dir": sys_dir,
            "args": [],
        }
        launcher.main(ctx)

        assert data_dir.is_dir(), "launcher.main() must ensure data/ exists"
        assert any("Code.exe" in str(c[0]) for c in popen_calls)


class TestRelocationAndDriveMigration:
    """Drive Letter & Folder Migration: Engram must work when moved without hardcoded paths."""

    def test_dynamic_env_building_after_relocation(self, tmp_path):
        """Environment paths dynamically adapt to base_dir and sys_dir on any drive letter."""
        base_dir = tmp_path / "DriveE" / "EngramPortable"
        sys_dir = base_dir / "_sys"
        (base_dir / "workspace").mkdir(parents=True)
        sys_dir.mkdir(parents=True)

        (sys_dir / "env.json").write_text(json.dumps({
            "env_vars": {"ENGRAM_TEST": "1"},
            "tool_env_vars": {
                "PEERHUB_CONFIG_HOME": {"base": "engram", "sub": "peerhub"},
                "CLAUDE_CONFIG_DIR":   {"base": "engram", "sub": "claude"},
                "NPM_CONFIG_PREFIX":   {"base": "env",    "sub": "nodejs/npm-global"},
            },
            "path_entries": [
                {"base": "env", "sub": "nodejs"},
                {"base": "env", "sub": "nodejs/npm-global"},
            ],
        }), encoding="utf-8")

        env = launcher.build_env(base_dir, sys_dir)

        assert env["BASE_DIR"] == str(base_dir)
        assert env["SYS_DIR"] == str(sys_dir)
        assert env["PEERHUB_CONFIG_HOME"] == str(base_dir / ".engram" / "peerhub")
        assert env["CLAUDE_CONFIG_DIR"] == str(base_dir / ".engram" / "claude")
        assert env["NPM_CONFIG_PREFIX"] == str(sys_dir / "env" / "nodejs" / "npm-global")

        # Verify .engram subdirectories were automatically created
        assert (base_dir / ".engram" / "peerhub").is_dir()
        assert (base_dir / ".engram" / "claude").is_dir()

    def test_relocate_tracks_base_dir_change(self, tmp_path):
        """Moving Engram to a new location updates last_base_dir.txt correctly."""
        base_dir_1 = tmp_path / "LocationA"
        sys_dir_1 = base_dir_1 / "_sys"
        sys_dir_1.mkdir(parents=True)

        launcher._relocate(base_dir_1, sys_dir_1)
        record = (sys_dir_1 / "data" / "last_base_dir.txt").read_text(encoding="utf-8")
        assert record == str(base_dir_1)

        # Relocated to LocationB
        base_dir_2 = tmp_path / "LocationB"
        launcher._relocate(base_dir_2, sys_dir_1)
        record = (sys_dir_1 / "data" / "last_base_dir.txt").read_text(encoding="utf-8")
        assert record == str(base_dir_2)


class TestZeroHostInvariants:
    """Strict Invariant: No SUBST, no junctions, clean diagnostic reporting."""

    def test_doctor_root_path_never_mentions_subst(self):
        """doctor.check_root_path must never recommend SUBST to the user."""
        res = doctor.check_root_path(Path(r"D:\Engram&Peerhub\PortableDev"))
        assert res["level"] == "warning"
        assert "contains '&'" in res["detail"]
        assert "subst" not in res["detail"].lower(), "Doctor must never recommend mounting via SUBST"
        assert "clean path" in res["detail"].lower()

    def test_doctor_flags_legacy_subst_records(self, tmp_path):
        """Doctor actively flags legacy SUBST entries if they linger from old versions."""
        sys_dir = tmp_path / "_sys"
        state_dir = sys_dir / "data" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "register.state.json").write_text(json.dumps({"subst_drive": "P"}), encoding="utf-8")

        res = doctor.check_legacy_host_integration(tmp_path, sys_dir)
        assert res["level"] == "warning"
        assert "legacy host integration recorded" in res["detail"]
        assert "subst P: /D" in res["detail"]
