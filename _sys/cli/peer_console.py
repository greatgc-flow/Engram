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


def _missing_profile_tokens(args: list[str], peer_id: str) -> list[str]:
    """Return the profile-default tokens not already present in args, as a
    flat list preserving (flag, value) pair grouping. Shared by
    _append_profile_defaults (append-at-end callers) and the cx root-scope
    insertion path (which needs the missing tokens without appending)."""
    defaults = _default_profile_args(peer_id)
    if not defaults:
        return []
    has_model = _has_flag(args, {"--model", "-m"})
    has_effort = _has_flag(args, {"--effort"}) or any(
        str(arg).startswith("model_reasoning_effort=") for arg in args
    )
    missing: list[str] = []
    index = 0
    while index < len(defaults):
        item = defaults[index]
        value = defaults[index + 1] if index + 1 < len(defaults) else None
        if item in {"--model", "-m"} and value is not None:
            if not has_model:
                missing.extend([item, value])
            index += 2
            continue
        if item == "--effort" and value is not None:
            if not has_effort:
                missing.extend([item, value])
            index += 2
            continue
        if item == "-c" and value is not None:
            if not has_effort:
                missing.extend([item, value])
            index += 2
            continue
        if item not in args and item not in missing:
            missing.append(item)
        index += 1
    return missing


def _append_profile_defaults(args: list[str], peer_id: str) -> list[str]:
    missing = _missing_profile_tokens(args, peer_id)
    return list(args) + missing if missing else args


def _has_flag(args: list[str], names: set[str]) -> bool:
    for arg in args:
        if arg in names:
            return True
        if any(arg.startswith(name + "=") for name in names):
            return True
        # Concatenated short-flag form (e.g. "-sread-only" for "-s", "-anever"
        # for "-a") — live-verified accepted by the real codex CLI. Only
        # applies to genuine 2-char short flags to avoid false-matching an
        # unrelated long option that happens to share a prefix.
        if any(
            len(name) == 2 and name.startswith("-") and not name.startswith("--")
            and arg.startswith(name) and arg != name
            for name in names
        ):
            return True
    return False


def _append_missing(args: list[str], defaults: list[str]) -> list[str]:
    """Append default flags to args if the flag token itself is missing.

    Evaluates flag-value pairs (e.g. ['-s', 'workspace-write']) atomically based
    on the presence of the flag token, preventing a bare positional string value
    from falsely suppressing default flag insertion.
    """
    out = list(args)
    i = 0
    while i < len(defaults):
        item = defaults[i]
        if item.startswith("-") and i + 1 < len(defaults) and not defaults[i + 1].startswith("-"):
            val = defaults[i + 1]
            if not _has_flag(out, {item}):
                out.extend([item, val])
            i += 2
        else:
            if not _has_flag(out, {item}):
                out.append(item)
            i += 1
    return out


def _consumes_next_value(token: str) -> bool:
    """Heuristic for "this flag-like token takes a following value" — same
    convention already used by _append_missing's pairing logic: a flag
    token followed by a non-flag-looking token is treated as a pair."""
    return token.startswith("-") and "=" not in token


