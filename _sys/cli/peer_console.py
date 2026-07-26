"""Default console launch arguments for peer CLIs.

The wrappers keep peer consoles in full-autonomy mode by default, while still
letting a user pass explicit safety/approval flags to override that default.

Cluster C8-B: Unified prepare_console_launch API, InvocationKind classification,
runtime forbidden_effective_args enforcement, and truthful model/profile banners.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


_ORCHESTRATION = Path(__file__).parent.parent / "ai" / "orchestration.json"


class SecurityValidationError(ValueError):
    """Raised when an illegal or forbidden security override argument is passed without break-glass permission."""
    pass


class InvocationKind(Enum):
    HELP_OR_VERSION = "help_or_version"
    LOCAL_AGENT = "local_agent"        # exec/e, review, resume, fork, nested exec review/resume, interactive root
    REMOTE_AGENT = "remote_agent"      # cloud, cloud exec -- local sandbox flags don't govern remote workers
    ADMIN_OR_SERVICE = "admin_or_service"  # login/logout, mcp, app-server, delete, doctor, completion, etc.


@dataclass(frozen=True)
class ConsoleLaunch:
    peer_id: str
    invocation_kind: InvocationKind
    final_argv: list[str]
    effective_model: str | None
    effective_profile: str  # e.g. "cx.effort" or "cx.custom" if explicit model doesn't match a configured profile
    banner_message: str | None  # None for HELP_OR_VERSION/ADMIN_OR_SERVICE


_CLAUDE_COMMANDS = {
    "agents", "auth", "auto-mode", "doctor", "install", "mcp", "plugin",
    "plugins", "project", "setup-token", "ultrareview", "update", "upgrade",
}

_GEMINI_COMMANDS = {"mcp", "extensions", "extension", "skills", "skill", "hooks", "hook", "gemma"}

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


def _default_profile_args(peer_id: str) -> list[str]:
    """Profile args for interactive console launches (claude.bat etc)."""
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


def _missing_profile_tokens(args: list[str], peer_id: str) -> list[str]:
    """Return the profile-default tokens not already present in args."""
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
        if any(
            len(name) == 2 and name.startswith("-") and not name.startswith("--")
            and arg.startswith(name) and arg != name
            for name in names
        ):
            return True
    return False


def _append_missing(args: list[str], defaults: list[str]) -> list[str]:
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
    return token.startswith("-") and "=" not in token


def _insert_root_flags(args: list[str], flags: list[str], agent_commands: set[str] | None = None) -> list[str]:
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
    if "--" in args:
        idx = args.index("--")
        return args[:idx], args[idx:]
    return list(args), []


def _is_help_or_version(args: list[str]) -> bool:
    return any(arg in {"-h", "--help", "-v", "--version", "-V"} for arg in args)


def _starts_with_command(args: list[str], commands: set[str]) -> bool:
    return bool(args) and not args[0].startswith("-") and args[0] in commands


def _classify_invocation(peer_id: str, head: list[str]) -> InvocationKind:
    if _is_help_or_version(head):
        return InvocationKind.HELP_OR_VERSION

    if peer_id == "cx":
        if not head:
            return InvocationKind.LOCAL_AGENT
        cmd = head[0]
        if cmd == "cloud" or (len(head) > 1 and head[0] in {"cx", "codex"} and head[1] == "cloud"):
            return InvocationKind.REMOTE_AGENT
        if cmd in _CODEX_ADMIN_COMMANDS:
            return InvocationKind.ADMIN_OR_SERVICE
        return InvocationKind.LOCAL_AGENT

    if peer_id == "cc":
        if _starts_with_command(head, _CLAUDE_COMMANDS):
            return InvocationKind.ADMIN_OR_SERVICE
        return InvocationKind.LOCAL_AGENT

    if peer_id == "ag":
        if _starts_with_command(head, _AGY_COMMANDS):
            return InvocationKind.ADMIN_OR_SERVICE
        return InvocationKind.LOCAL_AGENT

    if peer_id == "gc":
        if _starts_with_command(head, _GEMINI_COMMANDS):
            return InvocationKind.ADMIN_OR_SERVICE
        return InvocationKind.LOCAL_AGENT

    return InvocationKind.LOCAL_AGENT


def _extract_effective_model(args: list[str]) -> str | None:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--model", "-m", "--model_id"}:
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                return args[i + 1]
        for flag in ("--model=", "-m=", "--model_id="):
            if arg.startswith(flag):
                return arg[len(flag):]
        i += 1
    return None


def _resolve_profile_and_model(peer_id: str, final_argv: list[str]) -> tuple[str | None, str]:
    effective_model = _extract_effective_model(final_argv)

    node_profiles: dict[str, dict] = {}
    default_profile_name = "deepthink"
    try:
        data = json.loads(_ORCHESTRATION.read_text(encoding="utf-8"))
        node = next(item for item in data.get("hub_nodes", []) if item.get("node_id") == peer_id)
        default_profile_name = node.get("interactive_default_profile") or node.get("default_profile", "deepthink")
        node_profiles = node.get("profiles", {})
    except Exception:
        pass

    if effective_model is None:
        prof_dict = node_profiles.get(default_profile_name, {})
        prof_args = prof_dict.get("profile_args", [])
        effective_model = _extract_effective_model(prof_args) or prof_dict.get("model_id")
        return effective_model, f"{peer_id}.{default_profile_name}"

    for prof_name, prof_dict in node_profiles.items():
        prof_args = prof_dict.get("profile_args", [])
        prof_model = _extract_effective_model(prof_args) or prof_dict.get("model_id")
        if prof_model and prof_model == effective_model:
            return effective_model, f"{peer_id}.{prof_name}"

    return effective_model, f"{peer_id}.custom"


_DANGEROUS_VALUE_FLAGS = {"-s", "--sandbox", "--approval-mode", "-a", "--ask-for-approval"}


def _check_forbidden_args(peer_id: str, final_head: list[str]) -> None:
    """Reject a dangerous flag/value pair unless break-glass is set.

    Only matches genuine FLAG usage (a token starting with '-', or the value
    immediately following a known sandbox/approval-mode flag) -- never a bare
    positional argument. Scanning every token indiscriminately (an earlier
    draft's approach) false-positived on completely innocuous prompt text
    that happened to equal a dangerous keyword, e.g. `codex exec "yolo"`.

    Callers must pass only the pre-'--' head, never the terminator tail --
    independent cross-verification found that scanning the tail too
    false-positived on legitimate prompt text starting with a dash placed
    after a literal '--' (e.g. `codex exec -- -yolo`), which is positional
    per POSIX/clap convention and must never be treated as a flag.

    -a/--ask-for-approval is a dangerous-VALUE flag (not just -s/--sandbox/
    --approval-mode): independent cross-verification found that omitting it
    let `exec -a danger-full-access` both bypass this check (the value
    was scanned as an unmonitored bare positional) AND suppress the
    -s workspace-write default insertion in prepare_console_launch (since
    _has_flag saw -a present and assumed an explicit safe choice).
    """
    if os.environ.get("ALLOW_BREAK_GLASS_DANGER_ACCESS") == "1":
        return
    final_argv = final_head

    dangers = {"dangerously-bypass-approvals-and-sandbox", "danger-full-access", "yolo", "full-auto"}
    try:
        data = json.loads(_ORCHESTRATION.read_text(encoding="utf-8"))
        node = next(item for item in data.get("hub_nodes", []) if item.get("node_id") == peer_id)
        sec = node.get("security_contract", {})
        for item in sec.get("forbidden_effective_args", []):
            dangers.add(str(item).lstrip("-"))
    except Exception:
        pass

    for i, arg in enumerate(final_argv):
        if arg.startswith("-"):
            flag_part, _, value_part = arg.partition("=")
            clean_flag = flag_part.lstrip("-")
            if clean_flag in dangers:
                raise SecurityValidationError(
                    f"Forbidden security argument '{arg}' in final_argv for peer '{peer_id}' (break-glass disabled)"
                )
            if value_part and flag_part in _DANGEROUS_VALUE_FLAGS and value_part in dangers:
                raise SecurityValidationError(
                    f"Forbidden security argument '{arg}' in final_argv for peer '{peer_id}' (break-glass disabled)"
                )
            # Concatenated short-flag form, e.g. "-sdanger-full-access".
            for d in dangers:
                if len(arg) > 2 and arg[:2] in _DANGEROUS_VALUE_FLAGS and arg[2:] == d:
                    raise SecurityValidationError(
                        f"Forbidden security argument '{arg}' in final_argv for peer '{peer_id}' (break-glass disabled)"
                    )
            continue
        if i > 0 and final_argv[i - 1] in _DANGEROUS_VALUE_FLAGS and arg in dangers:
            raise SecurityValidationError(
                f"Forbidden security value '{arg}' for '{final_argv[i - 1]}' for peer '{peer_id}' (break-glass disabled)"
            )


def prepare_console_launch(peer_id: str, args: list[str]) -> ConsoleLaunch:
    """Classify invocation, apply security & profile defaults, validate forbidden args,
    and return structured ConsoleLaunch with truthful model/profile banner."""
    head, tail = _split_terminator(list(args))
    kind = _classify_invocation(peer_id, head)

    if kind == InvocationKind.HELP_OR_VERSION:
        return ConsoleLaunch(
            peer_id=peer_id,
            invocation_kind=kind,
            final_argv=head + tail,
            effective_model=None,
            effective_profile=f"{peer_id}.none",
            banner_message=None,
        )

    if kind == InvocationKind.ADMIN_OR_SERVICE:
        return ConsoleLaunch(
            peer_id=peer_id,
            invocation_kind=kind,
            final_argv=head + tail,
            effective_model=None,
            effective_profile=f"{peer_id}.admin",
            banner_message=None,
        )

    if kind == InvocationKind.REMOTE_AGENT:
        # No profile-default insertion here (unlike LOCAL_AGENT): independent
        # cross-verification found real `codex cloud exec --help` does not
        # accept --model at all ("error: unexpected argument '--model' found"
        # against the real installed binary) -- appending it would hard-crash
        # every real remote-agent invocation. Local sandbox flags don't apply
        # to a remote worker either, so REMOTE_AGENT gets forbidden-arg
        # enforcement only, no defaults inserted.
        final_argv = head + tail
        _check_forbidden_args(peer_id, head)
        eff_model, eff_prof = _resolve_profile_and_model(peer_id, final_argv)
        banner = (
            f"[remote-profile] {eff_prof} (--model {eff_model}) — remote worker launch"
            if eff_model else f"[remote-profile] {eff_prof} — remote worker launch"
        )
        return ConsoleLaunch(
            peer_id=peer_id,
            invocation_kind=kind,
            final_argv=final_argv,
            effective_model=eff_model,
            effective_profile=eff_prof,
            banner_message=banner,
        )

    # LOCAL_AGENT
    final_head = list(head)
    if peer_id == "cx":
        missing: list[str] = []
        if not _has_flag(final_head, {
            "--dangerously-bypass-approvals-and-sandbox",
            "--sandbox",
            "-s",
            "--ask-for-approval",
            "-a",
        }):
            missing.extend(["-s", "workspace-write"])
        missing.extend(_missing_profile_tokens(final_head, "cx"))
        if missing:
            final_head = _insert_root_flags(final_head, missing, agent_commands=_CODEX_AGENT_COMMANDS)

    elif peer_id == "cc":
        if not _has_flag(final_head, {
            "--dangerously-skip-permissions",
            "--allow-dangerously-skip-permissions",
            "--permission-mode",
            "--safe-mode",
            "--allowedTools",
            "--allowed-tools",
        }):
            final_head = _append_missing(final_head, ["--dangerously-skip-permissions"])
        final_head = _append_profile_defaults(final_head, "cc")

    elif peer_id == "ag":
        if not _has_flag(final_head, {"--dangerously-skip-permissions", "--sandbox"}):
            final_head = _append_missing(final_head, ["--dangerously-skip-permissions"])
        final_head = _append_profile_defaults(final_head, "ag")

    elif peer_id == "gc":
        if _has_flag(final_head, {"--approval-mode", "-y", "--yolo", "--sandbox", "-s"}):
            final_head = final_head if "--skip-trust" in final_head else final_head + ["--skip-trust"]
        else:
            final_head = _append_missing(final_head, ["--approval-mode", "auto_edit", "--skip-trust"])

    final_argv = final_head + tail
    _check_forbidden_args(peer_id, final_head)
    eff_model, eff_prof = _resolve_profile_and_model(peer_id, final_argv)
    banner = (
        f"[profile] {eff_prof} (--model {eff_model}) — this session's default; override anytime with this CLI's own model switch"
        if eff_model else f"[profile] {eff_prof}"
    )

    return ConsoleLaunch(
        peer_id=peer_id,
        invocation_kind=kind,
        final_argv=final_argv,
        effective_model=eff_model,
        effective_profile=eff_prof,
        banner_message=banner,
    )


def peer_default_args(peer_id: str, args: list[str]) -> list[str]:
    """Compatibility wrapper that calls prepare_console_launch and returns final_argv."""
    return prepare_console_launch(peer_id, args).final_argv


def interactive_profile_banner(peer_id: str) -> str | None:
    """Compatibility wrapper that calls prepare_console_launch with empty args."""
    return prepare_console_launch(peer_id, []).banner_message


def apply_security_semantics(cmd: list[str], security_contract: dict) -> list[str]:
    """Policy-to-CLI translation layer (design 2026-07-09 §Topic B)."""
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
