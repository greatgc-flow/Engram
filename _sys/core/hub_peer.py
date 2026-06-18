"""hub_peer.py — Universal peer interface + adapter contract (Phase 4).

Defines the PeerAdapter interface and a factory that selects the right
adapter based on orchestration.json `adapter_class` field.

This module does NOT replace hub.py's action_ask() — it exposes a typed
interface for peer interaction that higher-level code and tests can use
without importing all 5000+ lines of hub.py.

Interface contract (impl-plan.md §4.2):
    build_cmd(node, query)         → list[str]
    parse_output(stdout, node)     → str
    get_session_state(ai_root, node) → dict | None
    store_session_state(ai_root, node, state) → None

Adapter selection:
    orchestration.json hub_nodes[].adapter_class → adapter registry
    If not set: auto-detect from invoke field (claude/gemini/codex)
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_ORCHESTRATION_PATH = _AI_DIR / "orchestration.json"
_SESSIONS_PATH = _AI_DIR / "sessions"


def _load_orchestration() -> dict:
    if _ORCHESTRATION_PATH.exists():
        try:
            return json.loads(_ORCHESTRATION_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ── Protocol (structural interface) ──────────────────────────────────────────

@runtime_checkable
class PeerAdapter(Protocol):
    """Universal peer adapter interface. Each peer type implements this."""

    node_id: str

    def build_cmd(self, node: dict[str, Any], query: str) -> list[str]:
        """Build the subprocess command list for this peer."""
        ...

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        """Extract the usable response text from raw subprocess stdout."""
        ...

    def get_session_state(self, ai_root: Path, node: dict[str, Any]) -> dict | None:
        """Return stored session state dict, or None if no session exists."""
        ...

    def store_session_state(
        self, ai_root: Path, node: dict[str, Any], state: dict[str, Any]
    ) -> None:
        """Persist session state for reuse across hub.py calls."""
        ...


# ── Base adapter ──────────────────────────────────────────────────────────────

class BaseAdapter:
    """Common utilities shared across all adapters."""

    node_id: str = "base"

    def _session_file(self, ai_root: Path, node: dict[str, Any]) -> Path:
        peer = node.get("peer") or node.get("node_id", self.node_id)
        return ai_root / "sessions" / f"{peer}.json"

    def get_session_state(self, ai_root: Path, node: dict[str, Any]) -> dict | None:
        f = self._session_file(ai_root, node)
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def store_session_state(
        self, ai_root: Path, node: dict[str, Any], state: dict[str, Any]
    ) -> None:
        f = self._session_file(ai_root, node)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _substitute_args(self, raw_args: list[str], query: str) -> list[str]:
        """Replace {query} placeholder in invoke_args with actual query."""
        return [a.replace("{query}", query) for a in raw_args]

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()


# ── Peer-specific adapters ────────────────────────────────────────────────────

class ClaudeAdapter(BaseAdapter):
    """Adapter for cc (Claude Code CLI)."""

    node_id = "cc"

    def build_cmd(self, node: dict[str, Any], query: str) -> list[str]:
        invoke = node.get("invoke", "claude")
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        return [invoke] + self._substitute_args(raw_args, query)

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()


class GeminiAdapter(BaseAdapter):
    """Adapter for gc (Gemini CLI)."""

    node_id = "gc"

    def build_cmd(self, node: dict[str, Any], query: str) -> list[str]:
        invoke = node.get("invoke", "gemini")
        raw_args = node.get("invoke_args", ["-p", "{query}", "-o", "text", "-y"])
        return [invoke] + self._substitute_args(raw_args, query)

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        # Strip Gemini CLI session header lines (start with ✦ or ●)
        lines = stdout.splitlines()
        clean = [l for l in lines if not l.strip().startswith(("✦", "●", "─"))]
        return "\n".join(clean).strip()


class CodexAdapter(BaseAdapter):
    """Adapter for cx (OpenAI Codex CLI)."""

    node_id = "cx"

    def build_cmd(self, node: dict[str, Any], query: str) -> list[str]:
        invoke = node.get("invoke", "codex")
        raw_args = node.get("invoke_args", ["exec", "{query}", "--json", "--ephemeral"])
        return [invoke] + self._substitute_args(raw_args, query)

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        # Codex --json mode: extract assistant content from JSON response
        if "--json" in node.get("invoke_args", []):
            try:
                data = json.loads(stdout)
                msgs = data.get("messages") or data.get("output") or []
                if isinstance(msgs, list):
                    parts = []
                    for m in msgs:
                        if isinstance(m, dict) and m.get("role") == "assistant":
                            content = m.get("content", "")
                            if isinstance(content, list):
                                parts.extend(
                                    c.get("text", "") for c in content
                                    if isinstance(c, dict) and c.get("type") == "text"
                                )
                            else:
                                parts.append(str(content))
                    if parts:
                        return "\n".join(parts).strip()
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return stdout.strip()


class VirtualAdapter(BaseAdapter):
    """Adapter for virtual nodes (profile-specific variants like cc-deep)."""

    node_id = "virtual"

    def build_cmd(self, node: dict[str, Any], query: str) -> list[str]:
        invoke = node.get("invoke", "claude")
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        return [invoke] + self._substitute_args(raw_args, query)


# ── Adapter registry + factory ────────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "ClaudeAdapter": ClaudeAdapter,
    "GeminiAdapter": GeminiAdapter,
    "CodexAdapter": CodexAdapter,
    "VirtualAdapter": VirtualAdapter,
}

_INVOKE_TO_ADAPTER: dict[str, type[BaseAdapter]] = {
    "claude": ClaudeAdapter,
    "gemini": GeminiAdapter,
    "codex": CodexAdapter,
}


def get_adapter(node: dict[str, Any]) -> BaseAdapter:
    """Return the correct adapter for a node dict.

    Selection order:
      1. node["adapter_class"] → registry lookup
      2. node["invoke"] → auto-detect by executable name
      3. node["type"] == "virtual" → VirtualAdapter
      4. fallback: BaseAdapter
    """
    # 1. Explicit adapter_class
    adapter_class = node.get("adapter_class")
    if adapter_class and adapter_class in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[adapter_class]()

    # 2. Auto-detect from invoke field
    invoke = node.get("invoke", "")
    adapter_cls = _INVOKE_TO_ADAPTER.get(invoke)
    if adapter_cls:
        return adapter_cls()

    # 3. Virtual node
    if node.get("type") == "virtual":
        return VirtualAdapter()

    # 4. Fallback
    return BaseAdapter()


def get_adapter_for_peer(peer_id: str) -> BaseAdapter:
    """Convenience: get adapter by peer_id, loading node config from orchestration.json."""
    orch = _load_orchestration()
    for node in orch.get("hub_nodes", []):
        if node.get("node_id") == peer_id or peer_id in node.get("aliases", []):
            return get_adapter(node)
    # fallback by peer_id name
    fallback_map = {"cc": ClaudeAdapter, "gc": GeminiAdapter, "cx": CodexAdapter}
    cls = fallback_map.get(peer_id, BaseAdapter)
    return cls()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="hub_peer — adapter inspection tool")
    parser.add_argument("--peer", default="cc", help="Peer ID to inspect")
    parser.add_argument("--query", default="hello", help="Test query for build_cmd")
    parser.add_argument("--list", action="store_true", help="List registered adapters")
    args = parser.parse_args()

    if args.list:
        print("Registered adapters:")
        for k, v in _ADAPTER_REGISTRY.items():
            print(f"  {k:<20} → {v.__name__}")
        print("\nAuto-detect map (invoke → adapter):")
        for k, v in _INVOKE_TO_ADAPTER.items():
            print(f"  {k:<12} → {v.__name__}")
        return

    adapter = get_adapter_for_peer(args.peer)
    orch = _load_orchestration()
    node = next(
        (n for n in orch.get("hub_nodes", []) if n.get("node_id") == args.peer),
        {"node_id": args.peer, "invoke": args.peer, "invoke_args": ["-p", "{query}"]},
    )
    cmd = adapter.build_cmd(node, args.query)
    print(f"Peer     : {args.peer}")
    print(f"Adapter  : {type(adapter).__name__}")
    print(f"Command  : {shlex.join(cmd)}")


if __name__ == "__main__":
    _main()
