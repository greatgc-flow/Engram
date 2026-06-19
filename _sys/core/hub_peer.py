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


def resolve_node_id(node_id: str | None, *, orch: dict | None = None) -> str | None:
    """Resolve a node ID, alias, or invoke name to its canonical node ID."""
    if not node_id or not isinstance(node_id, str):
        return None
    orch = orch or _load_orchestration()
    nodes = orch.get("hub_nodes", [])
    for node in nodes:
        canonical = node.get("node_id")
        if canonical == node_id or node_id in node.get("aliases", []):
            return canonical
    for node in nodes:
        if node.get("invoke") == node_id:
            return node.get("node_id")
    return None


def _parent_node_id(node: dict) -> str | None:
    """Return the declared parent, accepting legacy `peer` during migration."""
    return node.get("parent_node") or (
        node.get("peer") if node.get("type") == "virtual" else None
    )


def is_routable(node_id: str | None, *, orch: dict | None = None) -> bool:
    """Return effective routability after recursively evaluating ancestors."""
    orch = orch or _load_orchestration()
    canonical = resolve_node_id(node_id, orch=orch)
    if canonical is None:
        return False
    nodes = {
        node["node_id"]: node
        for node in orch.get("hub_nodes", [])
        if node.get("node_id")
    }
    current = canonical
    seen: set[str] = set()
    while current:
        if current in seen:
            return False
        seen.add(current)
        node = nodes.get(current)
        if node is None or node.get("enabled") is False:
            return False
        parent = _parent_node_id(node)
        if not parent:
            return True
        current = parent
    return False


def root_peer_id(node_id: str | None, *, orch: dict | None = None) -> str | None:
    """Return the physical root peer for a routable node tree."""
    orch = orch or _load_orchestration()
    canonical = resolve_node_id(node_id, orch=orch)
    if canonical is None or not is_routable(canonical, orch=orch):
        return None
    nodes = {
        node["node_id"]: node
        for node in orch.get("hub_nodes", [])
        if node.get("node_id")
    }
    current = canonical
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            return None
        parent = _parent_node_id(node)
        if not parent:
            return current
        current = parent
    return None


# ── Protocol (structural interface) ──────────────────────────────────────────

@runtime_checkable
class PeerAdapter(Protocol):
    """Universal peer adapter interface. Each peer type implements this."""

    node_id: str

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        """Build the subprocess command list and return (cmd, use_stdin)."""
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

    def extract_usage(self, stdout: str, node: dict[str, Any]) -> dict[str, Any]:
        """Extract token usage metadata from raw subprocess stdout. Override per adapter."""
        return {}

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "claude")
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        use_stdin = False
        cmd_args = []
        for a in raw_args:
            if "{query}" in a:
                if node.get("requires_pty"):
                    cmd_args.append(a.replace("{query}", query))
                else:
                    cmd_args.append(a.replace("{query}", "-"))
                    use_stdin = True
            else:
                cmd_args.append(a)
        return [invoke] + cmd_args, use_stdin

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()


# ── Peer-specific adapters ────────────────────────────────────────────────────

class ClaudeAdapter(BaseAdapter):
    """Adapter for cc (Claude Code CLI)."""

    node_id = "cc"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "claude")
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        # Claude Code currently doesn't use session_id for resume via CLI flags in the same way cx/gc do.
        # It relies on local state files.
        return [invoke] + self._substitute_args(raw_args, query), False

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()


class GeminiAdapter(BaseAdapter):
    """Adapter for gc (Gemini CLI)."""

    node_id = "gc"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "gemini")
        # Legacy hub.py logic for gc:
        if session_id:
            return [invoke, "--resume", session_id, "-p", "-", "-o", "text", "--approval-mode", "auto_edit", "--skip-trust"], True
        
        # Fresh session: we can't generate the UUID here easily without side effects if we want to be pure, 
        # but for now we'll match legacy hub.py behavior.
        # Note: hub.py handles generating the new UUID if session_id is None.
        return [invoke, "-p", "-", "-o", "text", "--approval-mode", "auto_edit", "--skip-trust"], True

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        # Strip Gemini CLI session header lines (start with ✦ or ●)
        lines = stdout.splitlines()
        clean = [l for l in lines if not l.strip().startswith(("✦", "●", "─"))]
        return "\n".join(clean).strip()


class CodexAdapter(BaseAdapter):
    """Adapter for cx (OpenAI Codex CLI)."""

    node_id = "cx"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "codex")
        base = ["-s", "workspace-write", "--json", "--ignore-rules"]
        if session_id:
            return [invoke, "exec", "resume", session_id, "-"] + base, True
        return [invoke, "exec", "-"] + base, True

    def extract_usage(self, stdout: str, node: dict[str, Any]) -> dict[str, Any]:
        """Extract token usage from Codex --json response."""
        if "--json" not in node.get("invoke_args", []):
            return {}
        try:
            data = json.loads(stdout)
            usage = data.get("usage", {})
            details = usage.get("output_tokens_details", {})
            return {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "reasoning_tokens": details.get("reasoning_tokens"),
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            return {}

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


class AgyAdapter(BaseAdapter):
    """Adapter for ag (Antigravity / agy CLI — Gemini successor)."""

    node_id = "ag"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "agy")
        raw_args = node.get("invoke_args", ["--dangerously-skip-permissions", "-p", "{query}"])
        # agy -p takes the prompt inline (not via stdin); use _substitute_args to keep query in args
        return [invoke] + self._substitute_args(raw_args, query), False

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()


class VirtualAdapter(BaseAdapter):
    """Adapter for virtual nodes (profile-specific variants like cc-deep)."""

    node_id = "virtual"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        # Virtual nodes Typically inherit their base peer's behavior but with different flags
        return super().build_cmd(node, query, session_id)


# ── Adapter registry + factory ────────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "ClaudeAdapter": ClaudeAdapter,
    "GeminiAdapter": GeminiAdapter,
    "AgyAdapter": AgyAdapter,
    "CodexAdapter": CodexAdapter,
    "VirtualAdapter": VirtualAdapter,
}

_INVOKE_TO_ADAPTER: dict[str, type[BaseAdapter]] = {
    "claude": ClaudeAdapter,
    "gemini": GeminiAdapter,
    "agy": AgyAdapter,
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


def get_adapter_for_peer(peer_id: str, *, skip_disabled: bool = True) -> BaseAdapter:
    """Convenience: get adapter by peer_id, loading node config from orchestration.json.

    Raises ValueError if peer is disabled (enabled:false) unless skip_disabled=False.
    """
    orch = _load_orchestration()
    canonical = resolve_node_id(peer_id, orch=orch)
    if canonical is not None:
        if skip_disabled and not is_routable(canonical, orch=orch):
            raise ValueError(f"peer {peer_id!r} is disabled by node-tree policy")
        for node in orch.get("hub_nodes", []):
            if node.get("node_id") == canonical:
                return get_adapter(node)
    return BaseAdapter()


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
