"""Tests for hub_peer.py — PeerAdapter interface and adapter factory."""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

import hub_peer
from hub_peer import (
    PeerAdapter, BaseAdapter, ClaudeAdapter, GeminiAdapter, CodexAdapter, VirtualAdapter,
    get_adapter, get_adapter_for_peer,
    _ADAPTER_REGISTRY, _INVOKE_TO_ADAPTER,
)


# ── Protocol conformance ──────────────────────────────────────────────────────

class TestPeerAdapterProtocol:
    @pytest.mark.parametrize("cls", [ClaudeAdapter, GeminiAdapter, CodexAdapter, VirtualAdapter])
    def test_adapter_satisfies_protocol(self, cls):
        adapter = cls()
        assert isinstance(adapter, PeerAdapter)

    @pytest.mark.parametrize("cls", [ClaudeAdapter, GeminiAdapter, CodexAdapter, VirtualAdapter])
    def test_adapter_has_node_id(self, cls):
        adapter = cls()
        assert hasattr(adapter, "node_id")
        assert isinstance(adapter.node_id, str)

    @pytest.mark.parametrize("cls", [ClaudeAdapter, GeminiAdapter, CodexAdapter, VirtualAdapter])
    def test_build_cmd_returns_tuple(self, cls):
        adapter = cls()
        node = {"invoke": "claude", "invoke_args": ["-p", "{query}"]}
        result = adapter.build_cmd(node, "test query")
        assert isinstance(result, tuple) and len(result) == 2
        cmd, use_stdin = result
        assert isinstance(cmd, list) and len(cmd) >= 1
        assert isinstance(use_stdin, bool)


# ── ClaudeAdapter ─────────────────────────────────────────────────────────────

class TestClaudeAdapter:
    def setup_method(self):
        self.adapter = ClaudeAdapter()
        self.node = {
            "node_id": "cc", "invoke": "claude",
            "invoke_args": ["-p", "{query}", "--permission-mode", "acceptEdits"]
        }

    def test_build_cmd_substitutes_query(self):
        cmd, _ = self.adapter.build_cmd(self.node, "hello world")
        assert "hello world" in cmd
        assert cmd[0] == "claude"

    def test_parse_output_strips_whitespace(self):
        result = self.adapter.parse_output("  response text  \n", self.node)
        assert result == "response text"

    def test_build_cmd_no_query_placeholder(self):
        node = {"invoke": "claude", "invoke_args": ["--version"]}
        cmd, _ = self.adapter.build_cmd(node, "ignored")
        assert cmd == ["claude", "--version"]


# ── GeminiAdapter ─────────────────────────────────────────────────────────────

class TestGeminiAdapter:
    def setup_method(self):
        self.adapter = GeminiAdapter()
        self.node = {
            "node_id": "gc", "invoke": "gemini",
            "invoke_args": ["-p", "{query}", "-o", "text"]
        }

    def test_build_cmd_substitutes_query(self):
        cmd, use_stdin = self.adapter.build_cmd(self.node, "explain me")
        assert cmd[0] == "gemini"
        # GeminiAdapter uses stdin mode: query passed via stdin, not in cmd
        if use_stdin:
            assert "-" in cmd or "explain me" not in cmd
        else:
            assert "explain me" in cmd

    def test_parse_output_strips_session_headers(self):
        raw = "✦ Session started\n● connecting...\n─────\nActual response here"
        result = self.adapter.parse_output(raw, self.node)
        assert "✦" not in result
        assert "●" not in result
        assert "Actual response here" in result

    def test_parse_output_keeps_content_lines(self):
        raw = "This is the answer\nWith multiple lines"
        result = self.adapter.parse_output(raw, self.node)
        assert "This is the answer" in result


# ── CodexAdapter ──────────────────────────────────────────────────────────────

class TestCodexAdapter:
    def setup_method(self):
        self.adapter = CodexAdapter()
        self.node = {
            "node_id": "cx", "invoke": "codex",
            "invoke_args": ["exec", "{query}", "--json", "--ephemeral"]
        }

    def test_build_cmd_substitutes_query(self):
        cmd, use_stdin = self.adapter.build_cmd(self.node, "write a test")
        assert cmd[0] == "codex"
        if use_stdin:
            assert "-" in cmd or "write a test" not in cmd
        else:
            assert "write a test" in cmd

    def test_parse_output_extracts_json_assistant_content(self):
        response = json.dumps({
            "messages": [
                {"role": "user", "content": "ignored"},
                {"role": "assistant", "content": [{"type": "text", "text": "Here is the answer"}]},
            ]
        })
        result = self.adapter.parse_output(response, self.node)
        assert result == "Here is the answer"

    def test_parse_output_handles_string_content(self):
        response = json.dumps({
            "messages": [
                {"role": "assistant", "content": "Direct string response"},
            ]
        })
        result = self.adapter.parse_output(response, self.node)
        assert result == "Direct string response"

    def test_parse_output_falls_back_on_invalid_json(self):
        result = self.adapter.parse_output("not json at all", self.node)
        assert result == "not json at all"

    def test_parse_output_without_json_flag_returns_raw(self):
        node = {"invoke": "codex", "invoke_args": ["exec", "{query}"]}
        result = self.adapter.parse_output("plain output", node)
        assert result == "plain output"


