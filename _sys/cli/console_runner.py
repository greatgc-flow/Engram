"""console_runner.py — Interactive AI-CLI console launcher.

Engram owns *interactive, user-launched* AI CLI sessions: argument
classification, banner, process spawn/wait, and exit-code translation.
It does not own peer coordination — dispatch, sessions, health, leases,
and telemetry belong to the separately-installed `peerhub` package.

1-way dependency:
argv + config -> prepare_console_launch() (C8) -> immutable ConsoleLaunch -> spawn/wait.
"""
from __future__ import annotations

import os
import subprocess
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from peer_console import ConsoleLaunch, InvocationKind, prepare_console_launch

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent


@dataclass(frozen=True)
class ConsoleSessionSpec:
    peer_id: str
    cmd_prefix: list[str]
    env: dict[str, str]
    cwd: str | Path | None = None
    # Peers disagreed on whether Ctrl+C is a successful exit: cx/cc treat
    # exit 130 as success, ag historically treated it as a failure. Kept as
    # a per-peer knob so agy_entry.py can preserve its own convention.
    keyboard_interrupt_is_success: bool = True


@dataclass(frozen=True)
class ConsoleResult:
    exit_code: int
    launch: ConsoleLaunch
    error: Exception | None = None


def run_console_session(
    spec: ConsoleSessionSpec,
    user_argv: list[str],
    _popen_runner: Callable[..., Any] | None = None,
) -> ConsoleResult:
    """Launch one interactive AI CLI session and wait for it to exit."""
    launch = prepare_console_launch(spec.peer_id, user_argv)

    if launch.banner_message:
        print(launch.banner_message)

    full_cmd = spec.cmd_prefix + launch.final_argv
    cwd_str = str(spec.cwd) if spec.cwd else None

    exit_code = 1

    # New process group on Windows: without this, the real CLI child shares
    # this wrapper's console/process group with every ancestor (the launching
    # cmd.exe, this python wrapper). A single Ctrl+C reaching the console then
    # hits all of them simultaneously -- the outer cmd.exe pops "Terminate
    # batch job (Y/N)?" and kills this whole session, regardless of where the
    # interrupt actually came from. Isolating the child's process group stops
    # one interrupt from cascading through every layer at once. Trade-off:
    # the child no longer receives this console's Ctrl+C automatically --
    # acceptable here since Claude Code's own interrupt is ESC-based, not
    # Ctrl+C (user-confirmed 2026-08-05, not otherwise relied on).
    popen_kwargs: dict = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        if _popen_runner:
            proc = _popen_runner(full_cmd, env=spec.env, cwd=cwd_str, **popen_kwargs)
        else:
            proc = subprocess.Popen(full_cmd, env=spec.env, cwd=cwd_str, **popen_kwargs)

        if hasattr(proc, "wait"):
            proc.wait()
            exit_code = getattr(proc, "returncode", 0)
        else:
            exit_code = 0

    except KeyboardInterrupt:
        exit_code = 130
    except Exception as e:
        print(f"[{spec.peer_id}_entry] error: {e}", file=sys.stderr)
        exit_code = 1

    return ConsoleResult(exit_code=exit_code, launch=launch)
