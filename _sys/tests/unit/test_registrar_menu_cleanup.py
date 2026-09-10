"""
registrar.clean_orphans() -- standalone on-demand context-menu orphan sweep.

Covers the `engram menu-cleanup` command (registrar.py's public clean_orphans()
wrapper around the existing _clean_orphans() machinery that apply()/remove()
already run as a side effect). This is deliberately a separate test file: no
prior test exercised _clean_orphans()'s actual scan/removal logic -- every
existing call site (test_path_scenarios.py, test_system_lifecycle.py) mocks
_clean_orphans() itself out entirely, since apply()/remove() tests only care
about their own registration/teardown behavior, not the sweep.
"""
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

_sys_path = Path(__file__).parent.parent.parent  # _sys/
if str(_sys_path) not in sys.path:
    sys.path.insert(0, str(_sys_path))

from core import registrar  # noqa: E402


def _make_ctx(base_dir: Path) -> dict:
    return {
        "base_dir": base_dir,
        "sys_dir":  base_dir / "_sys",
        "paths":    {},
        "args":     [],
        "state":    {},
    }


_DEFAULT_CTX_MENU = {
    "win11_classic_menu": False,
    "registry": {
        "targets": {
            "Directory": {"path": r"Software\Classes\Directory\shell", "arg": "%V"},
        }
    },
    "entries": [],
}


def _write_ctx_menu(sys_dir: Path, cfg: dict = _DEFAULT_CTX_MENU) -> None:
    sys_dir.mkdir(parents=True, exist_ok=True)
    (sys_dir / "context_menu.json").write_text(json.dumps(cfg), encoding="utf-8")


def _enum_key_stub(names):
    """winreg.EnumKey(key, index) stand-in: returns names[index], then OSError."""
    def _enum(_key, index):
        try:
            return names[index]
        except IndexError:
            raise OSError("no more items")
    return _enum


def _mock_open_key(handle=None):
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value = handle if handle is not None else MagicMock()
    mock_open.return_value.__exit__.return_value = False
    return mock_open


