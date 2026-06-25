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
import copy
import hashlib
import os
import re
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ContextPolicy:
    """Adapter-owned policy for shaping hub-injected context.

    Defaults reproduce the current non-ag behavior exactly: no preamble,
    room context always included, handoff unfiltered, query rendered last,
    and room context never unconditionally skipped.
    """

    preamble_lines: tuple[str, ...] = ()
    skip_room_context_when_complete: bool = False
    handoff_sections: tuple[str, ...] | None = None
    # A6: query-first / minimal-context shaping for context-fragile adapters.
    # query_first renders [USER QUERY] immediately after the preamble (no
    # trailing duplicate) so the task leads; skip_room_context always drops
    # [HUB CONTEXT] and [HANDOFF] (distinct from skip_room_context_when_complete,
    # which only fires for completed rooms). Both default False → cc/cx unchanged.
    query_first: bool = False
    skip_room_context: bool = False


@dataclass(frozen=True)
class SessionInvocation:
    """Result of building a session-reuse command.

    cmd          : full subprocess argv (cmd[0] = executable name)
    use_stdin    : whether the query is delivered via stdin
    session_id   : the session/thread id this invocation will create or resume,
                   or None when the adapter cannot predict it ahead of time
    """
    cmd: list[str]
    use_stdin: bool
    session_id: str | None = None

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_ORCHESTRATION_PATH = _AI_DIR / "orchestration.json"
_SESSIONS_PATH = _AI_DIR / "sessions"
_ORCHESTRATION_MTIME_NS = -1
_ORCHESTRATION_CACHE: dict[str, Any] = {}
_NORMALIZED_CACHE: dict[str, Any] | None = None
_NORMALIZED_SOURCE: dict[str, Any] | None = None
_PEERS_PATH = _AI_DIR / "peers.json"
_PEERS_MTIME_NS = -1
_PEERS_SYS_DIR_CACHE: dict[str, str] = {}


def resolve_peer_sys_dir(peer_id: str, sys_dir: Path | str | None = None) -> str | None:
    """Resolve peer_id to its sys_subdir based on peers.json.
    If sys_dir is provided, the path is resolved relative to it, otherwise just the subdir is returned.
    """
    global _PEERS_MTIME_NS, _PEERS_SYS_DIR_CACHE
    base_id = peer_id.split('.')[0]
    if _PEERS_PATH.exists():
        try:
            mtime_ns = _PEERS_PATH.stat().st_mtime_ns
            if mtime_ns != _PEERS_MTIME_NS:
                peers_data = json.loads(_PEERS_PATH.read_text(encoding="utf-8")).get("peers", {})
                new_cache = {}
                for p_cfg in peers_data.values():
                    subdir = p_cfg.get("sys_subdir")
                    if subdir:
                        for n_id in p_cfg.get("node_ids", []):
                            new_cache[n_id] = subdir
                _PEERS_SYS_DIR_CACHE = new_cache
                _PEERS_MTIME_NS = mtime_ns
        except Exception:
            pass
    
    subdir = _PEERS_SYS_DIR_CACHE.get(base_id)
    if not subdir:
        return None
        
    if sys_dir is not None:
        return str(Path(sys_dir) / subdir)
    return subdir


def _load_orchestration() -> dict:
    global _ORCHESTRATION_MTIME_NS, _ORCHESTRATION_CACHE
    global _NORMALIZED_CACHE, _NORMALIZED_SOURCE
    if _ORCHESTRATION_PATH.exists():
        try:
            mtime_ns = _ORCHESTRATION_PATH.stat().st_mtime_ns
            if mtime_ns != _ORCHESTRATION_MTIME_NS:
                _ORCHESTRATION_CACHE = json.loads(
                    _ORCHESTRATION_PATH.read_text(encoding="utf-8")
                )
                _ORCHESTRATION_MTIME_NS = mtime_ns
                _NORMALIZED_CACHE = None
                _NORMALIZED_SOURCE = None
            return _ORCHESTRATION_CACHE
        except Exception:
            pass
    return {}


