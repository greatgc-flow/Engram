"""Tests for hub_peer.py ??PeerAdapter interface and adapter factory."""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

import hub_peer
from hub_peer import (
    PeerAdapter, BaseAdapter, ClaudeAdapter, AgyAdapter, AgyAdapter, CodexAdapter, VirtualAdapter,
    ContextPolicy,
    get_adapter, get_adapter_for_peer,
    _ADAPTER_REGISTRY, _INVOKE_TO_ADAPTER,
)


# ?? Protocol conformance ??????????????????????????????????????????????????????

class TestPeerAdapterProtocol:
    @pytest.mark.parametrize("cls", [ClaudeAdapter, AgyAdapter, CodexAdapter, VirtualAdapter])
    def test_adapter_satisfies_protocol(self, cls):
        adapter = cls()
        assert isinstance(adapter, PeerAdapter)

    @pytest.mark.parametrize("cls", [ClaudeAdapter, AgyAdapter, CodexAdapter, VirtualAdapter])
    def test_adapter_has_node_id(self, cls):
        adapter = cls()
        assert hasattr(adapter, "node_id")
        assert isinstance(adapter.node_id, str)

    @pytest.mark.parametrize("cls", [ClaudeAdapter, AgyAdapter, CodexAdapter, VirtualAdapter])
    def test_build_cmd_returns_tuple(self, cls):
        adapter = cls()
        node = {"invoke": "claude", "invoke_args": ["-p", "{query}"]}
        result = adapter.build_cmd(node, "test query")
        assert isinstance(result, tuple) and len(result) == 2
        cmd, use_stdin = result
        assert isinstance(cmd, list) and len(cmd) >= 1
        assert isinstance(use_stdin, bool)


# ?? ClaudeAdapter ?????????????????????????????????????????????????????????????

class TestClaudeAdapter:
    def setup_method(self):
        self.adapter = ClaudeAdapter()
        self.node = {
            "node_id": "cc", "invoke": "claude",
            "invoke_args": ["-p", "{query}", "--permission-mode", "acceptEdits"]
        }

    def test_build_cmd_substitutes_query(self):
        cmd, use_stdin = self.adapter.build_cmd(self.node, "hello world")
        assert cmd[0] == "claude"
        if use_stdin:
            assert "-" in cmd or "hello world" not in cmd
        else:
            assert "hello world" in cmd

    def test_parse_output_strips_whitespace(self):
        result = self.adapter.parse_output("  response text  \n", self.node)
        assert result == "response text"

    def test_build_cmd_no_query_placeholder(self):
        node = {"invoke": "claude", "invoke_args": ["--version"]}
        cmd, _ = self.adapter.build_cmd(node, "ignored")
        assert cmd == ["claude", "--version"]


# ?? AgyAdapter ?????????????????????????????????????????????????????????????

class TestAgyAdapter:
    def setup_method(self):
        self.adapter = AgyAdapter()
        self.node = {
            "node_id": "ag", "invoke": "agy",
            "invoke_args": ["-p", "{query}", "-o", "text"]
        }

    def test_build_cmd_substitutes_query(self):
        cmd, use_stdin = self.adapter.build_cmd(self.node, "explain me")
        assert cmd[0] == "agy"
        # AgyAdapter uses stdin mode: query passed via stdin, not in cmd
        if use_stdin:
            assert "-" in cmd or "explain me" not in cmd
        else:
            assert "explain me" in cmd

    def test_parse_output_strips_session_headers(self):
        raw = "Session started\nconnecting...\n\nActual response here"
        result = self.adapter.parse_output(raw, self.node)
        assert "Actual response here" in result

    def test_parse_output_keeps_content_lines(self):
        raw = "This is the answer\nWith multiple lines"
        result = self.adapter.parse_output(raw, self.node)
        assert "This is the answer" in result


# ?? CodexAdapter ??????????????????????????????????????????????????????????????

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

    def test_extract_usage_returns_reasoning_tokens(self):
        response = json.dumps({
            "usage": {
                "input_tokens": 500,
                "output_tokens": 200,
                "output_tokens_details": {"reasoning_tokens": 150},
            },
            "messages": [{"role": "assistant", "content": "ok"}],
        })
        usage = self.adapter.extract_usage(response, self.node)
        assert usage["input_tokens"] == 500
        assert usage["output_tokens"] == 200
        assert usage["reasoning_tokens"] == 150

    def test_extract_usage_no_reasoning_tokens(self):
        response = json.dumps({
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "messages": [{"role": "assistant", "content": "hi"}],
        })
        usage = self.adapter.extract_usage(response, self.node)
        assert usage["reasoning_tokens"] is None

    def test_extract_usage_without_json_flag_returns_empty(self):
        node = {"invoke": "codex", "invoke_args": ["exec", "{query}"]}
        usage = self.adapter.extract_usage('{"usage": {"input_tokens": 1}}', node)
        assert usage == {}

    def test_extract_usage_invalid_json_returns_empty(self):
        usage = self.adapter.extract_usage("not json", self.node)
        assert usage == {}


