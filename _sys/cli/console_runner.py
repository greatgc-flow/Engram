"""console_runner.py — Unified console session runner with C5 lease lifecycle.

Cluster S3: Step 3 of 3 (Console-side adoption).
Enforces 1-way dependency:
argv + config -> prepare_console_launch() (C8) -> immutable ConsoleLaunch -> C5 lease lifecycle -> spawn/wait.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from peer_console import ConsoleLaunch, InvocationKind, prepare_console_launch

_CLI_DIR = Path(__file__).parent
_SYS_DIR = _CLI_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

_VENV_PY = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
_HUB = _SYS_DIR / "core" / "hub.py"
_PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


@dataclass(frozen=True)
class ConsoleSessionSpec:
    peer_id: str
    cmd_prefix: list[str]
    env: dict[str, str]
    cwd: str | Path | None = None
    context_fill_frame: bool = False
    health_json_path: Path | None = None
    heartbeat_interval_sec: float = 300.0  # 5 minutes default; unit tests can pass lower value
    # Independent cross-verification found peers had DIFFERENT pre-migration
    # Ctrl+C conventions: cx/codex's original code never explicitly marked
    # health RED for exit_code 130, but ag's original code always did
    # ("final_status = GREEN if exit_code == 0 else RED", unconditionally,
    # so 130 -> RED). A single hardcoded (0, 130)-is-success rule silently
    # regressed ag's behavior. Defaults to the cx/cc-compatible convention;
    # agy_entry.py overrides this to preserve its own original behavior.
    keyboard_interrupt_is_success: bool = True


@dataclass(frozen=True)
class ConsoleResult:
    exit_code: int
    launch: ConsoleLaunch
    lease_id: str | None
    lease_claimed: bool
    error: Exception | None = None


def should_claim_lease(kind: InvocationKind) -> bool:
    """Exhaustive lease-duty mapping.

    LOCAL_AGENT: claims + renews
    REMOTE_AGENT: claims + renews
    HELP_OR_VERSION: no lease (zero friction)
    ADMIN_OR_SERVICE: no lease (zero friction)

    Fails loudly if an unmapped InvocationKind is encountered.
    """
    if kind in (InvocationKind.LOCAL_AGENT, InvocationKind.REMOTE_AGENT):
        return True
    elif kind in (InvocationKind.HELP_OR_VERSION, InvocationKind.ADMIN_OR_SERVICE):
        return False
    else:
        raise ValueError(f"Unhandled InvocationKind in lease duty mapping: {kind}")


def _run_hub_action(args: list[str], env: dict[str, str], capture_output: bool = True, text: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [_PYTHON, str(_HUB)] + args
    return subprocess.run(cmd, capture_output=capture_output, text=text, env=env)


def _update_peer_health_json(spec: ConsoleSessionSpec, exit_code: int, duration_ms: int, pid: int | None, stage: str) -> None:
    if not spec.health_json_path or not spec.health_json_path.exists():
        return
    try:
        data = json.loads(spec.health_json_path.read_text(encoding="utf-8"))
        avail = data.setdefault("availability", {})
        if spec.peer_id == "cx":
            # Independent cross-verification found this wrote a synthetic
            # duration=0/success record at "start" too (the original
            # pre-migration code only wrote invocation metrics once, after
            # actual completion) -- a hard-killed wrapper could leave a
            # false successful-invocation record. Only write at "finish".
            if stage == "finish":
                success = exit_code == 0 or (exit_code == 130 and spec.keyboard_interrupt_is_success)
                avail["last_invocation_duration_ms"] = duration_ms
                avail["last_invocation_exit_code"] = 0 if success else 1
        elif spec.peer_id == "ag":
            if stage == "start" and pid is not None:
                avail["active_pid"] = pid
            elif stage == "finish":
                avail.pop("active_pid", None)
        spec.health_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[CLI] Warning: failed to update health.json for {spec.peer_id}: {exc}", file=sys.stderr)


def _claim_terminal_lease(spec: ConsoleSessionSpec, kind: InvocationKind) -> tuple[str | None, str | None]:
    """Attempts to claim a terminal lease via hub terminal-handoff.

    Returns (lease_id, error_message).
    """
    reason = f"console_launch_{kind.value}"
    res = _run_hub_action(
        ["terminal-handoff", "--agent", "unknown", "--peer", spec.peer_id, "--reason", reason],
        env=spec.env,
    )
    if res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip() or f"exit code {res.returncode}"
        return None, err

    # Parse the lease_id from THIS specific subprocess call's own stdout
    # first -- it's guaranteed to be the lease just minted by this exact
    # handoff. Independent cross-verification found the state.json-first
    # ordering could adopt an unrelated or already-closed lease (e.g. a
    # stale same-peer assignment from an earlier, unrelated session) if a
    # concurrent handoff raced this read; state.json is only a fallback if
    # the stdout parse somehow fails.
    lease_id = None
    for line in res.stdout.splitlines():
        if "lease=" in line:
            parts = line.split("lease=")
            if len(parts) > 1:
                lease_id = parts[1].split()[0]
                break

    if not lease_id:
        state_file = _PORTABLE_ROOT / ".ai" / "state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                assignment = state.get("human_interface_assignment")
                if isinstance(assignment, dict) and assignment.get("peer") == spec.peer_id:
                    lease_id = assignment.get("lease_id")
            except Exception:
                pass

    if not lease_id:
        return None, "Failed to resolve lease_id from terminal-handoff response"

    return lease_id, None


def _renew_heartbeat(spec: ConsoleSessionSpec, lease_id: str, owner_pid: int) -> tuple[bool, str]:
    """Runs a single heartbeat renewal call to hub terminal-heartbeat.

    Returns (success, reason).
    """
    res = _run_hub_action(
        ["terminal-heartbeat", "--peer", spec.peer_id, "--lease-id", lease_id, "--pid", str(owner_pid)],
        env=spec.env,
    )
    output = res.stdout + "\n" + res.stderr
    if res.returncode == 0:
        return True, "ok"
    if "CAS rejection" in output or "stale lease" in output:
        return False, "cas_rejection"
    return False, "transient_failure"


def run_console_session(
    spec: ConsoleSessionSpec,
    user_argv: list[str],
    _popen_runner: Callable[..., Any] | None = None,
) -> ConsoleResult:
    """Executes a console session adhering to C8 security classification & C5 lease management.

    1-way dependency guaranteed:
    user_argv -> prepare_console_launch() (C8) -> ConsoleLaunch -> Lease Lifecycle -> Spawn/Wait.
    """
    # 1. C8 Security prep
    launch = prepare_console_launch(spec.peer_id, user_argv)

    # 2. Pre-launch hub initialization
    _run_hub_action(["init-session", "--agent", spec.peer_id], env=spec.env)
    _run_hub_action(["health-update", "--peer", spec.peer_id, "--status", "GREEN"], env=spec.env)

    fill_args = ["context-fill"]
    if spec.context_fill_frame:
        fill_args.append("--frame")
    fill = _run_hub_action(fill_args, env=spec.env)
    if fill.stdout and fill.stdout.strip():
        print(fill.stdout.strip())

    _run_hub_action(["status"], env=spec.env, capture_output=False)

    # 3. Lease Duty Determination
    needs_lease = should_claim_lease(launch.invocation_kind)
    lease_id: str | None = None
    lease_claimed = False

    if needs_lease:
        lease_id, claim_err = _claim_terminal_lease(spec, launch.invocation_kind)
        if lease_id:
            lease_claimed = True
        else:
            allow_unleased = os.environ.get("ALLOW_UNLEASED_CONSOLE") == "1"
            if not allow_unleased:
                print(
                    f"[console_runner:ERROR] Terminal lease claim failed for peer '{spec.peer_id}': {claim_err}. "
                    f"Aborting launch (set ALLOW_UNLEASED_CONSOLE=1 to break glass).",
                    file=sys.stderr,
                )
                return ConsoleResult(
                    exit_code=1,
                    launch=launch,
                    lease_id=None,
                    lease_claimed=False,
                    error=RuntimeError(f"Lease claim failed: {claim_err}"),
                )
            else:
                print(
                    f"[console_runner:WARN] Terminal lease claim failed ({claim_err}), "
                    f"proceeding degraded without lease due to ALLOW_UNLEASED_CONSOLE=1.",
                    file=sys.stderr,
                )

    # 4. Background Heartbeat Thread
    #
    # Independent cross-verification found a real, reproducible HIGH-severity
    # race: the retry loop used an uninterruptible time.sleep(1.0) between
    # attempts, and shutdown only joined the thread for 2.0s before
    # proceeding to terminal-close regardless -- a heartbeat call could land
    # (and succeed) AFTER terminal-close already ran, since hub.py's CAS
    # check only compares lease_id, not close_reason/expiry, effectively
    # reviving a just-closed lease. Fixed with a lock shared between every
    # heartbeat attempt and the final terminal-close call: close cannot run
    # while a heartbeat call is in flight (blocks on the lock), and once
    # close acquires the lock, the loop's stop_heartbeat.is_set() check
    # (re-checked immediately after acquiring the lock, not just before)
    # guarantees no new heartbeat call starts afterward. The retry delay is
    # now an interruptible stop_heartbeat.wait() instead of a blind sleep.
    stop_heartbeat = threading.Event()
    heartbeat_call_lock = threading.Lock()
    heartbeat_thread: threading.Thread | None = None
    owner_pid = os.getpid()

    if lease_claimed and lease_id:
        def heartbeat_loop():
            interval = spec.heartbeat_interval_sec
            while not stop_heartbeat.wait(timeout=interval):
                if stop_heartbeat.is_set():
                    break
                ok = False
                reason = ""
                for attempt in range(3):
                    with heartbeat_call_lock:
                        if stop_heartbeat.is_set():
                            ok, reason = False, "stopping"
                            break
                        ok, reason = _renew_heartbeat(spec, lease_id, owner_pid)
                    if ok:
                        break
                    if reason == "cas_rejection":
                        break
                    if stop_heartbeat.wait(timeout=1.0):
                        reason = "stopping"
                        break

                if not ok:
                    if reason == "cas_rejection":
                        print(
                            f"[console_runner] Terminal lease {lease_id} superseded (CAS rejection). Stopping heartbeat renewal.",
                            file=sys.stderr,
                        )
                    elif reason != "stopping":
                        print(
                            f"[console_runner:WARN] terminal-priority-lost: Heartbeat renewal failed for lease {lease_id}.",
                            file=sys.stderr,
                        )
                    break

        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True, name=f"heartbeat-{spec.peer_id}")
        heartbeat_thread.start()

    # 5. Process Execution
    if launch.banner_message:
        print(launch.banner_message)

    full_cmd = spec.cmd_prefix + launch.final_argv
    cwd_str = str(spec.cwd) if spec.cwd else None

    exit_code = 1
    t_start = time.time()

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

        _update_peer_health_json(spec, 0, 0, getattr(proc, "pid", None), stage="start")

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
    finally:
        # Stop Heartbeat
        stop_heartbeat.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2.0)

        # Release Lease if claimed. Acquiring the same lock the heartbeat
        # loop holds during each renewal call guarantees close can never run
        # concurrently with an in-flight heartbeat (even if join() above
        # timed out with the thread still mid-call) -- see the heartbeat
        # loop's comment for the full race this closes. Bounded acquire
        # (not an unbounded `with`) so a genuinely hung heartbeat subprocess
        # call can never block shutdown forever -- best-effort close either
        # way, just logs if the lock couldn't be acquired in time.
        if lease_claimed and lease_id:
            got_lock = heartbeat_call_lock.acquire(timeout=5.0)
            if not got_lock:
                print(
                    f"[console_runner:WARN] heartbeat lock still held after 5s; "
                    f"closing lease {lease_id} anyway (best effort).",
                    file=sys.stderr,
                )
            try:
                _run_hub_action(
                    ["terminal-close", "--lease-id", lease_id, "--reason", "console_exit"],
                    env=spec.env,
                )
            finally:
                if got_lock:
                    heartbeat_call_lock.release()

        duration_ms = int((time.time() - t_start) * 1000)
        interrupt_ok = spec.keyboard_interrupt_is_success
        success = exit_code == 0 or (exit_code == 130 and interrupt_ok)
        final_status = "GREEN" if success else "RED"

        _run_hub_action(
            ["health-update", "--peer", spec.peer_id, "--status", final_status, "--failures", "0" if success else "1"],
            env=spec.env,
        )
        _update_peer_health_json(spec, exit_code, duration_ms, None, stage="finish")

    return ConsoleResult(
        exit_code=exit_code,
        launch=launch,
        lease_id=lease_id,
        lease_claimed=lease_claimed,
    )