def normalize_orchestration(orch: dict | None = None) -> dict:
    """Expand nested peer profiles into a deterministic in-memory node tree.

    The tracked configuration stores physical/root peers only. Each
    ``hub_nodes[].profiles`` entry becomes a routable child named
    ``{peer_id}.{profile_name}``. The root peer itself is merged with its
    ``default_profile`` so legacy calls such as ``hub.py ask --to cx`` retain
    their stable identity while using an explicit model/profile.
    """
    global _NORMALIZED_CACHE, _NORMALIZED_SOURCE
    if orch and orch.get("_normalized") is True:
        return orch
    use_cache = orch is None
    if use_cache:
        raw = _load_orchestration()
        if _NORMALIZED_CACHE is not None and _NORMALIZED_SOURCE is raw:
            return _NORMALIZED_CACHE
    else:
        raw = orch or {}
    source = copy.deepcopy(raw)
    raw_nodes = source.get("hub_nodes", [])
    expanded: list[dict[str, Any]] = []

    for raw_node in raw_nodes:
        base = copy.deepcopy(raw_node)
        profiles = base.pop("profiles", {}) or {}
        default_profile = base.pop("default_profile", None)
        root = copy.deepcopy(base)

        if default_profile and default_profile in profiles:
            selected = copy.deepcopy(profiles[default_profile])
            root["profile_id"] = f"{root.get('node_id')}.{default_profile}"
            root["profile_name"] = default_profile
            for key in (
                "model_id", "runtime_model", "model_availability",
                "runtime_context_window", "validated_at", "validation_method",
                "routing_state", "profile_args", "capability_class",
                "reasoning_effort", "cost_tier",
            ):
                if key in selected:
                    root[key] = selected[key]
        expanded.append(root)

        root_id = root.get("node_id")
        if not root_id:
            continue
        for profile_name, profile in profiles.items():
            child = copy.deepcopy(base)
            child["node_id"] = f"{root_id}.{profile_name}"
            child["type"] = "profile"
            child["parent_node"] = root_id
            child["profile_id"] = child["node_id"]
            child["profile_name"] = profile_name
            child["aliases"] = list(profile.get("aliases", []))
            for key, value in profile.items():
                if key != "aliases":
                    child[key] = copy.deepcopy(value)
            expanded.append(child)

    source["hub_nodes"] = expanded
    source["_normalized"] = True
    if use_cache:
        _NORMALIZED_CACHE = source
        _NORMALIZED_SOURCE = raw
    return source


def profile_catalog(orch: dict | None = None) -> dict[str, dict[str, Any]]:
    """Return normalized profile metadata keyed by ``peer.profile``."""
    normalized = normalize_orchestration(orch)
    return {
        node["profile_id"]: {
            key: copy.deepcopy(value)
            for key, value in node.items()
            if key not in {"invoke_args", "aliases", "adapter_class", "requires_pty"}
        }
        for node in normalized.get("hub_nodes", [])
        if node.get("type") == "profile" and node.get("profile_id")
    }


def resolve_node_id(node_id: str | None, *, orch: dict | None = None) -> str | None:
    """Resolve a node ID, alias, or invoke name to its canonical node ID."""
    if not node_id or not isinstance(node_id, str):
        return None
    orch = normalize_orchestration(orch)
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
    orch = normalize_orchestration(orch)
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
        if (
            node is None
            or node.get("enabled") is False
            or node.get("routing_state") == "blocked"
        ):
            return False
        parent = _parent_node_id(node)
        if not parent:
            return True
        current = parent
    return False