# ── VirtualAdapter ────────────────────────────────────────────────────────────

class TestVirtualAdapter:
    def test_build_cmd_uses_invoke_field(self):
        adapter = VirtualAdapter()
        node = {
            "node_id": "cc-deep", "type": "virtual", "peer": "cc",
            "invoke": "claude",
            "invoke_args": ["-p", "{query}", "--effort", "max"]
        }
        cmd, use_stdin = adapter.build_cmd(node, "deep question")
        assert cmd[0] == "claude"
        assert "--effort" in cmd
        if use_stdin:
            assert "-" in cmd or "deep question" not in cmd
        else:
            assert "deep question" in cmd


# ── get_adapter factory ───────────────────────────────────────────────────────

class TestGetAdapter:
    def test_explicit_adapter_class_takes_priority(self):
        node = {"adapter_class": "GeminiAdapter", "invoke": "claude", "node_id": "test"}
        adapter = get_adapter(node)
        assert isinstance(adapter, GeminiAdapter)

    def test_auto_detect_from_invoke_claude(self):
        node = {"invoke": "claude", "node_id": "cc"}
        adapter = get_adapter(node)
        assert isinstance(adapter, ClaudeAdapter)

    def test_auto_detect_from_invoke_gemini(self):
        node = {"invoke": "gemini", "node_id": "gc"}
        adapter = get_adapter(node)
        assert isinstance(adapter, GeminiAdapter)

    def test_auto_detect_from_invoke_codex(self):
        node = {"invoke": "codex", "node_id": "cx"}
        adapter = get_adapter(node)
        assert isinstance(adapter, CodexAdapter)

    def test_virtual_type_fallback(self):
        node = {"type": "virtual", "invoke": "unknown-tool", "node_id": "virt"}
        adapter = get_adapter(node)
        assert isinstance(adapter, VirtualAdapter)

    def test_unknown_returns_base_adapter(self):
        node = {"invoke": "totally-unknown", "node_id": "unk"}
        adapter = get_adapter(node)
        assert isinstance(adapter, BaseAdapter)

    def test_unknown_adapter_class_falls_back_to_invoke(self):
        node = {"adapter_class": "NonExistent", "invoke": "gemini", "node_id": "gc"}
        adapter = get_adapter(node)
        assert isinstance(adapter, GeminiAdapter)


# ── get_adapter_for_peer ──────────────────────────────────────────────────────

class TestGetAdapterForPeer:
    def _mock_orch(self, nodes):
        return patch.object(hub_peer, "_load_orchestration", return_value={"hub_nodes": nodes})

    def test_loads_adapter_from_orchestration(self):
        nodes = [{"node_id": "gc", "adapter_class": "GeminiAdapter", "invoke": "gemini", "aliases": []}]
        with self._mock_orch(nodes):
            adapter = get_adapter_for_peer("gc")
        assert isinstance(adapter, GeminiAdapter)

    def test_resolves_by_alias(self):
        nodes = [{"node_id": "gc", "adapter_class": "GeminiAdapter", "invoke": "gemini", "aliases": ["gemini"]}]
        with self._mock_orch(nodes):
            adapter = get_adapter_for_peer("gemini")
        assert isinstance(adapter, GeminiAdapter)

    def test_fallback_map_cc(self):
        with self._mock_orch([]):
            adapter = get_adapter_for_peer("cc")
        assert isinstance(adapter, ClaudeAdapter)

    def test_fallback_map_gc(self):
        with self._mock_orch([]):
            adapter = get_adapter_for_peer("gc")
        assert isinstance(adapter, GeminiAdapter)

    def test_fallback_map_cx(self):
        with self._mock_orch([]):
            adapter = get_adapter_for_peer("cx")
        assert isinstance(adapter, CodexAdapter)


# ── Session state ─────────────────────────────────────────────────────────────

class TestSessionState:
    def test_store_and_retrieve_session(self, tmp_path):
        adapter = BaseAdapter()
        node = {"node_id": "gc"}
        state = {"session_id": "abc123", "created": "2026-06-18T00:00:00Z"}
        adapter.store_session_state(tmp_path, node, state)
        retrieved = adapter.get_session_state(tmp_path, node)
        assert retrieved == state

    def test_get_session_returns_none_if_missing(self, tmp_path):
        adapter = BaseAdapter()
        node = {"node_id": "nonexistent"}
        result = adapter.get_session_state(tmp_path, node)
        assert result is None

    def test_session_file_uses_peer_field(self, tmp_path):
        adapter = BaseAdapter()
        node = {"peer": "gc", "node_id": "gc-plan"}
        state = {"session_id": "xyz"}
        adapter.store_session_state(tmp_path, node, state)
        # File should be stored under "gc" not "gc-plan"
        f = tmp_path / "sessions" / "gc.json"
        assert f.exists()