class TestRegistrarMenuCleanup:

    def test_orphaned_entry_removed_and_counted(self, tmp_path):
        """(a) An entry whose recorded physical root no longer exists on disk
        is removed from the registry and its 4 sidecar files, and counted."""
        base_dir  = tmp_path / "install"
        local_dir = tmp_path / "_local"
        local_dir.mkdir()
        _write_ctx_menu(base_dir / "_sys")

        key_name  = "SandboxRun_D_ghost"
        ghost_root = tmp_path / "deleted_folder_that_never_existed"
        (local_dir / f"{key_name}.bat").write_text("@echo off", encoding="utf-8")
        (local_dir / f"{key_name}.physroot.txt").write_bytes(str(ghost_root).encode("mbcs"))
        (local_dir / f"{key_name}.root.txt").write_bytes(str(ghost_root).encode("mbcs"))

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.OpenKey", _mock_open_key()), \
             patch("winreg.EnumKey", side_effect=_enum_key_stub([key_name])), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == [key_name]
        assert not (local_dir / f"{key_name}.bat").exists()
        assert not (local_dir / f"{key_name}.physroot.txt").exists()
        assert not (local_dir / f"{key_name}.root.txt").exists()

        deleted = [
            c.args[0] for c in mock_run.call_args_list
            if c.args and isinstance(c.args[0], list) and "delete" in c.args[0]
        ]
        assert any(key_name in " ".join(cmd) for cmd in deleted), \
            f"expected a 'reg delete' call naming {key_name}, got: {mock_run.call_args_list}"

    def test_orphan_registered_under_multiple_targets_counted_once(self, tmp_path):
        """An entry registered under several registry targets (the shipped
        context_menu.json ships 5: Directory/Background, Directory, Drive,
        *, lnkfile) shares one relay/sidecar set but has one registry key
        per target. A real 'reg delete' must fire for every target, but the
        reported 'removed' count must reflect one stale ENTRY, not one row
        per target -- see _clean_orphans()'s dedup docstring."""
        base_dir  = tmp_path / "install"
        local_dir = tmp_path / "_local"
        local_dir.mkdir()
        multi_target_cfg = {
            "win11_classic_menu": False,
            "registry": {
                "targets": {
                    "Directory/Background": {"path": r"Software\Classes\Directory\Background\shell", "arg": "%V"},
                    "Directory":            {"path": r"Software\Classes\Directory\shell",             "arg": "%V"},
                    "Drive":                {"path": r"Software\Classes\Drive\shell",                 "arg": "%1"},
                }
            },
            "entries": [],
        }
        _write_ctx_menu(base_dir / "_sys", cfg=multi_target_cfg)

        key_name   = "SandboxRun_D_ghost_multi"
        ghost_root = tmp_path / "gone"
        (local_dir / f"{key_name}.bat").write_text("@echo off", encoding="utf-8")
        (local_dir / f"{key_name}.physroot.txt").write_bytes(str(ghost_root).encode("mbcs"))
        (local_dir / f"{key_name}.root.txt").write_bytes(str(ghost_root).encode("mbcs"))

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.OpenKey", _mock_open_key()), \
             patch("winreg.EnumKey", side_effect=_enum_key_stub([key_name])), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == [key_name], \
            f"expected exactly one de-duplicated entry, got: {result['removed']}"

        delete_calls = [
            c.args[0] for c in mock_run.call_args_list
            if c.args and isinstance(c.args[0], list) and "delete" in c.args[0]
        ]
        assert len(delete_calls) == 3, \
            f"expected one 'reg delete' per target (3), got {len(delete_calls)}: {delete_calls}"

    def test_live_entry_left_untouched(self, tmp_path):
        """(b) An entry whose recorded physical root still exists must survive
        the sweep completely untouched: not counted, no files removed, no
        registry delete attempted."""
        base_dir  = tmp_path / "install"
        local_dir = tmp_path / "_local"
        local_dir.mkdir()
        _write_ctx_menu(base_dir / "_sys")

        alive_root = tmp_path / "still_here"
        alive_root.mkdir()

        key_name = "SandboxRun_D_alive"
        (local_dir / f"{key_name}.bat").write_text("@echo off", encoding="utf-8")
        (local_dir / f"{key_name}.physroot.txt").write_bytes(str(alive_root).encode("mbcs"))
        (local_dir / f"{key_name}.root.txt").write_bytes(str(alive_root).encode("mbcs"))

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.OpenKey", _mock_open_key()), \
             patch("winreg.EnumKey", side_effect=_enum_key_stub([key_name])), \
             patch("subprocess.run") as mock_run:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == []
        assert (local_dir / f"{key_name}.bat").exists()
        assert (local_dir / f"{key_name}.physroot.txt").exists()
        assert (local_dir / f"{key_name}.root.txt").exists()
        mock_run.assert_not_called()

    def test_works_with_zero_prior_state(self, tmp_path):
        """(c) The command must work with no register.state.json (or any state
        file) present anywhere, and must never create one -- it is standalone
        by design, not derived from a prior register/unregister run."""
        base_dir  = tmp_path / "install"
        local_dir = tmp_path / "_local"
        local_dir.mkdir()
        _write_ctx_menu(base_dir / "_sys")
        state_dir = tmp_path / "_state"  # deliberately never created

        ctx = _make_ctx(base_dir)
        ctx["paths"] = {"state": state_dir}

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.OpenKey", _mock_open_key()), \
             patch("winreg.EnumKey", side_effect=_enum_key_stub([])):
            result = registrar.clean_orphans(ctx)

        assert result["status"] == "success"
        assert result["removed"] == []
        assert not state_dir.exists(), "clean_orphans must never create the state directory"
        assert not (state_dir / "register.state.json").exists()

    def test_missing_context_menu_json_is_noop_not_crash(self, tmp_path):
        """(d) Missing context_menu.json is a valid no-op (same convention as
        apply()/remove(): 'empty/missing config is success, not failure'),
        never a crash -- and the registry is never even touched."""
        base_dir = tmp_path / "install"
        (base_dir / "_sys").mkdir(parents=True)
        # No context_menu.json written at all.

        with patch("winreg.OpenKey") as mock_open_key:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == []
        mock_open_key.assert_not_called()

    def test_empty_context_menu_json_is_noop_not_crash(self, tmp_path):
        """(d) An empty context_menu.json file (parses to {}) is likewise a
        valid no-op, not a crash."""
        base_dir = tmp_path / "install"
        sys_dir = base_dir / "_sys"
        sys_dir.mkdir(parents=True)
        (sys_dir / "context_menu.json").write_text("{}", encoding="utf-8")

        with patch("winreg.OpenKey") as mock_open_key:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == []
        mock_open_key.assert_not_called()

    def test_no_registry_targets_configured_is_noop(self, tmp_path):
        """A context_menu.json with entries but zero registry targets is also
        a valid no-op: there is nothing to scan."""
        base_dir = tmp_path / "install"
        _write_ctx_menu(
            base_dir / "_sys",
            cfg={"win11_classic_menu": False, "registry": {"targets": {}}, "entries": []},
        )

        with patch("winreg.OpenKey") as mock_open_key:
            result = registrar.clean_orphans(_make_ctx(base_dir))

        assert result["status"] == "success"
        assert result["removed"] == []
        mock_open_key.assert_not_called()

    def test_missing_base_dir_does_not_crash(self, tmp_path):
        """clean_orphans() must not require a valid/registered install: even
        a ctx with no usable base_dir for key-name derivation still runs the
        (unscoped) sweep correctly, since the scan itself never actually
        filters by base_key -- see _clean_orphans()'s docstring."""
        local_dir = tmp_path / "_local"
        local_dir.mkdir()
        sys_dir = tmp_path / "somewhere" / "_sys"
        _write_ctx_menu(sys_dir)

        ctx = {"sys_dir": sys_dir, "base_dir": None, "paths": {}, "args": [], "state": {}}

        with patch.dict(os.environ, {"LOCALAPPDATA": str(local_dir)}), \
             patch("winreg.OpenKey", _mock_open_key()), \
             patch("winreg.EnumKey", side_effect=_enum_key_stub([])):
            result = registrar.clean_orphans(ctx)

        assert result["status"] == "success"
        assert result["removed"] == []
