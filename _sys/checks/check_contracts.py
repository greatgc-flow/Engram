"""check_contracts.py - GAP-2 Prevention Gate.

Runs test_contracts.py (fast, no network, no AI) as a Claude Code PreToolUse
hook. Claude Code hook semantics are fixed: exit 2 blocks the tool call; exit 0,
1, 3, 4, or any other code is non-blocking. Therefore this script uses process
exit codes for hook behavior and logs a separate policy_exit_code for observability.

Process exit codes:
  0 - allow: contracts pass / not applicable
  1 - allow: internal check failure, fail-open but visible
  2 - block: contract violation, governed-core internal failure, or fail-open cap exceeded

Policy exit codes logged for diagnostics:
  0 - all contracts pass / not applicable
  1 - contract violation(s) found
  2 - internal check failure, fail-open
  3 - governed-core internal check failure, fail-closed
  4 - consecutive internal fail-open cap exceeded

Usage:
  python check_contracts.py [--changed-file path/to/file.py]
"""
from __future__ import annotations

import argparse
import json
import platform
import select
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_DATA_DIR = _SYS_DIR / "data"
_TESTS_DIR = _SYS_DIR / "tests" / "unit"

_STATE_FILE = _DATA_DIR / "check_contracts_state.json"
_OPERATIONAL_ERRORS_LOG = _DATA_DIR / "operational_errors.jsonl"
_FAIL_OPEN_CAP = 3

PROCESS_ALLOW = 0
PROCESS_WARN_ALLOW = 1
PROCESS_BLOCK = 2

POLICY_PASS = 0
POLICY_CONTRACT_VIOLATION = 1
POLICY_INTERNAL_FAIL_OPEN = 2
POLICY_GOVERNED_FAIL_CLOSED = 3
POLICY_FAIL_OPEN_CAP_EXCEEDED = 4

# Contract suite moved under l1_core/; fall back to the legacy flat path so the
# guard never fails open on a missing file (cx pre-merge review, DIR-003).
_CONTRACT_TEST = _TESTS_DIR / "l1_core" / "test_contracts.py"
if not _CONTRACT_TEST.exists():
    _CONTRACT_TEST = _TESTS_DIR / "test_contracts.py"

# Governed-core contract targets. Internal check failures for these paths fail
# closed unless explicitly downgraded by --force-tier0.
_GOVERNED_CORE_PATHS = {
    _SYS_DIR / "ai" / "orchestration.json",
    _SYS_DIR / "ai" / "peers.json",
    _TESTS_DIR / "l1_core" / "test_contracts.py",
    _TESTS_DIR / "test_contracts.py",
    _CHECKS_DIR / "check_contracts.py",
}

# Preserve the older trigger surface for existing contract checks, without
# making these extra files governed-core fail-closed targets.
_ADDITIONAL_CONTRACT_TRIGGER_PATHS = {
    _SYS_DIR / "ai" / "common" / "tool-registry.json",
    _SYS_DIR / "ai" / "knowledge" / "general" / "active-lessons.jsonl",
    _SYS_DIR / "ai" / "runtime-directives.jsonl",
}

_CONTRACT_TRIGGER_PATHS = _GOVERNED_CORE_PATHS | _ADDITIONAL_CONTRACT_TRIGGER_PATHS


def _python() -> str:
    venv_py = _SYS_DIR / "env" / "venv" / "Scripts" / "python.exe"
    return str(venv_py) if venv_py.exists() else sys.executable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_resolve(path: str | Path) -> Path:
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path).absolute()


def _path_matches(path: str | Path, candidates: set[Path]) -> bool:
    resolved = _safe_resolve(path)
    return any(resolved == _safe_resolve(candidate) for candidate in candidates)


def _is_under_sys(path: Path) -> bool:
    try:
        path.relative_to(_safe_resolve(_SYS_DIR))
        return True
    except ValueError:
        return False


def is_core_file(changed: str | None) -> bool:
    """Return True if the changed file should trigger the contract gate."""
    if changed is None:
        return True  # always check when no file specified

    p = _safe_resolve(changed)
    if _path_matches(p, _CONTRACT_TRIGGER_PATHS):
        return True

    # Existing behavior: any Python file under _sys/ triggers the contract gate.
    if p.suffix == ".py" and _is_under_sys(p):
        return True

    return False


def is_governed_core_file(changed: str | None, *, always: bool = False) -> bool:
    """Return True if this invocation targets governed-core fail-closed files."""
    if always or changed is None:
        return True
    return _path_matches(changed, _GOVERNED_CORE_PATHS)


