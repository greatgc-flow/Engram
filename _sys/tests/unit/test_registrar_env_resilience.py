"""registrar: read-only stale scan + real logical/physical root recording
(design section 3 / P0: "registrar records real logical/physical roots").
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from _sys.core.root import find_root

_sys_path = find_root(__file__)
if str(_sys_path) not in sys.path:
    sys.path.insert(0, str(_sys_path))

from core import registrar  # noqa: E402

CTX_MENU = {
    "win11_classic_menu": False,
    "registry": {"targets": {"Directory": {"path": r"Software\Classes\Directory\shell", "arg": "%V"}}},
    "entries": [],
}


def _enum_key_stub(names):
    def _enum(_key, index):
        try:
            return names[index]
        except IndexError:
            raise OSError("no more items")
    return _enum


def _open_key():
    m = MagicMock()
    m.return_value.__enter__.return_value = MagicMock()
    m.return_value.__exit__.return_value = False
    return m


def _sys_with_menu(tmp_path):
    sys_dir = tmp_path / "install" / "_sys"
    sys_dir.mkdir(parents=True)
    (sys_dir / "context_menu.json").write_text(json.dumps(CTX_MENU), encoding="utf-8")
    return sys_dir


def test_find_stale_entries_lists_without_deleting_or_printing(tmp_path, capsys):
    sys_dir = _sys_with_menu(tmp_path)
    local = tmp_path / "local"
    local.mkdir()
    key = "SandboxRun_D_ghost"
    ghost = tmp_path / "gone"
    (local / f"{key}.bat").write_text("@echo off", encoding="utf-8")
    (local / f"{key}.physroot.txt").write_bytes(str(ghost).encode("mbcs"))

    with patch("winreg.OpenKey", _open_key()), \
         patch("winreg.EnumKey", side_effect=_enum_key_stub([key])), \
         patch("subprocess.run") as run:
        stale = registrar.find_stale_entries(sys_dir, relay_root=local)

    assert stale == [key]
    run.assert_not_called()                      # no `reg delete`
    assert (local / f"{key}.bat").exists()       # sidecars untouched
    assert (local / f"{key}.physroot.txt").exists()
    assert capsys.readouterr().out == ""         # doctor JSON output must stay clean


def test_find_stale_entries_ignores_live_install(tmp_path):
    sys_dir = _sys_with_menu(tmp_path)
    local = tmp_path / "local"
    local.mkdir()
    key = "SandboxRun_D_live"
    live = tmp_path / "live_root"
    live.mkdir()
    (local / f"{key}.bat").write_text("@echo off", encoding="utf-8")
    (local / f"{key}.physroot.txt").write_bytes(str(live).encode("mbcs"))
    with patch("winreg.OpenKey", _open_key()), \
         patch("winreg.EnumKey", side_effect=_enum_key_stub([key])):
        assert registrar.find_stale_entries(sys_dir, relay_root=local) == []


def test_find_stale_entries_without_context_menu_config_is_empty(tmp_path):
    sys_dir = tmp_path / "install" / "_sys"
    sys_dir.mkdir(parents=True)
    assert registrar.find_stale_entries(sys_dir, relay_root=tmp_path) == []


def test_clean_orphans_dry_run_does_not_claim_removal(tmp_path, capsys):
    local = tmp_path / "local"
    local.mkdir()
    key = "SandboxRun_D_ghost"
    (local / f"{key}.bat").write_text("@echo off", encoding="utf-8")
    (local / f"{key}.physroot.txt").write_bytes(str(tmp_path / "gone").encode("mbcs"))
    with patch("winreg.OpenKey", _open_key()), \
         patch("winreg.EnumKey", side_effect=_enum_key_stub([key])), \
         patch("subprocess.run") as run:
        found = registrar._clean_orphans("x", CTX_MENU["registry"]["targets"], local, dry_run=True)
    assert found == [key]
    run.assert_not_called()
    assert "Orphan removed" not in capsys.readouterr().out


# ---- real logical / physical root recording --------------------------------------------

def test_physical_root_resolves_aliases(monkeypatch):
    monkeypatch.setattr(registrar.os.path, "realpath", lambda p: r"D:\Real\Engram")
    logical, physical = registrar._root_pair(Path(r"P:\Engram"))
    assert logical == r"P:\Engram" and physical == r"D:\Real\Engram"


def test_physical_root_falls_back_to_logical_on_error(monkeypatch):
    def boom(p):
        raise OSError("cannot resolve")
    monkeypatch.setattr(registrar.os.path, "realpath", boom)
    logical, physical = registrar._root_pair(Path(r"P:\Engram"))
    assert physical == logical == r"P:\Engram"


def test_apply_passes_distinct_root_and_physroot(tmp_path, monkeypatch):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    cfg = dict(CTX_MENU)
    cfg["entries"] = [{"id": "engram_open", "label": "Open", "targets": ["Directory"]}]
    (sys_dir / "context_menu.json").write_text(json.dumps(cfg), encoding="utf-8")
    real = str(tmp_path / "real_location")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(registrar.os.path, "realpath", lambda p: real if str(p) == str(base) else str(p))
    seen = {}

    def fake_register(entry, cfg_, base_key, relay_root, paths, root, phys_root, drive, folder=""):
        seen["root"], seen["phys_root"] = root, phys_root
        return {"key_name": "k", "relay": "r", "reg_keys": []}

    ctx = {"base_dir": base, "sys_dir": sys_dir, "paths": {"state": sys_dir / "data" / "state"},
           "state": {}, "command": "register", "args": []}
    with patch.object(registrar, "_register_entry", fake_register),          patch.object(registrar, "_clean_orphans", lambda *a, **k: []),          patch.object(registrar, "winreg", MagicMock()),          patch("subprocess.run", return_value=MagicMock(returncode=0)):
        registrar.apply(ctx)
    assert seen["root"] == str(base)
    assert seen["phys_root"] == real


def test_register_entry_writes_both_sidecars(tmp_path):
    local = tmp_path / "local"
    local.mkdir()
    cfg = dict(CTX_MENU)
    cfg["relay"] = {"content_template": "@echo off\nrem {root_file} {physroot_file}\n"}
    entry = {"id": "engram_open", "label": "Open", "targets": ["Directory"]}
    with patch.object(registrar, "winreg", MagicMock()), patch("subprocess.run", return_value=MagicMock(returncode=0)):
        registrar._register_entry(entry, cfg, "SandboxRun_x", local, {"env": tmp_path}, str(tmp_path / "logical"),
                                  str(tmp_path / "physical"), "D", "folder")
    assert (local / "SandboxRun_x_engram_open.root.txt").read_bytes().decode("mbcs") == str(tmp_path / "logical")
    assert (local / "SandboxRun_x_engram_open.physroot.txt").read_bytes().decode("mbcs") == str(tmp_path / "physical")
