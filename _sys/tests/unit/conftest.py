"""pytest fixtures for hub.py unit tests."""
import os
import sys
import json
import tempfile
import shutil
import pytest
from pathlib import Path

# hub.py 경로를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))


@pytest.fixture
def ai_dir(tmp_path):
    """격리된 임시 .ai/ 디렉토리."""
    ai = tmp_path / ".ai"
    (ai / ".lock").mkdir(parents=True)
    (ai / "sessions").mkdir()
    (ai / "consensus").mkdir()
    (ai / "mailbox.json").write_text(
        json.dumps({"messages": [], "unread_count": 0}), encoding="utf-8"
    )
    (ai / "state.json").write_text(
        json.dumps({
            "pair": None, "claude_sid": None, "gemini_sid": None,
            "mission": None, "blocked": None, "phase": None, "updated_at": None
        }), encoding="utf-8"
    )
    (ai / "nodes.json").write_text(
        json.dumps({
            "version": "1",
            "nodes": {
                "cc": {"tier": 1, "type": "orchestrator", "invoke": "claude",
                       "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "persistent"},
                "ca": {"tier": 2, "type": "agent", "invoke": "claude",
                       "invoke_args": ["-p", "{query}"], "timeout": 0, "memory": "short-term"},
                "gc": {"tier": 3, "type": "sensor", "invoke": "gemini",
                       "invoke_args": ["-p", "{query}", "-o", "text", "-y"], "timeout": 0, "memory": "session"},
            }
        }), encoding="utf-8"
    )
    return ai


@pytest.fixture(autouse=True)
def patch_ai_root(ai_dir, monkeypatch):
    """모든 테스트에서 find_ai_root()가 tmp .ai/ 반환하도록 패치."""
    import hub
    monkeypatch.setattr(hub, "find_ai_root", lambda: ai_dir)
    monkeypatch.setattr(hub, "ensure_ai_dir", lambda p: p)
    return ai_dir