def _default_state() -> dict:
    return {
        "consecutive_fail_open": 0,
        "last_result": "never_run",
        "last_ts": None,
    }


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    if not isinstance(data, dict):
        return _default_state()

    state = _default_state()
    state.update(data)
    try:
        state["consecutive_fail_open"] = int(state.get("consecutive_fail_open", 0))
    except (TypeError, ValueError):
        state["consecutive_fail_open"] = 0
    if state["consecutive_fail_open"] < 0:
        state["consecutive_fail_open"] = 0
    return state


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_name(_STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(_STATE_FILE)


def _reset_state(last_result: str) -> None:
    state = _default_state()
    state["last_result"] = last_result
    state["last_ts"] = _utc_now()
    _save_state(state)


def _record_contract_violation_state() -> None:
    state = _load_state()
    state["last_result"] = "contract_violation"
    state["last_ts"] = _utc_now()
    _save_state(state)


def _record_internal_failure_state() -> int:
    state = _load_state()
    count = int(state.get("consecutive_fail_open", 0)) + 1
    state["consecutive_fail_open"] = count
    state["last_result"] = "internal_failure"
    state["last_ts"] = _utc_now()
    _save_state(state)
    return count


def _truncate(text: str, limit: int = 2000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _append_operational_error(
    *,
    pattern: str,
    severity: str,
    detail: str,
    process_exit_code: int,
    policy_exit_code: int,
    governed_core: bool,
    force_tier0: bool,
    consecutive_fail_open: int,
    changed_file: str,
    original_rc: int,
) -> None:
    entry = {
        "ts": _utc_now(),
        "peer": "check_contracts",
        "pattern": pattern,
        "severity": severity,
        "detail": detail,
        "exit_code": process_exit_code,
        "process_exit_code": process_exit_code,
        "policy_exit_code": policy_exit_code,
        "governed_core": governed_core,
        "force_tier0": force_tier0,
        "consecutive_fail_open": consecutive_fail_open,
        "changed_file": changed_file,
        "original_rc": original_rc,
    }
    try:
        _OPERATIONAL_ERRORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _OPERATIONAL_ERRORS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[check_contracts] WARN: could not write operational error log: {exc}", file=sys.stderr)


def _classify_internal_failure(
    *,
    original_rc: int,
    output: str,
    governed_core: bool,
    force_tier0: bool,
    changed_label: str,
) -> tuple[int, int, int]:
    consecutive = _record_internal_failure_state()

    if consecutive > _FAIL_OPEN_CAP:
        process_exit_code = PROCESS_BLOCK
        policy_exit_code = POLICY_FAIL_OPEN_CAP_EXCEEDED
        pattern = "CONTRACT_CHECK_FAIL_OPEN_CAP_EXCEEDED"
        severity = "error"
    elif governed_core and not force_tier0:
        process_exit_code = PROCESS_BLOCK
        policy_exit_code = POLICY_GOVERNED_FAIL_CLOSED
        pattern = "CONTRACT_CHECK_FAIL_CLOSED"
        severity = "error"
    elif governed_core and force_tier0:
        process_exit_code = PROCESS_WARN_ALLOW
        policy_exit_code = POLICY_GOVERNED_FAIL_CLOSED
        pattern = "CONTRACT_CHECK_FAIL_CLOSED_OVERRIDE"
        severity = "warn"
    else:
        process_exit_code = PROCESS_WARN_ALLOW
        policy_exit_code = POLICY_INTERNAL_FAIL_OPEN
        pattern = "CONTRACT_CHECK_INTERNAL_ERROR"
        severity = "warn"

    detail = (
        f"contract check internal failure; original_rc={original_rc}; "
        f"process_exit_code={process_exit_code}; policy_exit_code={policy_exit_code}; "
        f"governed_core={governed_core}; force_tier0={force_tier0}; "
        f"consecutive_fail_open={consecutive}; changed_file={changed_label}; "
        f"output={_truncate(output)}"
    )
    _append_operational_error(
        pattern=pattern,
        severity=severity,
        detail=detail,
        process_exit_code=process_exit_code,
        policy_exit_code=policy_exit_code,
        governed_core=governed_core,
        force_tier0=force_tier0,
        consecutive_fail_open=consecutive,
        changed_file=changed_label,
        original_rc=original_rc,
    )
    return process_exit_code, policy_exit_code, consecutive


def run_contracts() -> tuple[int, str]:
    """Run test_contracts.py and return (returncode, output)."""
    if not _CONTRACT_TEST.exists():
        return 2, f"[check_contracts] test_contracts.py not found at {_CONTRACT_TEST}"

    try:
        result = subprocess.run(
            [
                _python(),
                "-m",
                "pytest",
                str(_CONTRACT_TEST),
                "-q",
                "--tb=short",
                "--no-header",
                "--disable-warnings",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 2, "[check_contracts] TIMEOUT: contract check took >60s"
    except FileNotFoundError:
        return 2, "[check_contracts] ERROR: pytest not found"
    except Exception as e:
        return 2, f"[check_contracts] ERROR: {e}"


def _file_from_hook_stdin() -> str | None:
    """Read Claude Code PreToolUse JSON from stdin and extract file path."""
    # Return None if stdin is empty.
    if platform.system() == "Windows":
        # On Windows, select() only works on sockets/pipes.
        if sys.stdin.isatty():
            return None
    else:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        data = json.loads(raw)
        tool_input = data.get("tool_input", {})
        # Write/Edit/MultiEdit all use file_path in tool_input.
        return tool_input.get("file_path") or tool_input.get("path")
    except Exception:
        return None


def _print_blocking(message: str = "") -> None:
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Contract gate check")
    parser.add_argument(
        "--changed-file",
        default=None,
        help="Path to the file being modified (optional filter)",
    )
    parser.add_argument(
        "--always",
        action="store_true",
        help="Run even if changed-file is not a core file",
    )
    parser.add_argument(
        "--hook",
        action="store_true",
        help="Hook mode: read file path from Claude Code JSON stdin",
    )
    parser.add_argument(
        "--force-tier0",
        action="store_true",
        help="Tier-0 human override: downgrade a governed-core fail-closed to fail-open, logged",
    )
    args = parser.parse_args(argv)

    if args.hook and args.changed_file is None:
        args.changed_file = _file_from_hook_stdin()

    if not args.always and not is_core_file(args.changed_file):
        print(f"[check_contracts] SKIP - not a core file: {args.changed_file}")
        sys.exit(PROCESS_ALLOW)

    changed_label = args.changed_file or "(all)"
    governed_core = is_governed_core_file(args.changed_file, always=args.always)

    print(f"[check_contracts] Checking contracts for: {changed_label}")

    rc, output = run_contracts()

    if rc == 0:
        _reset_state("pass")
        last = [ln for ln in output.splitlines() if ln.strip()]
        print(f"[check_contracts] PASS - {last[-1] if last else 'ok'}")
        sys.exit(PROCESS_ALLOW)

    if rc == 1:
        _record_contract_violation_state()
        _print_blocking("[check_contracts] FAIL - contract violation(s):")
        _print_blocking(output)
        _print_blocking()
        _print_blocking("  NACK: _sys/ file write blocked until test_contracts.py passes.")
        _print_blocking("  Fix: update test_contracts.py to match the new API signature,")
        _print_blocking("       or revert the API change.")
        sys.exit(PROCESS_BLOCK)

    process_exit_code, policy_exit_code, consecutive = _classify_internal_failure(
        original_rc=rc,
        output=output,
        governed_core=governed_core,
        force_tier0=args.force_tier0,
        changed_label=changed_label,
    )

    if process_exit_code == PROCESS_WARN_ALLOW:
        if governed_core and args.force_tier0:
            print(f"[check_contracts] WARN (force-tier0 fail-open override): {output.strip()}", file=sys.stderr)
        else:
            print(f"[check_contracts] WARN (fail-open visible): {output.strip()}", file=sys.stderr)
        sys.exit(PROCESS_WARN_ALLOW)

    if policy_exit_code == POLICY_GOVERNED_FAIL_CLOSED:
        _print_blocking(f"[check_contracts] FAIL-CLOSED (governed-core internal error): {output.strip()}")
        _print_blocking("  NACK: governed-core write blocked because contract gate is unhealthy.")
        _print_blocking("  Use --force-tier0 only if the human operator accepts this risk.")
        sys.exit(PROCESS_BLOCK)

    _print_blocking(f"[check_contracts] FAIL-CLOSED (internal failure cap exceeded): {output.strip()}")
    _print_blocking(f"  NACK: contract gate has failed internally {consecutive} consecutive times.")
    _print_blocking(f"  Cap: {_FAIL_OPEN_CAP}. Repair the gate or use a separate Tier-0 recovery path.")
    sys.exit(PROCESS_BLOCK)


if __name__ == "__main__":
    main()