# ?? BaseAdapter extract_usage ?????????????????????????????????????????????????

class TestBaseAdapterExtractUsage:
    def test_base_adapter_returns_empty(self):
        from hub_peer import BaseAdapter
        adapter = BaseAdapter()
        node = {"invoke": "claude", "invoke_args": ["-p", "{query}"]}
        assert adapter.extract_usage("any text", node) == {}


# ?? ContextPolicy (ADDENDUM-3) ????????????????????????????????????????????????

class TestContextPolicy:
    def test_base_context_policy_is_current_non_ag_default(self):
        assert BaseAdapter().context_policy({}) == ContextPolicy()

    def test_default_context_policy_values(self):
        policy = ContextPolicy()
        assert policy.preamble_lines == ()
        assert policy.skip_room_context_when_complete is False
        assert policy.handoff_sections is None
        # A6: new query-shaping fields default off ??cc/cx rendering unchanged.
        assert policy.query_first is False
        assert policy.skip_room_context is False

    @pytest.mark.parametrize("cls", [ClaudeAdapter, CodexAdapter])
    def test_cc_cx_gc_inherit_default_context_policy(self, cls):
        # cc/cx/gc must NOT override context_policy ??they stay byte-neutral.
        assert cls().context_policy({}) == ContextPolicy()
        assert "context_policy" not in cls.__dict__


# ?? VirtualAdapter ????????????????????????????????????????????????????????????

class TestAgyAdapter:
    def setup_method(self):
        self.adapter = AgyAdapter()
        self.node = {
            "node_id": "ag", "invoke": "agy",
            "invoke_args": ["--dangerously-skip-permissions", "-p", "{query}"],
            "requires_pty": False,
        }

    def test_build_cmd_substitutes_query_inline(self):
        cmd, use_stdin = self.adapter.build_cmd(self.node, "hello ag")
        assert cmd[0] == "agy"
        assert "--dangerously-skip-permissions" in cmd
        assert "-p" in cmd
        # Query must be inline (not stdin) ??AgyAdapter does not use stdin
        assert use_stdin is False
        assert "hello ag" in cmd

    def test_build_cmd_does_not_use_stdin(self):
        _, use_stdin = self.adapter.build_cmd(self.node, "test")
        assert use_stdin is False

    def test_parse_output_strips_whitespace(self):
        result = self.adapter.parse_output("  ANTIGRAVITY  \n", self.node)
        assert result == "ANTIGRAVITY"

    def test_parse_output_empty(self):
        assert self.adapter.parse_output("", self.node) == ""

    def test_parse_output_multiline(self):
        raw = "Line one\nLine two\nLine three"
        result = self.adapter.parse_output(raw, self.node)
        assert "Line one" in result
        assert "Line three" in result

    def test_extract_usage_returns_empty(self):
        assert self.adapter.extract_usage("any output", self.node) == {}

    def test_registry_contains_agy_adapter(self):
        from hub_peer import _ADAPTER_REGISTRY, _INVOKE_TO_ADAPTER
        assert "AgyAdapter" in _ADAPTER_REGISTRY
        assert "agy" in _INVOKE_TO_ADAPTER

    def test_get_adapter_by_adapter_class(self):
        node = {"adapter_class": "AgyAdapter", "invoke": "agy", "node_id": "ag"}
        adapter = get_adapter(node)
        assert isinstance(adapter, AgyAdapter)

    def test_get_adapter_by_invoke_agy(self):
        node = {"invoke": "agy", "node_id": "ag"}
        adapter = get_adapter(node)
        assert isinstance(adapter, AgyAdapter)

    # ?? A4: terminal-stream normalizer ????????????????????????????????????????
    def test_parse_output_carriage_return_overwrites_redraw(self):
        raw = "Thinking 10%\rThinking 100%\nAnswer"
        assert self.adapter.parse_output(raw, self.node) == "Thinking 100%\nAnswer"

    def test_parse_output_backspace_moves_cursor_left(self):
        assert self.adapter.parse_output("abc\b\bXY", self.node) == "aXY"

    def test_parse_output_csi_erase_line_clears_to_redraw(self):
        assert self.adapter.parse_output("old\x1b[2K\rnew", self.node) == "new"

    def test_parse_output_strips_osc_sequence(self):
        raw = "\x1b]0;window title\x07result"
        assert self.adapter.parse_output(raw, self.node) == "result"

    # ?€?€ A6: continuation/conversation flags are refused ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
    def test_build_session_cmd_injects_conversation(self):
        node = {
            "node_id": "ag", "invoke": "agy",
            "invoke_args": ["--dangerously-skip-permissions", "-p", "{query}"],
            "requires_pty": False,
        }
        cmd = self.adapter.build_session_cmd(node, "hello", "abc12345")
        assert cmd.cmd[0] == "agy"
        assert "--conversation" in cmd.cmd
        assert "abc12345" in cmd.cmd

    def test_build_cmd_does_not_scan_query_content_for_flags(self):
        # A query that literally contains "--continue" must NOT trip the guard.
        cmd, _ = self.adapter.build_cmd(self.node, "please --continue the task")
        assert "please --continue the task" in cmd

    # ?? ADDENDUM-3: context policy ????????????????????????????????????????????
    def test_ag_context_policy_encapsulates_context_delta(self):
        policy = self.adapter.context_policy({})
        assert policy.skip_room_context_when_complete is True
        assert policy.handoff_sections == ("GOAL", "PENDING_ISSUES", "KEY_DECISIONS")
        assert policy.preamble_lines[0] == "[IPC BOUNDARY]"
        assert len(policy.preamble_lines) == 4

    def test_ag_context_policy_is_query_first_and_minimal(self):
        # A6: agy is context-fragile ??task must lead and injected room/handoff
        # context is dropped unconditionally.
        policy = self.adapter.context_policy({})
        assert policy.query_first is True
        assert policy.skip_room_context is True


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


