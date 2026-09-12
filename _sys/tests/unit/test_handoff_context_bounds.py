import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core import hub


def test_automatic_context_uses_configured_context_fill_sections(tmp_path, monkeypatch):
    ai_root = tmp_path / ".ai"
    room_dir = ai_root / "sessions" / "room-test"
    room_dir.mkdir(parents=True)
    (ai_root / "state.json").write_text(
        json.dumps({"room_id": "room-test", "members": {}}), encoding="utf-8"
    )
    (room_dir / "handoff.md").write_text(
        "## [GOAL]\n- current goal\n\n"
        "## [PENDING_ISSUES]\n- current issue\n\n"
        "## [CONSENSUS_HISTORY]\n- stale expensive history\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hub, "_load_nodes", lambda _root: {})
    monkeypatch.setattr(hub, "_load_active_lessons", lambda **_kwargs: [])
    monkeypatch.setattr(hub, "_get_active_runtime_directives", lambda _path: [])
    monkeypatch.setattr(
        hub,
        "_load_protocol_cfg",
        lambda: {"session": {"context_fill_sections": ["GOAL", "PENDING_ISSUES"]}},
    )

    rendered = hub._build_ask_query_with_context(ai_root, "do work")

    assert "current goal" in rendered
    assert "current issue" in rendered
    assert "stale expensive history" not in rendered


def test_handoff_writer_enforces_total_character_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(hub, "HANDOFF_MAX_CHARS", 500)
    sections = {name: [] for name in hub._HANDOFF_SECTIONS}
    sections["KEY_DECISIONS"] = ["decision-" + ("x" * 2_000)]

    hub._write_handoff(tmp_path, sections)

    rendered = (tmp_path / "handoff.md").read_text(encoding="utf-8")
    sidecar = json.loads((tmp_path / "handoff.json").read_text(encoding="utf-8"))
    assert len(rendered) <= 500
    assert sidecar["sections"] == sections
