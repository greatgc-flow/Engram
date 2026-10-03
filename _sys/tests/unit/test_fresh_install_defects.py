"""Regression tests for defects found by a real fresh-install E2E run."""
import re
import sys
import types
from pathlib import Path

import pytest

from _sys.core.root import find_root

SYS = find_root(__file__)
sys.path.insert(0, str(SYS))
from core import backups, dispatcher, tidy_temp  # noqa: E402

REAL_WORKTREE = SYS.parent.resolve()


def _bat_files():
    out = []
    for p in REAL_WORKTREE.rglob("*"):
        if p.suffix.lower() in (".bat", ".cmd") and not {"env", "node_modules", ".git"} & set(p.parts):
            out.append(p)
    return out


def test_no_double_colon_comment_hazard_inside_paren_blocks():
    """`::` inside a (...) block is parsed as a label/drive command; a `)` followed by `:` ends the
    block early and runs a drive command. Inside blocks, comments must not contain `)` or `(`."""
    bad = []
    for p in _bat_files():
        depth = 0
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            s = line.strip()
            if s.startswith("::"):
                if depth > 0 and ("(" in s or ")" in s):
                    bad.append(f"{p.name}:{n}: {s[:60]}")
                continue
            if s.lower().startswith("rem "):
                continue
            body = re.sub(r'"[^"]*"|\^[()]|%[^%]*%|![^!]*!', "", s)
            depth = max(0, depth + body.count("(") - body.count(")"))
    assert not bad, "\n".join(bad)


def test_dispatcher_usage_failure_has_no_traceback(monkeypatch, capsys):
    mod = types.ModuleType("usage_mod")
    mod.run = lambda ctx: {"status": "failed", "operation": "repair", "detail": "usage", "exit_code": 2}
    monkeypatch.setitem(sys.modules, "usage_mod", mod)
    cfg = {"pipelines": {"repair": ["repair.run"]},
           "operations": {"repair.run": {"module": "usage_mod", "method": "run", "failure_policy": "abort"}}}
    monkeypatch.setattr(dispatcher, "_load_json", lambda path: cfg)
    monkeypatch.setattr(dispatcher, "_build_ctx", lambda *a: {})
    monkeypatch.setattr(Path, "exists", lambda self: True)
    assert dispatcher.main(["dispatcher.py", "repair", "--dry-run"]) == 2
    out = capsys.readouterr().out
    assert "RuntimeError" not in out and "Traceback" not in out


def test_tidy_never_plans_backup_payloads(tmp_path):
    base = tmp_path / "Engram"
    sys_dir = base / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    (sys_dir / "env").mkdir(parents=True)
    tidy_temp.configure_paths(root=base, sys_dir=sys_dir, explicit_sys_dir=True)
    try:
        src = tmp_path / "src"
        (src / "__pycache__").mkdir(parents=True)
        (src / "__pycache__" / "a.pyc").write_bytes(b"x")
        ref = backups.create(sys_dir, "venv", src, reason="t", op_id="op", label="l",
                             now="2026-10-01T00:00:00Z")
        backups.commit(ref, now="2026-10-01T00:00:00Z")
        root = backups.backups_root(sys_dir).resolve()
        assert list(root.rglob("__pycache__"))
        for label, key, items in tidy_temp.build_plan(now=1.0):
            if key == "backups":
                continue
            for it in items:
                assert root not in Path(it).resolve().parents and Path(it).resolve() != root, (label, it)
    finally:
        tidy_temp.configure_paths(root=REAL_WORKTREE, sys_dir=SYS, explicit_sys_dir=False)


def test_core_subprocess_text_decoding_never_uses_locale():
    bad = []
    for p in (SYS / "core").glob("*.py"):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "text=True" in line and "mkstemp" not in line:
                bad.append(f"{p.name}:{n}")
    assert not bad, bad