# ?? get_adapter factory ???????????????????????????????????????????????????????

class TestGetAdapter:
    def test_explicit_adapter_class_takes_priority(self):
        node = {"adapter_class": "AgyAdapter", "invoke": "claude", "node_id": "test"}
        adapter = get_adapter(node)
        assert isinstance(adapter, AgyAdapter)

    def test_auto_detect_from_invoke_claude(self):
        node = {"invoke": "claude", "node_id": "cc"}
        adapter = get_adapter(node)
        assert isinstance(adapter, ClaudeAdapter)

    def test_auto_detect_from_invoke_gemini(self):
        node = {"invoke": "agy", "node_id": "ag"}
        adapter = get_adapter(node)
        assert isinstance(adapter, AgyAdapter)

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
        node = {"adapter_class": "NonExistent", "invoke": "agy", "node_id": "ag"}
        adapter = get_adapter(node)
        assert isinstance(adapter, AgyAdapter)


# ?? get_adapter_for_peer ??????????????????????????????????????????????????????

class TestGetAdapterForPeer:
    def _mock_orch(self, nodes):
        return patch.object(hub_peer, "_load_orchestration", return_value={"hub_nodes": nodes})

    def test_loads_adapter_from_orchestration(self):
        nodes = [{"node_id": "ag", "adapter_class": "AgyAdapter", "invoke": "agy", "aliases": []}]
        with self._mock_orch(nodes):
            adapter = get_adapter_for_peer("ag")
        assert isinstance(adapter, AgyAdapter)

    def test_resolves_by_alias(self):
        nodes = [{"node_id": "ag", "adapter_class": "AgyAdapter", "invoke": "agy", "aliases": ["agy"]}]
        with self._mock_orch(nodes):
            adapter = get_adapter_for_peer("agy")
        assert isinstance(adapter, AgyAdapter)

    def test_fallback_returns_base_when_no_orch(self):
        # G1 fix: hardcoded fallback_map removed; empty orchestration ??BaseAdapter
        with self._mock_orch([]):
            assert isinstance(get_adapter_for_peer("cc"), BaseAdapter)
            assert isinstance(get_adapter_for_peer("ag"), BaseAdapter)
            assert isinstance(get_adapter_for_peer("cx"), BaseAdapter)

    def test_fallback_by_invoke_name(self):
        # G1: invoke-name fallback resolves via orchestration.json, not hardcoded map
        nodes = [{"node_id": "cc", "adapter_class": "ClaudeAdapter", "invoke": "claude"}]
        with self._mock_orch(nodes):
            adapter = get_adapter_for_peer("claude")  # match by invoke name
        assert isinstance(adapter, ClaudeAdapter)

    def test_virtual_node_with_disabled_parent_is_rejected(self):
        nodes = [
            {"node_id": "ag", "type": "peer", "enabled": False, "invoke": "agy"},
            {
                "node_id": "gc-plan",
                "type": "virtual",
                "parent_node": "ag",
                "adapter_class": "VirtualAdapter",
            },
        ]
        with self._mock_orch(nodes), pytest.raises(ValueError, match="node-tree"):
            get_adapter_for_peer("gc-plan")

    def test_alias_resolves_through_recursive_tree_gate(self):
        nodes = [
            {"node_id": "cc", "type": "peer", "invoke": "claude"},
            {
                "node_id": "cc-deep",
                "type": "virtual",
                "parent_node": "cc",
                "aliases": ["claude-deep"],
                "adapter_class": "VirtualAdapter",
            },
        ]
        with self._mock_orch(nodes):
            assert hub_peer.is_routable("claude-deep")
            assert hub_peer.root_peer_id("claude-deep") == "cc"


# ?? Session state ?????????????????????????????????????????????????????????????

class TestSessionState:
    def test_store_and_retrieve_session(self, tmp_path):
        adapter = BaseAdapter()
        node = {"node_id": "ag"}
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
        node = {"peer": "ag", "node_id": "gc-plan"}
        state = {"session_id": "xyz"}
        adapter.store_session_state(tmp_path, node, state)
        # File should be stored under "ag" not "gc-plan"
        f = tmp_path / "sessions" / "ag.json"
        assert f.exists()
