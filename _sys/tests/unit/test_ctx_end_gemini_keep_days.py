from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import ctx_end  # noqa: E402


def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("GEMINI_SESSION_KEEP", raising=False)
    assert ctx_end._gemini_session_keep_days() == 7


def test_valid_value(monkeypatch):
    monkeypatch.setenv("GEMINI_SESSION_KEEP", "14")
    assert ctx_end._gemini_session_keep_days() == 14


def test_invalid_value_falls_back_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("GEMINI_SESSION_KEEP", "not-a-number")
    assert ctx_end._gemini_session_keep_days() == 7