def root_peer_id(node_id: str | None, *, orch: dict | None = None) -> str | None:
    """Return the physical root peer for a routable node tree."""
    orch = normalize_orchestration(orch)
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

    def build_session_cmd(
        self, node: dict[str, Any], query: str, session_id: str | None = None
    ) -> SessionInvocation:
        """Build a session-reuse (resume/new-session) invocation."""
        ...

    def session_fingerprint(self, node: dict[str, Any]) -> str:
        """Return a stable fingerprint of the static session invocation flags."""
        ...

    def extract_session_id(
        self, stdout: str, node: dict[str, Any], command_session_id: str | None
    ) -> str | None:
        """Resolve the session id to persist from stdout / the command id."""
        ...

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        """Extract the usable response text from raw subprocess stdout."""
        ...

    def context_policy(self, node: dict[str, Any]) -> ContextPolicy:
        """Return adapter-specific context-shaping policy."""
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
        cmd_args.extend(node.get("profile_args", []))
        return [invoke] + cmd_args, use_stdin

    # ── Session reuse contract ────────────────────────────────────────────────
    # Adapters that support hub-managed session reuse override these three
    # methods. The base raises so a misconfigured node (session_mode=reuse on a
    # peer with no reuse implementation) fails loudly instead of silently
    # dropping session state.

    def build_session_cmd(
        self, node: dict[str, Any], query: str, session_id: str | None = None
    ) -> SessionInvocation:
        raise RuntimeError(
            f"{node.get('node_id', self.node_id)} does not implement session reuse"
        )

    def session_fingerprint(self, node: dict[str, Any]) -> str:
        """Return a stable fingerprint of the static session invocation flags."""
        import hashlib
        import json
        fp_data = {
            "invoke": node.get("invoke", ""),
            "invoke_args": node.get("invoke_args", []),
            "profile_args": node.get("profile_args", [])
        }
        return hashlib.sha256(json.dumps(fp_data, sort_keys=True).encode("utf-8")).hexdigest()

    def extract_session_id(
        self, stdout: str, node: dict[str, Any], command_session_id: str | None
    ) -> str | None:
        return command_session_id

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()

    def context_policy(self, node: dict[str, Any]) -> ContextPolicy:
        """Default policy: empty preamble, room context always included,
        handoff unfiltered. Reproduces the current non-ag rendering exactly."""
        return ContextPolicy()


# ── Peer-specific adapters ────────────────────────────────────────────────────

class ClaudeAdapter(BaseAdapter):
    """Adapter for cc (Claude Code CLI)."""

    node_id = "cc"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "claude")
        invoke_path = Path(invoke)
        if (
            not invoke_path.is_absolute()
            and invoke_path.parts
            and invoke_path.parts[0].casefold() == "_sys"
        ):
            invoke = str((_SYS_DIR.parent / invoke_path).resolve())
        raw_args = node.get("invoke_args", ["-p", "{query}"])
        processed_args = []
        use_stdin = False
        for arg in raw_args:
            if arg == "{query}":
                processed_args.append("-")
                use_stdin = True
            else:
                processed_args.append(arg)
        return [invoke] + processed_args + node.get("profile_args", []), use_stdin

    def build_session_cmd(
        self, node: dict[str, Any], query: str, session_id: str | None = None
    ) -> SessionInvocation:
        effective_id = session_id or str(uuid.uuid4())
        cmd, use_stdin = self.build_cmd(node, query, session_id)
        
        # Inject --session-id flag if not present
        if "--session-id" not in cmd:
            cmd.extend(["--session-id", effective_id])
            
        return SessionInvocation(cmd, use_stdin, effective_id)

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        return stdout.strip()



