"""Default console launch arguments for peer CLIs.

The wrappers keep peer consoles in full-autonomy mode by default, while still
letting a user pass explicit safety/approval flags to override that default.
"""
from __future__ import annotations

import json
from pathlib import Path


_ORCHESTRATION = Path(__file__).parent.parent / "ai" / "orchestration.json"


def _default_profile_args(peer_id: str) -> list[str]:
    """Profile args for interactive console launches (claude.bat etc).

    Prefers interactive_default_profile (typically "effort") over
    default_profile ("deepthink", used by hub.py IPC ask) — an interactive
    session has a human present to catch a bad answer, so it doesn't need the
    top tier by default. A per-session override (e.g. /model) still wins,
    since _append_profile_defaults never replaces an already-present flag.
    """
    try:
        data = json.loads(_ORCHESTRATION.read_text(encoding="utf-8"))
        node = next(
            item for item in data.get("hub_nodes", [])
            if item.get("node_id") == peer_id
        )
        prof = node.get("interactive_default_profile") or node.get("default_profile", "deepthink")
        return list(node.get("profiles", {}).get(prof, {}).get("profile_args", []))
    except (OSError, ValueError, StopIteration, TypeError):
        return []


def interactive_profile_banner(peer_id: str) -> str | None:
    """Human-readable 'launching as: {peer}.{profile} (--model ...)' label,
    or None if no profile is configured for this peer's console launch."""
    try:
        data = json.loads(_ORCHESTRATION.read_text(encoding="utf-8"))
        node = next(
            item for item in data.get("hub_nodes", [])
            if item.get("node_id") == peer_id
        )
        prof = node.get("interactive_default_profile") or node.get("default_profile", "deepthink")
        args = node.get("profiles", {}).get(prof, {}).get("profile_args", [])
        if "--model" not in args:
            return None
        model = args[args.index("--model") + 1]
        return f"[profile] {peer_id}.{prof} (--model {model}) — this session's default; override anytime with this CLI's own model switch"
    except (OSError, ValueError, StopIteration, TypeError, IndexError):
        return None


def _append_profile_defaults(args: list[str], peer_id: str) -> list[str]:
    defaults = _default_profile_args(peer_id)
    if not defaults:
        return args
    out = list(args)
    has_model = _has_flag(out, {"--model", "-m"})
    has_effort = _has_flag(out, {"--effort"}) or any(
        str(arg).startswith("model_reasoning_effort=") for arg in out
    )
    index = 0
    while index < len(defaults):
        item = defaults[index]
        value = defaults[index + 1] if index + 1 < len(defaults) else None
        if item in {"--model", "-m"} and value is not None:
            if not has_model:
                out.extend([item, value])
            index += 2
            continue
        if item == "--effort" and value is not None:
            if not has_effort:
                out.extend([item, value])
            index += 2
            continue
        if item == "-c" and value is not None:
            if not has_effort:
                out.extend([item, value])
            index += 2
            continue
        if item not in out:
            out.append(item)
        index += 1
    return out

def _has_flag(args: list[str], names: set[str]) -> bool:
    for arg in args:
        if arg in names:
            return True
        if any(arg.startswith(name + "=") for name in names):
            return True
    return False


def _append_missing(args: list[str], defaults: list[str]) -> list[str]:
    out = list(args)
    for item in defaults:
        if item not in out:
            out.append(item)
    return out


def _is_help_or_version(args: list[str]) -> bool:
    return any(arg in {"-h", "--help", "-v", "--version", "-V"} for arg in args)


def apply_security_semantics(cmd: list[str], security_contract: dict) -> list[str]:
    """Policy-to-CLI translation layer (design 2026-07-09 §Topic B): drives a
    peer's sandbox flags from its security_contract.sandbox_semantics
    declaration, so a peer whose required_effective_args is legitimately
    empty (e.g. cx, whose sandbox is declared via semantics rather than a
    literal arg list) still gets the right runtime flag applied."""
    semantics = security_contract.get("sandbox_semantics")
    if not semantics:
        return list(cmd)

    out = list(cmd)
    if semantics == "skip-permissions":
        eff_args = security_contract.get("required_effective_args") or []
        out = _append_missing(out, list(eff_args))
    elif semantics == "workspace-write":
        if not _has_flag(out, {
            "--dangerously-bypass-approvals-and-sandbox",
            "--sandbox",
            "-s",
            "--ask-for-approval",
            "-a",
        }):
            out = _append_missing(out, ["-s", "workspace-write"])
    return out


_CLAUDE_COMMANDS = {
    "agents", "auth", "auto-mode", "doctor", "install", "mcp", "plugin",
    "plugins", "project", "setup-token", "ultrareview", "update", "upgrade",
}

_GEMINI_COMMANDS = {"mcp", "extensions", "extension", "skills", "skill", "hooks", "hook", "gemma"}

_CODEX_COMMANDS = {
    "exec", "e", "review", "login", "logout", "mcp", "plugin", "mcp-server",
    "app-server", "remote-control", "app", "completion", "update", "doctor",
    "sandbox", "debug", "apply", "a", "resume", "archive", "unarchive",
    "fork", "cloud", "exec-server", "features", "help",
}

_AGY_COMMANDS = {"changelog", "help", "install", "models", "plugin", "plugins", "update"}


def _starts_with_command(args: list[str], commands: set[str]) -> bool:
    return bool(args) and not args[0].startswith("-") and args[0] in commands


def peer_default_args(peer_id: str, args: list[str]) -> list[str]:
    """Return argv with peer-specific full-autonomy defaults appended.

    Explicit user safety/approval flags win. Defaults are appended so positional
    prompts and subcommands keep their original order.
    """
    current = list(args)
    if _is_help_or_version(current):
        return current

    if peer_id == "cc":
        if _starts_with_command(current, _CLAUDE_COMMANDS):
            return current
        if not _has_flag(current, {
            "--dangerously-skip-permissions",
            "--allow-dangerously-skip-permissions",
            "--permission-mode",
            "--safe-mode",
            "--allowedTools",
            "--allowed-tools",
        }):
            current = _append_missing(current, ["--dangerously-skip-permissions"])
        return _append_profile_defaults(current, "cc")

    if peer_id == "gc":
        if _starts_with_command(current, _GEMINI_COMMANDS):
            return current
        if _has_flag(current, {"--approval-mode", "-y", "--yolo", "--sandbox", "-s"}):
            return current if "--skip-trust" in current else current + ["--skip-trust"]
        return _append_missing(current, ["--approval-mode", "auto_edit", "--skip-trust"])

    if peer_id == "cx":
        if _starts_with_command(current, _CODEX_COMMANDS):
            return current
        if not _has_flag(current, {
            "--dangerously-bypass-approvals-and-sandbox",
            "--sandbox",
            "-s",
            "--ask-for-approval",
            "-a",
        }):
            current = _append_missing(current, ["-s", "workspace-write"])
        return _append_profile_defaults(current, "cx")

    if peer_id == "ag":
        # ag is active and requires PTY routing on Windows. DIR-002 currently
        # keeps skip-permissions for non-interactive trusted IPC.
        if _starts_with_command(current, _AGY_COMMANDS):
            return current
        if not _has_flag(current, {"--dangerously-skip-permissions", "--sandbox"}):
            current = _append_missing(current, ["--dangerously-skip-permissions"])
        return _append_profile_defaults(current, "ag")

    return current
