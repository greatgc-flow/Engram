"""Tests for T12/T13 hardcoding-audit fixes (2026-07-09)."""
import importlib.util
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


SYS_DIR = Path(__file__).resolve().parents[2]
CHECKS_DIR = SYS_DIR / "checks"
CLI_DIR = SYS_DIR / "cli"
sys.path.insert(0, str(CHECKS_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_saturation_default_root_is_sys(monkeypatch):
    module = _load("saturation_t12", CHECKS_DIR / "saturation_scan.py")
    seen = []

    monkeypatch.setattr(module, "_read_commit_count", lambda root: 0)
    monkeypatch.setattr(module, "scan_lines", lambda root: seen.append(root) or [])
    monkeypatch.setattr(module.sys, "argv", [
        "saturation_scan.py", "--force", "--checks", "lines",
    ])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert exc.value.code == 0
    assert seen == [SYS_DIR]


