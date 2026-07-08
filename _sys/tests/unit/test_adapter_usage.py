"""Unit tests for adapter token usage extraction."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub_peer


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def test_claude_extract_usage_reads_matching_session_jsonl(tmp_path, monkeypatch):
    session_id = "claude-session-1"
    projects = tmp_path / "claude-projects"
    monkeypatch.setattr(hub_peer, "_claude_projects_dir", lambda: projects)
    _write_jsonl(
        projects / "project-a" / f"{session_id}.jsonl",
        [
            {"type": "user", "sessionId": session_id},
            {
                "type": "assistant",
                "sessionId": session_id,
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 10,
                        "cache_read_input_tokens": 3,
                        "cache_creation_input_tokens": 2,
                        "output_tokens": 7,
                        "output_tokens_details": {"reasoning_tokens": 4},
                    },
                },
            },
        ],
    )

    usage = hub_peer.ClaudeAdapter().extract_usage("", {}, session_id=session_id)

    assert usage == {
        "input_tokens": 15,
        "output_tokens": 7,
        "reasoning_tokens": 4,
    }


def test_claude_extract_usage_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_peer, "_claude_projects_dir", lambda: tmp_path / "missing")

    assert hub_peer.ClaudeAdapter().extract_usage("", {}, session_id="missing") == {}


def test_claude_extract_usage_session_mismatch_returns_empty(tmp_path, monkeypatch):
    projects = tmp_path / "claude-projects"
    monkeypatch.setattr(hub_peer, "_claude_projects_dir", lambda: projects)
    _write_jsonl(
        projects / "project-a" / "expected.jsonl",
        [
            {
                "type": "assistant",
                "sessionId": "other",
                "message": {"role": "assistant", "usage": {"input_tokens": 1, "output_tokens": 2}},
            },
        ],
    )

    assert hub_peer.ClaudeAdapter().extract_usage("", {}, session_id="expected") == {}


def test_agy_extract_usage_reads_matching_transcript(tmp_path, monkeypatch):
    session_id = "agy-session-1"
    brain = tmp_path / "brain"
    conversations = tmp_path / "conversations"
    monkeypatch.setattr(hub_peer, "_agy_brain_dir", lambda: brain)
    monkeypatch.setattr(hub_peer, "_agy_conversations_dir", lambda: conversations)
    _write_jsonl(
        brain / session_id / ".system_generated" / "logs" / "transcript.jsonl",
        [
            {"conversationId": session_id, "event": "start"},
            {
                "conversationId": session_id,
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 5,
                    "reasoning_tokens": 2,
                },
            },
        ],
    )

    usage = hub_peer.AgyAdapter().extract_usage("", {}, session_id=session_id)

    assert usage == {
        "input_tokens": 8,
        "output_tokens": 5,
        "reasoning_tokens": 2,
    }


def test_agy_extract_usage_missing_transcript_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_peer, "_agy_brain_dir", lambda: tmp_path / "brain")
    monkeypatch.setattr(hub_peer, "_agy_conversations_dir", lambda: tmp_path / "conversations")

    assert hub_peer.AgyAdapter().extract_usage("", {}, session_id="missing") == {}


def test_agy_extract_usage_session_mismatch_returns_empty(tmp_path, monkeypatch):
    session_id = "expected"
    brain = tmp_path / "brain"
    conversations = tmp_path / "conversations"
    monkeypatch.setattr(hub_peer, "_agy_brain_dir", lambda: brain)
    monkeypatch.setattr(hub_peer, "_agy_conversations_dir", lambda: conversations)
    _write_jsonl(
        brain / session_id / ".system_generated" / "logs" / "transcript.jsonl",
        [
            {
                "conversationId": "other",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        ],
    )

    assert hub_peer.AgyAdapter().extract_usage("", {}, session_id=session_id) == {}


def test_codex_extract_usage_parses_jsonl_stream():
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
            json.dumps({"type": "item.completed", "item": {"text": "done"}}),
            json.dumps(
                {
                    "type": "token_count",
                    "usage": {
                        "input_tokens": 11,
                        "output_tokens": 13,
                        "output_tokens_details": {"reasoning_tokens": 5},
                    },
                }
            ),
        ]
    )

    usage = hub_peer.CodexAdapter().extract_usage(
        stdout,
        {"invoke_args": ["exec", "{query}", "--json"]},
        session_id="thread-1",
    )

    assert usage == {
        "input_tokens": 11,
        "output_tokens": 13,
        "reasoning_tokens": 5,
    }


def test_codex_extract_usage_empty_stream_returns_empty():
    assert hub_peer.CodexAdapter().extract_usage(
        "",
        {"invoke_args": ["exec", "{query}", "--json"]},
        session_id="thread-1",
    ) == {}


def test_codex_extract_usage_thread_mismatch_returns_empty():
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "other-thread"}),
            json.dumps({"type": "usage", "usage": {"input_tokens": 1, "output_tokens": 2}}),
        ]
    )

    assert hub_peer.CodexAdapter().extract_usage(
        stdout,
        {"invoke_args": ["exec", "{query}", "--json"]},
        session_id="thread-1",
    ) == {}
