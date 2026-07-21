from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub  # noqa: E402


def _patch_feedback_path(monkeypatch, tmp_path):
    fb_path = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(hub, "_feedback_path", lambda ai_root: fb_path)
    monkeypatch.setattr(hub, "_get_lock", lambda ai_root, name: nullcontext())
    monkeypatch.setattr(hub, "_now", lambda: "2026-07-21T00:00:00")
    return fb_path


def test_feedback_add_skips_corrupted_line(tmp_path, monkeypatch):
    fb_path = _patch_feedback_path(monkeypatch, tmp_path)
    fb_path.write_text('not valid json\n{"id": "GAP-20260721-001"}\n', encoding="utf-8")

    hub.action_feedback_add(tmp_path, "cc", "bug", "warn", "title", "detail")

    # Did not crash, and the new entry's seq continued past the valid line.
    lines = fb_path.read_text(encoding="utf-8").splitlines()
    assert any('"GAP-20260721-002"' in line for line in lines)


def test_feedback_list_skips_corrupted_line(tmp_path, monkeypatch, capsys):
    fb_path = _patch_feedback_path(monkeypatch, tmp_path)
    fb_path.write_text('not valid json\n{"id": "GAP-1", "status": "open", "severity": "warn", "category": "bug", "title": "t"}\n', encoding="utf-8")

    hub.action_feedback_list(tmp_path)

    out = capsys.readouterr().out
    assert "GAP-1" in out


def test_feedback_resolve_skips_corrupted_line(tmp_path, monkeypatch):
    fb_path = _patch_feedback_path(monkeypatch, tmp_path)
    fb_path.write_text('not valid json\n{"id": "GAP-1", "status": "open"}\n', encoding="utf-8")

    hub.action_feedback_resolve(tmp_path, "GAP-1")

    lines = fb_path.read_text(encoding="utf-8").splitlines()
    assert any('"status": "done"' in line for line in lines)