class CodexAdapter(BaseAdapter):
    """Adapter for cx (OpenAI Codex CLI)."""

    node_id = "cx"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        return super().build_cmd(node, query, session_id)

    def build_session_cmd(
        self, node: dict[str, Any], query: str, session_id: str | None = None
    ) -> SessionInvocation:
        effective_id = session_id or str(uuid.uuid4())
        
        # Base arguments processing (similar to build_cmd)
        invoke = node.get("invoke", "codex")
        processed_args: list[str] = []
        use_stdin = False
        for arg in node.get("invoke_args", ["exec", "{query}"]):
            if arg == "{query}":
                processed_args.append("-")
                use_stdin = True
            else:
                processed_args.append(arg)
                
        # Inject resume if session_id exists
        if session_id:
            # invoke_args usually starts with ["exec", ...]
            # We need to rewrite "exec" -> "exec", "resume", <id>
            if processed_args and processed_args[0] == "exec":
                processed_args.insert(1, "resume")
                processed_args.insert(2, effective_id)
            else:
                # Fallback if exec is missing for some reason
                processed_args = ["resume", effective_id] + processed_args

        cmd = [invoke] + processed_args + node.get("profile_args", [])
        return SessionInvocation(cmd, use_stdin, effective_id)

    @staticmethod
    def _extract_jsonl_texts(raw: str) -> list[str]:
        """Extract assistant text from a codex --json JSONL event stream.

        Supported events:
          - {"type":"item.completed","item":{"text":"..."}}
          - {"type":"item.delta","item":{"type":"text","text":"..."}}
          - {"type":"message","role":"assistant","content":[{"type":"text",...}]}
          - flat {"text"|"content"|"message":"..."}
        Returns the deduped list of texts (empty if none parsed).
        """
        texts: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            t = obj.get("type", "")
            if t == "item.completed":
                item = obj.get("item", {})
                val = item.get("text") or item.get("content", "")
                if val:
                    texts.append(val)
            elif t == "item.delta":
                delta = obj.get("item", {})
                if delta.get("type") == "text":
                    val = delta.get("text", "")
                    if val:
                        texts.append(val)
            elif t == "message":
                role = obj.get("role", "")
                if role in ("assistant", ""):
                    content = obj.get("content", "")
                    if isinstance(content, str) and content:
                        texts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                val = block.get("text", "")
                                if val:
                                    texts.append(val)
            elif "text" in obj and obj["text"]:
                texts.append(obj["text"])
            elif "content" in obj and isinstance(obj["content"], str) and obj["content"]:
                texts.append(obj["content"])
            elif "message" in obj and isinstance(obj["message"], str) and obj["message"]:
                texts.append(obj["message"])
        seen: set[str] = set()
        return [t for t in texts if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

    def extract_session_id(
        self, stdout: str, node: dict[str, Any], command_session_id: str | None
    ) -> str | None:
        """Extract the codex thread_id from the thread.started event."""
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "thread.started":
                tid = obj.get("thread_id")
                if tid:
                    return str(tid)
        return command_session_id

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
        # Codex --json mode: adapter-owned parsing (moved from hub._extract_jsonl_text)
        if "--json" not in node.get("invoke_args", []):
            return stdout.strip()
        # 1. JSONL event stream (codex exec --json): item.completed / message events
        texts = self._extract_jsonl_texts(stdout)
        if texts:
            return "\n\n".join(texts).strip()
        # 2. Single-JSON {"messages":[...]} response shape
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
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            pass
        return stdout.strip()


_AGY_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_AGY_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
# Continuation/conversation flags the hub must never send to ag. session_mode
class AgyAdapter(BaseAdapter):
    """Adapter for ag (Antigravity / agy CLI — Gemini successor)."""

    node_id = "ag"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        invoke = node.get("invoke", "agy")
        invoke_path = Path(invoke)
        if (
            not invoke_path.is_absolute()
            and invoke_path.parts
            and invoke_path.parts[0].casefold() == "_sys"
        ):
            invoke = str((_SYS_DIR.parent / invoke_path).resolve())
        raw_args = node.get("invoke_args", ["--dangerously-skip-permissions", "-p", "{query}"])
        profile_args = node.get("profile_args", [])
        # agy -p takes the prompt inline (not via stdin); use _substitute_args to keep query in args
        return [invoke] + self._substitute_args(raw_args, query) + profile_args, False

    def build_session_cmd(
        self, node: dict[str, Any], query: str, session_id: str | None = None
    ) -> SessionInvocation:
        effective_id = session_id or str(uuid.uuid4())
        cmd, use_stdin = self.build_cmd(node, query, session_id)
        
        # Inject --conversation flag if not present
        if "--conversation" not in cmd:
            cmd.extend(["--conversation", effective_id])
            
        return SessionInvocation(cmd, use_stdin, effective_id)

    def context_policy(self, node: dict[str, Any]) -> ContextPolicy:
        """ag IPC context delta (A6): the agy model is context-fragile — it
        responds to the largest leading block, not a small trailing query. So
        ag gets the task FIRST (query_first) and NO injected room/handoff
        (skip_room_context); agy loads ambient repo context on its own. The IPC
        BOUNDARY preamble still leads. skip_room_context_when_complete and
        handoff_sections are retained for defence-in-depth but are subsumed by
        skip_room_context (which drops [HUB CONTEXT]/[HANDOFF] unconditionally)."""
        return ContextPolicy(
            preamble_lines=(
                "[IPC BOUNDARY]",
                "Treat [USER QUERY] as the only task.",
                "Do not read mailbox, handoff, summary, or prior-session files unless the user query explicitly requests them.",
                "Use only context included in this prompt.",
            ),
            query_first=True,
            skip_room_context=True,
            skip_room_context_when_complete=True,
            handoff_sections=(
                "GOAL",
                "PENDING_ISSUES",
                "KEY_DECISIONS",
            ),
        )

    def parse_output(self, stdout: str, node: dict[str, Any]) -> str:
        """Normalize a raw PTY terminal stream into plain text (A4).

        Models a single-line cursor: OSC/residual CSI are removed, ``\\r`` homes
        the cursor to column 0, ``\\b`` moves it left, ``CSI K``/``CSI 2K`` erase,
        and ordinary characters overwrite at the cursor so redraws collapse to the
        final rendered frame. Only outer whitespace is stripped.
        """
        text = _AGY_OSC_RE.sub("", stdout)
        lines_out: list[str] = []
        buf: list[str] = []
        col = 0
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b":
                if i + 1 < n and text[i + 1] == "[":
                    m = _AGY_CSI_RE.match(text, i)
                    if m:
                        seq = m.group(0)
                        final = seq[-1]
                        params = seq[2:-1]
                        if final == "K":
                            if params in ("", "0"):
                                del buf[col:]
                            elif params == "1":
                                for j in range(min(col, len(buf))):
                                    buf[j] = " "
                            elif params == "2":
                                buf = []
                                col = 0
                        i = m.end()
                        continue
                # lone or unmatched ESC: drop it
                i += 1
                continue
            if ch == "\r":
                col = 0
                i += 1
                continue
            if ch == "\b":
                if col > 0:
                    col -= 1
                i += 1
                continue
            if ch == "\n":
                lines_out.append("".join(buf))
                buf = []
                col = 0
                i += 1
                continue
            if col < len(buf):
                buf[col] = ch
            else:
                while len(buf) < col:
                    buf.append(" ")
                buf.append(ch)
            col += 1
            i += 1
        lines_out.append("".join(buf))
        return "\n".join(lines_out).strip()


class VirtualAdapter(BaseAdapter):
    """Compatibility adapter for generated profile nodes."""

    node_id = "virtual"

    def build_cmd(self, node: dict[str, Any], query: str, session_id: str | None = None) -> tuple[list[str], bool]:
        # Virtual nodes Typically inherit their base peer's behavior but with different flags
        return super().build_cmd(node, query, session_id)


# ── Adapter registry + factory ────────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "ClaudeAdapter": ClaudeAdapter,
    "AgyAdapter": AgyAdapter,
    "CodexAdapter": CodexAdapter,
    "VirtualAdapter": VirtualAdapter,
}

_INVOKE_TO_ADAPTER: dict[str, type[BaseAdapter]] = {
    "claude": ClaudeAdapter,
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
    orch = normalize_orchestration()
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
    orch = normalize_orchestration()
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