def _insert_root_flags(args: list[str], flags: list[str], agent_commands: set[str] | None = None) -> list[str]:
    """Insert default flags at root scope (before the subcommand or first
    positional prompt), value-aware so an existing (flag, value) pair like
    ['--model', 'gpt-5'] is never split apart and a value that happens to
    equal an agent-command name (e.g. '--model exec') is never
    misidentified as the subcommand itself.

    Codex CLI requires root options like '-s workspace-write' to precede the
    subcommand token; callers are responsible for excluding anything at/after
    a literal '--' terminator (see _split_terminator) before calling this.
    """
    out = list(args)
    insert_idx = len(out)
    i = 0
    while i < len(out):
        arg = out[i]
        if agent_commands and arg in agent_commands:
            insert_idx = i
            break
        if arg.startswith("-"):
            if _consumes_next_value(arg) and i + 1 < len(out) and not out[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue
        insert_idx = i
        break

    out[insert_idx:insert_idx] = flags
    return out


def _split_terminator(args: list[str]) -> tuple[list[str], list[str]]:
    """Split argv at the first literal '--' option terminator. Everything
    from '--' onward (inclusive) is positional per POSIX/clap convention and
    must never be scanned for flags or have defaults inserted into it —
    live-verified against codex.cmd (a trailing --help after '--' is passed
    through literally, not interpreted)."""
    if "--" in args:
        idx = args.index("--")
        return args[:idx], args[idx:]
    return list(args), []


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
            # Append, not root-scope insert: this function has no production
            # caller today and is peer-agnostic, whereas the root-scope
            # requirement was empirically verified only for codex's CLI
            # grammar (see peer_default_args' cx branch). Generalizing an
            # unverified assumption here risks producing invalid syntax for
            # whichever peer eventually wires this in.
            out = _append_missing(out, ["-s", "workspace-write"])
    return out


_CLAUDE_COMMANDS = {
    "agents", "auth", "auto-mode", "doctor", "install", "mcp", "plugin",
    "plugins", "project", "setup-token", "ultrareview", "update", "upgrade",
}

_GEMINI_COMMANDS = {"mcp", "extensions", "extension", "skills", "skill", "hooks", "hook", "gemma"}

# C8-A Split: Agent-launching commands that need security & profile defaults vs. pure administrative/service commands.
_CODEX_AGENT_COMMANDS = {
    "exec", "e", "review", "resume", "fork",
}

_CODEX_ADMIN_COMMANDS = {
    "login", "logout", "mcp", "plugin", "mcp-server", "app-server",
    "remote-control", "app", "completion", "update", "doctor", "sandbox",
    "debug", "apply", "a", "archive", "unarchive", "cloud", "exec-server",
    "features", "help", "delete",
}

_AGY_COMMANDS = {"changelog", "help", "install", "models", "plugin", "plugins", "update"}


def _starts_with_command(args: list[str], commands: set[str]) -> bool:
    return bool(args) and not args[0].startswith("-") and args[0] in commands


def peer_default_args(peer_id: str, args: list[str]) -> list[str]:
    """Return argv with peer-specific full-autonomy defaults appended.

    Explicit user safety/approval flags win. Defaults are placed appropriately
    for CLI grammar. Anything at/after a literal '--' terminator is left
    completely untouched (never scanned, never a defaults-insertion target).
    """
    head, tail = _split_terminator(list(args))
    if _is_help_or_version(head):
        return head + tail

    if peer_id == "cc":
        if _starts_with_command(head, _CLAUDE_COMMANDS):
            return head + tail
        if not _has_flag(head, {
            "--dangerously-skip-permissions",
            "--allow-dangerously-skip-permissions",
            "--permission-mode",
            "--safe-mode",
            "--allowedTools",
            "--allowed-tools",
        }):
            head = _append_missing(head, ["--dangerously-skip-permissions"])
        return _append_profile_defaults(head, "cc") + tail

    if peer_id == "gc":
        if _starts_with_command(head, _GEMINI_COMMANDS):
            return head + tail
        if _has_flag(head, {"--approval-mode", "-y", "--yolo", "--sandbox", "-s"}):
            result = head if "--skip-trust" in head else head + ["--skip-trust"]
            return result + tail
        return _append_missing(head, ["--approval-mode", "auto_edit", "--skip-trust"]) + tail

    if peer_id == "cx":
        # Pure administrative commands bypass defaults entirely
        if _starts_with_command(head, _CODEX_ADMIN_COMMANDS):
            return head + tail

        # Agent-launching commands (exec, review, resume, fork) AND a plain
        # root prompt both need every default inserted at the SAME root-scope
        # point, in one pass — codex rejects '--model'/'-c ...' appended
        # after the subcommand exactly like it rejects '-s workspace-write'
        # there (live-verified: 'codex review --uncommitted --model X' exits
        # 2 with "unexpected argument '--model'"). Appending profile defaults
        # separately at the end (the old behavior) reintroduces that bug.
        missing: list[str] = []
        if not _has_flag(head, {
            "--dangerously-bypass-approvals-and-sandbox",
            "--sandbox",
            "-s",
            "--ask-for-approval",
            "-a",
        }):
            missing.extend(["-s", "workspace-write"])
        missing.extend(_missing_profile_tokens(head, "cx"))
        if missing:
            head = _insert_root_flags(head, missing, agent_commands=_CODEX_AGENT_COMMANDS)
        return head + tail

    if peer_id == "ag":
        # ag is active and requires PTY routing on Windows. DIR-002 currently
        # keeps skip-permissions for non-interactive trusted IPC.
        if _starts_with_command(head, _AGY_COMMANDS):
            return head + tail
        if not _has_flag(head, {"--dangerously-skip-permissions", "--sandbox"}):
            head = _append_missing(head, ["--dangerously-skip-permissions"])
        return _append_profile_defaults(head, "ag") + tail

    return head + tail
