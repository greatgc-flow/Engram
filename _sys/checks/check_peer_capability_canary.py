#!/usr/bin/env python3
"""Empirical peer capability canary for direct UTF-8 file writes.

Capability:
  direct_file_write.safe_utf8.v1

The harness invokes a candidate peer/profile through its real native CLI path in
a disposable workspace, then judges artifacts on disk. Transcripts are retained
for diagnostics only; they are never trusted as proof that a write succeeded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

if str(_SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR / "core"))
if str(_CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CHECKS_DIR))

from _common import build_env  # noqa: E402
from check_cli_reality import fingerprint, real_binary  # noqa: E402
from hub_peer import get_adapter, normalize_orchestration  # noqa: E402


CAPABILITY_ID = "direct_file_write.safe_utf8.v1"
SCHEMA_VERSION = 2
SOURCE_TAG = "empirical_probe"
PASS_SCORE = 95
REPEATABILITY_REQUIRED = 3
VALID_DAYS = 7

SCORES_PATH = _SYS_DIR / "ai" / "knowledge" / "peer-capability-scores.jsonl"
ARTIFACT_ROOT = _PORTABLE_ROOT / "_archive" / "capability-canaries"

ROUNDTRIP_FILE = "roundtrip_utf8.txt"
TARGETED_FILE = "targeted_edit.txt"
CRLF_FILE = "line_endings_crlf.txt"
LF_FILE = "line_endings_lf.txt"
LARGE_FILE = "large_partial_replace.txt"
FAILURE_TARGET = "impossible_target_dir"
FAILURE_REPORT = "failure_report.json"

TARGET_TOKEN = "T21_TARGET_VALUE_ORIGINAL"
TARGET_REPLACEMENT = "T21_TARGET_VALUE_REPLACED"
LARGE_TOKEN = "T21_LARGE_PARTIAL_TOKEN_ORIGINAL"
LARGE_REPLACEMENT = "T21_LARGE_PARTIAL_TOKEN_REPLACED"

ROUNDTRIP_TEXT = (
    "ASCII baseline: The quick brown fox 12345.\n"
    "Korean: 한글 안전성 점검 - 직접 파일 쓰기 카나리.\n"
    "Symbols: § arrows -> <- => <= ... bullets * + -.\n"
    "Box drawing: ┌─┬─┐ │ A │ B │ └─┴─┘.\n"
    "Accents: cafe\u0301 naive façade coöperate São Paulo.\n"
)
CRLF_TEXT = "CRLF line 1\r\nCRLF Korean 한글 line 2\r\nCRLF symbols § -> ...\r\n"
LF_TEXT = "LF line 1\nLF Korean 한글 line 2\nLF symbols § -> ...\n"

TARGETED_INITIAL_TEXT = (
    "HEADER: keep this line byte-identical\n"
    "Korean context: 주변 문장은 바뀌면 안 됩니다.\n"
    "Symbols context: § -> <- ... * bullets stay.\n"
    "BEGIN_TARGET_BLOCK\n"
    f"value={TARGET_TOKEN}\n"
    "END_TARGET_BLOCK\n"
    "FOOTER: keep this line byte-identical\n"
)
TARGETED_EXPECTED_TEXT = TARGETED_INITIAL_TEXT.replace(TARGET_TOKEN, TARGET_REPLACEMENT)

WEIGHTS = {
    "unicode_byte_roundtrip": 30,
    "targeted_edit_preservation": 25,
    "line_endings_and_bom": 15,
    "target_scope": 10,
    "failure_truthfulness": 15,
    "repeatability": 5,
}
HARD_GATES = {
    "targeted_edit_preservation",
    "line_endings_and_bom",
    "target_scope",
    "failure_truthfulness",
}

Invoker = Callable[[str, str, str, Path, dict, int | None], subprocess.CompletedProcess]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_bytes(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n")


def _large_initial_text() -> str:
    lines = []
    for idx in range(1400):
        lines.append(
            f"{idx:04d} :: 한글 UTF-8 context § -> ... ┌─┐ cafe\u0301 stable content\n"
        )
    insert_at = len(lines) // 2
    lines.insert(insert_at, f"PARTIAL_EDIT_TARGET={LARGE_TOKEN}\n")
    return "".join(lines)


def _snapshot_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def prepare_fixture(workspace: Path) -> dict[str, Any]:
    """Create a disposable workspace and return the expected final artifacts."""
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    large_initial = _large_initial_text()
    large_expected = large_initial.replace(LARGE_TOKEN, LARGE_REPLACEMENT, 1)

    initial_bytes = {
        ROUNDTRIP_FILE: b"",
        TARGETED_FILE: TARGETED_INITIAL_TEXT.encode("utf-8"),
        CRLF_FILE: b"",
        LF_FILE: b"",
        LARGE_FILE: large_initial.encode("utf-8"),
    }
    expected_bytes = {
        ROUNDTRIP_FILE: ROUNDTRIP_TEXT.encode("utf-8"),
        TARGETED_FILE: TARGETED_EXPECTED_TEXT.encode("utf-8"),
        CRLF_FILE: CRLF_TEXT.encode("utf-8"),
        LF_FILE: LF_TEXT.encode("utf-8"),
        LARGE_FILE: large_expected.encode("utf-8"),
    }

    for rel, data in initial_bytes.items():
        _write_bytes(workspace / rel, data)
    (workspace / FAILURE_TARGET).mkdir(parents=True, exist_ok=True)

    return {
        "workspace": str(workspace),
        "initial_bytes": initial_bytes,
        "expected_bytes": expected_bytes,
        "allowed_files": sorted([*expected_bytes.keys(), FAILURE_REPORT]),
        "large_initial_size_bytes": len(initial_bytes[LARGE_FILE]),
        "large_expected_size_bytes": len(expected_bytes[LARGE_FILE]),
    }


def build_prompt(workspace: Path) -> str:
    """Instruction sent to the candidate peer for the empirical write probe."""
    return f"""[DIRECT_FILE_WRITE_CAPABILITY_CANARY capability={CAPABILITY_ID}]
This is an authorized empirical canary in a disposable local workspace.

Workspace:
{workspace}

Use your normal native file-edit/write capability. Do not ask another agent to
edit these files. Do not write outside this workspace.

Required writes:
1. Overwrite {ROUNDTRIP_FILE} with exactly this UTF-8 text:
<<<ROUNDTRIP_TEXT
{ROUNDTRIP_TEXT}<<<END_ROUNDTRIP_TEXT

2. In {TARGETED_FILE}, replace only {TARGET_TOKEN} with {TARGET_REPLACEMENT}.
Preserve every other byte in the file.

3. Overwrite {CRLF_FILE} with exactly this content, preserving CRLF line endings:
<<<CRLF_TEXT
{CRLF_TEXT}<<<END_CRLF_TEXT

4. Overwrite {LF_FILE} with exactly this content, preserving LF line endings and no BOM:
<<<LF_TEXT
{LF_TEXT}<<<END_LF_TEXT

5. In {LARGE_FILE}, replace only the first {LARGE_TOKEN} with {LARGE_REPLACEMENT}.
This file is intentionally larger than 50KB and already contains UTF-8 text.
Preserve every other byte.

6. Attempt to write a file at {FAILURE_TARGET}. That path is a directory, so the
write should fail. Record the truthful result in {FAILURE_REPORT} as JSON:
{{"target": "{FAILURE_TARGET}", "status": "failed", "reason": "<short reason>"}}

Do not create, rename, delete, or modify any other file."""


def _subcheck(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    weight = WEIGHTS[name]
    return {
        "weight": weight,
        "earned": weight if passed else 0,
        "passed": bool(passed),
        "hard_gate": name in HARD_GATES,
        "details": details or {},
    }


def _score_unicode(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    checked = [ROUNDTRIP_FILE, TARGETED_FILE, LARGE_FILE]
    mismatches = []
    for rel in checked:
        path = workspace / rel
        expected = _normalize_bytes(fixture["expected_bytes"][rel])
        actual = _normalize_bytes(path.read_bytes()) if path.exists() else None
        if actual != expected:
            mismatches.append(rel)
    return _subcheck("unicode_byte_roundtrip", not mismatches, {"mismatches": mismatches})


def _score_targeted(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    targeted_path = workspace / TARGETED_FILE
    large_path = workspace / LARGE_FILE
    targeted_actual = targeted_path.read_bytes() if targeted_path.exists() else None
    large_actual = large_path.read_bytes() if large_path.exists() else None
    targeted_expected = fixture["expected_bytes"][TARGETED_FILE]
    large_expected = fixture["expected_bytes"][LARGE_FILE]

    targeted_passed = targeted_actual == targeted_expected
    large_passed = large_actual == large_expected
    large_size = len(large_actual or b"")
    token_count = 0
    replacement_count = 0
    if large_actual is not None:
        token_count = large_actual.count(LARGE_TOKEN.encode("utf-8"))
        replacement_count = large_actual.count(LARGE_REPLACEMENT.encode("utf-8"))

    details = {
        "targeted_edit_passed": targeted_passed,
        "large_partial_edit_passed": large_passed,
        "large_file_size_bytes": large_size,
        "large_file_over_50kb": large_size > 50 * 1024,
        "large_original_token_count": token_count,
        "large_replacement_count": replacement_count,
    }
    return _subcheck(
        "targeted_edit_preservation",
        targeted_passed and large_passed and large_size > 50 * 1024,
        details,
    )


def _score_line_endings(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    bom_files = []
    raw_mismatches = []
    for rel, expected in fixture["expected_bytes"].items():
        path = workspace / rel
        actual = path.read_bytes() if path.exists() else b""
        if actual.startswith(b"\xef\xbb\xbf"):
            bom_files.append(rel)
        if rel in (CRLF_FILE, LF_FILE) and actual != expected:
            raw_mismatches.append(rel)
    return _subcheck(
        "line_endings_and_bom",
        not bom_files and not raw_mismatches,
        {"bom_files": bom_files, "raw_line_ending_mismatches": raw_mismatches},
    )


def _score_target_scope(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    observed = _snapshot_files(workspace)
    allowed = set(fixture["allowed_files"])
    expected = set(fixture["expected_bytes"])
    observed_files = set(observed)
    extra_files = sorted(observed_files - allowed)
    missing_files = sorted(expected - observed_files)
    failure_dir = workspace / FAILURE_TARGET
    failure_dir_children = []
    if failure_dir.exists():
        failure_dir_children = [
            p.relative_to(workspace).as_posix()
            for p in failure_dir.rglob("*")
        ]
    passed = (
        not extra_files
        and not missing_files
        and failure_dir.exists()
        and failure_dir.is_dir()
        and not failure_dir_children
    )
    return _subcheck(
        "target_scope",
        passed,
        {
            "extra_files": extra_files,
            "missing_files": missing_files,
            "failure_dir_children": sorted(failure_dir_children),
        },
    )


def _score_truthfulness(workspace: Path) -> dict[str, Any]:
    report_path = workspace / FAILURE_REPORT
    details: dict[str, Any] = {"report_exists": report_path.exists()}
    passed = False
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            status = str(report.get("status", "")).lower()
            target = report.get("target")
            details.update({"status": status, "target": target, "parse_error": None})
            passed = (
                target in (FAILURE_TARGET, str(Path(FAILURE_TARGET)))
                and status in {"failed", "denied", "refused", "error"}
                and (workspace / FAILURE_TARGET).is_dir()
            )
        except Exception as exc:
            details["parse_error"] = str(exc)
    return _subcheck("failure_truthfulness", passed, details)


def score_workspace(workspace: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    subchecks = {
        "unicode_byte_roundtrip": _score_unicode(workspace, fixture),
        "targeted_edit_preservation": _score_targeted(workspace, fixture),
        "line_endings_and_bom": _score_line_endings(workspace, fixture),
        "target_scope": _score_target_scope(workspace, fixture),
        "failure_truthfulness": _score_truthfulness(workspace),
    }
    hard_failures = [
        name for name, result in subchecks.items()
        if result["hard_gate"] and not result["passed"]
    ]
    score_without_repeatability = sum(result["earned"] for result in subchecks.values())
    base_passed = score_without_repeatability >= PASS_SCORE and not hard_failures
    return {
        "score_without_repeatability": score_without_repeatability,
        "subchecks": subchecks,
        "hard_failures": hard_failures,
        "base_passed": base_passed,
    }


def runtime_fingerprint_valid(runtime_fingerprint: dict[str, Any] | None) -> bool:
    if not isinstance(runtime_fingerprint, dict):
        return False
    binary = runtime_fingerprint.get("binary")
    return (
        isinstance(runtime_fingerprint.get("peer"), str)
        and bool(runtime_fingerprint["peer"].strip())
        and isinstance(runtime_fingerprint.get("profile"), str)
        and bool(runtime_fingerprint["profile"].strip())
        and isinstance(runtime_fingerprint.get("model_id"), str)
        and bool(runtime_fingerprint["model_id"].strip())
        and isinstance(runtime_fingerprint.get("reasoning_effort"), str)
        and bool(runtime_fingerprint["reasoning_effort"].strip())
        and isinstance(runtime_fingerprint.get("adapter"), str)
        and bool(runtime_fingerprint["adapter"].strip())
        and isinstance(runtime_fingerprint.get("invoke_args"), list)
        and isinstance(runtime_fingerprint.get("profile_config_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", runtime_fingerprint["profile_config_sha256"]) is not None
        and isinstance(binary, dict)
        and binary.get("exists") is True
        and isinstance(binary.get("sha256"), str)
        and bool(binary.get("sha256"))
    )


def _same_runtime(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not runtime_fingerprint_valid(left) or not runtime_fingerprint_valid(right):
        return False
    left_binary = left["binary"]
    right_binary = right["binary"]
    return (
        left.get("peer") == right.get("peer")
        and left.get("profile") == right.get("profile")
        and left.get("model_id") == right.get("model_id")
        and left.get("reasoning_effort") == right.get("reasoning_effort")
        and left.get("adapter") == right.get("adapter")
        and left.get("invoke_args") == right.get("invoke_args")
        and left.get("profile_config_sha256") == right.get("profile_config_sha256")
        and left_binary.get("sha256") == right_binary.get("sha256")
    )


def _consecutive_base_passes(
    peer: str,
    profile: str,
    runtime_fingerprint: dict[str, Any],
    prior_entries: list[dict[str, Any]],
    current_base_passed: bool,
) -> int:
    count = 1 if current_base_passed else 0
    for entry in reversed(prior_entries):
        if entry.get("peer") != peer or entry.get("profile") != profile:
            continue
        if entry.get("capability_id") != CAPABILITY_ID:
            continue
        if not _same_runtime(entry.get("runtime_fingerprint"), runtime_fingerprint):
            break
        
        # Skip transient PTY errors so they don't reset consecutive progress
        inv = entry.get("invocation", {})
        if inv.get("transport") == "pty" and (inv.get("transport_error") is not None or inv.get("timeout_kind") is not None):
            continue

        if not entry.get("base_passed", entry.get("passed")):
            break
        count += 1
    return count


def build_score_entry(
    *,
    peer: str,
    profile: str,
    workspace: Path,
    fixture: dict[str, Any],
    artifact_dir: Path,
    runtime_fingerprint: dict[str, Any],
    prior_entries: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    invocation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or _utc_now()
    scored = score_workspace(workspace, fixture)
    prior_entries = prior_entries or []
    runtime_ok = runtime_fingerprint_valid(runtime_fingerprint)
    consecutive = _consecutive_base_passes(
        peer,
        profile,
        runtime_fingerprint,
        prior_entries,
        scored["base_passed"],
    )
    repeatability_passed = consecutive >= REPEATABILITY_REQUIRED
    repeatability = _subcheck(
        "repeatability",
        repeatability_passed,
        {
            "required_consecutive_passes": REPEATABILITY_REQUIRED,
            "consecutive_base_passes": consecutive,
        },
    )

    subchecks = dict(scored["subchecks"])
    subchecks["repeatability"] = repeatability
    hard_failures = list(scored["hard_failures"])
    if not runtime_ok:
        hard_failures.append("runtime_fingerprint")
    score = scored["score_without_repeatability"] + repeatability["earned"]
    passed = (
        score >= PASS_SCORE
        and scored["base_passed"]
        and repeatability_passed
        and runtime_ok
        and not hard_failures
    )

    measured_at = _iso(now)
    safe_capability = CAPABILITY_ID.replace(".", "-").replace("_", "-")
    entry = {
        "schema_version": SCHEMA_VERSION,
        "id": f"cap-{now.strftime('%Y%m%d')}-{peer}-{profile}-{safe_capability}",
        "peer": peer,
        "profile": profile,
        "capability_id": CAPABILITY_ID,
        "score": score,
        "passed": passed,
        "base_passed": scored["base_passed"],
        "measured_at": measured_at,
        "expires_at": _iso(now + timedelta(days=VALID_DAYS)),
        "source_tag": SOURCE_TAG,
        "runtime_fingerprint": runtime_fingerprint,
        "subchecks": subchecks,
        "hard_failures": sorted(set(hard_failures)),
        "artifact_dir": str(artifact_dir),
    }
    if invocation is not None:
        entry["invocation"] = invocation
    return entry


def is_capability_record_valid(
    entry: dict[str, Any],
    now: datetime | None = None,
    expected_runtime_fingerprint: dict[str, Any] | None = None,
) -> bool:
    now = now or _utc_now()
    expires_at = _parse_iso(entry.get("expires_at"))
    if entry.get("capability_id") != CAPABILITY_ID:
        return False
    if entry.get("source_tag") != SOURCE_TAG:
        return False
    if entry.get("passed") is not True:
        return False
    if expires_at is None or expires_at <= now:
        return False
    runtime_fingerprint = entry.get("runtime_fingerprint")
    if not runtime_fingerprint_valid(runtime_fingerprint):
        return False
    if expected_runtime_fingerprint is not None and not _same_runtime(
        runtime_fingerprint,
        expected_runtime_fingerprint,
    ):
        return False
    return True


def load_score_entries(path: Path = SCORES_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def write_score_entry(entry: dict[str, Any], path: Path = SCORES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _profile_node(orch: dict, peer: str, profile: str) -> dict[str, Any]:
    normalized = normalize_orchestration(orch)
    profile_id = f"{peer}.{profile}"
    for node in normalized.get("hub_nodes", []):
        if node.get("node_id") == profile_id and node.get("type") == "profile":
            return node
    raise RuntimeError(f"Profile {profile_id} not found")


def build_cmd_and_prompt(orch: dict, peer: str, profile: str, prompt: str) -> tuple[list[str], str | None, Any, dict]:
    profile_node = _profile_node(orch, peer, profile)
    adapter = get_adapter(profile_node)
    cmd, use_stdin = adapter.build_cmd(profile_node, prompt)
    if cmd:
        executable = Path(cmd[0])
        if not executable.is_absolute() and executable.parts and executable.parts[0].casefold() == "_sys":
            cmd[0] = str((_PORTABLE_ROOT / executable).resolve())
    return cmd, (prompt if use_stdin else None), adapter, profile_node


def invoke_peer_native_write(
    peer: str,
    profile: str,
    prompt: str,
    workspace: Path,
    orch: dict,
    timeout: int | None,
) -> subprocess.CompletedProcess:
    cmd, stdin_data, _adapter, _profile_node_obj = build_cmd_and_prompt(orch, peer, profile, prompt)
    return subprocess.run(
        cmd,
        input=stdin_data,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout or 300,
        env=build_env(),
    )


@dataclass(frozen=True)
class PtyCompletedProcess:
    returncode: int
    stdout: str
    stderr: str
    transport: str = "pty"
    elapsed_sec: int = 0
    exit_code: int | None = None
    timeout_kind: str | None = None
    transport_error: str | None = None


def invoke_peer_native_write_pty(
    peer: str,
    profile: str,
    prompt: str,
    workspace: Path,
    orch: dict,
    timeout: int | None,
) -> PtyCompletedProcess:
    try:
        import winpty
    except Exception as exc:
        return PtyCompletedProcess(
            returncode=1,
            stdout="",
            stderr=f"winpty import/DLL load failed: {exc}",
            transport="pty",
            elapsed_sec=0,
            exit_code=1,
            timeout_kind=None,
            transport_error=f"winpty_import_failed: {exc}",
        )

    try:
        profile_node = _profile_node(orch, peer, profile)
        adapter = get_adapter(profile_node)
        cmd, use_stdin = adapter.build_cmd(profile_node, prompt)
        if cmd:
            executable = Path(cmd[0])
            if not executable.is_absolute() and executable.parts and executable.parts[0].casefold() == "_sys":
                cmd[0] = str((_PORTABLE_ROOT / executable).resolve())
        
        import hub
        timeout_sec = timeout or 300

        # Scope AGY_CONFIG_HOME to THIS canary invocation only (a disposable home
        # per workspace) so the PTY spike never pollutes the production agy session
        # DB, and so the shared build_env() is not globally rerouted for other
        # checks (check_versions / check_cli_canary rely on the real agy home).
        pty_env = build_env()
        agy_home = workspace / ".agy_config"
        try:
            agy_home.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        pty_env["AGY_CONFIG_HOME"] = str(agy_home)

        res = hub._ask_with_pty(
            cmd=cmd,
            node_id=profile_node.get("node_id"),
            timeout_sec=timeout_sec,
            process_env=pty_env,
            quiet=True,
            ai_root=None,
            cwd=str(workspace),
        )
        
        timed_out = res.timed_out
        transport_error = res.transport_error
        exit_code = res.exit_code
        
        is_success = (not timed_out) and (transport_error is None) and (exit_code in {0, None})
        returncode = 0 if is_success else (exit_code if exit_code is not None else 1)
        
        sanitized_text = adapter.parse_output(res.text, profile_node)
        capped_stdout = sanitized_text[-2000:]
        
        return PtyCompletedProcess(
            returncode=returncode,
            stdout=capped_stdout,
            stderr=transport_error or "",
            transport="pty",
            elapsed_sec=res.elapsed,
            exit_code=exit_code,
            timeout_kind=res.timeout_kind,
            transport_error=transport_error,
        )
    except Exception as exc:
        return PtyCompletedProcess(
            returncode=1,
            stdout="",
            stderr=str(exc),
            transport="pty",
            elapsed_sec=0,
            exit_code=1,
            timeout_kind=None,
            transport_error=f"pty_execution_failed: {exc}",
        )


def resolve_runtime_fingerprint(orch: dict, peer: str, profile: str) -> dict[str, Any]:
    model_id = None
    reasoning_effort = None
    adapter = None
    invoke_args: list[str] = []
    profile_config_sha256 = None
    try:
        profile_node = _profile_node(orch, peer, profile)
        model_id = profile_node.get("model_id") or profile_node.get("runtime_model")
        reasoning_effort = profile_node.get("reasoning_effort")
        adapter = profile_node.get("adapter_class")
        invoke_args = list(profile_node.get("invoke_args") or [])
    except Exception:
        pass
    try:
        raw_profile = next(
            node.get("profiles", {}).get(profile)
            for node in orch.get("hub_nodes", [])
            if node.get("node_id") == peer and isinstance(node.get("profiles"), dict)
        )
        if isinstance(raw_profile, dict):
            canonical = json.dumps(
                raw_profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            profile_config_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (StopIteration, TypeError, ValueError):
        pass
    try:
        binary = fingerprint(real_binary(peer, orch))
    except Exception as exc:
        binary = {"exists": False, "sha256": None, "error": str(exc)}
    return {
        "peer": peer,
        "profile": profile,
        "model_id": model_id,
        "reasoning_effort": reasoning_effort,
        "adapter": adapter,
        "invoke_args": invoke_args,
        "profile_config_sha256": profile_config_sha256,
        "binary": binary,
    }


def run_one_pass(
    *,
    peer: str,
    profile: str,
    orch: dict,
    artifact_dir: Path,
    runtime_fingerprint: dict[str, Any],
    prior_entries: list[dict[str, Any]],
    invoker: Invoker = invoke_peer_native_write,
    timeout: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    workspace = artifact_dir / "workspace"
    fixture = prepare_fixture(workspace)
    prompt = build_prompt(workspace)
    invocation: dict[str, Any]
    try:
        result = invoker(peer, profile, prompt, workspace, orch, timeout)
        invocation = {
            "returncode": result.returncode,
            "stdout_tail": (result.stdout or "")[-2000:],
            "stderr_tail": (result.stderr or "")[-2000:],
        }
        if hasattr(result, "transport"):
            invocation["transport"] = result.transport
        if hasattr(result, "elapsed_sec"):
            invocation["elapsed_sec"] = result.elapsed_sec
        if hasattr(result, "exit_code"):
            invocation["exit_code"] = result.exit_code
        if hasattr(result, "timeout_kind"):
            invocation["timeout_kind"] = result.timeout_kind
        if hasattr(result, "transport_error"):
            invocation["transport_error"] = result.transport_error
    except Exception as exc:
        invocation = {"returncode": None, "error": str(exc)}
        (artifact_dir / "invocation_error.json").write_text(
            json.dumps(invocation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    entry = build_score_entry(
        peer=peer,
        profile=profile,
        workspace=workspace,
        fixture=fixture,
        artifact_dir=artifact_dir,
        runtime_fingerprint=runtime_fingerprint,
        prior_entries=prior_entries,
        now=now,
        invocation=invocation,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "entry.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return entry


def run_canary(
    *,
    peer: str,
    profile: str,
    orch: dict,
    passes: int = REPEATABILITY_REQUIRED,
    scores_path: Path = SCORES_PATH,
    artifact_root: Path = ARTIFACT_ROOT,
    invoker: Invoker = invoke_peer_native_write,
    timeout: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if passes <= 0:
        raise ValueError("passes must be positive")
    run_started = now or _utc_now()
    runtime_fingerprint = resolve_runtime_fingerprint(orch, peer, profile)
    prior_entries = load_score_entries(scores_path)
    new_entries: list[dict[str, Any]] = []

    # Run the first pass to determine transport dynamically
    pass_now = run_started + timedelta(seconds=1)
    run_id = f"{pass_now.strftime('%Y%m%dT%H%M%S')}-{peer}-{profile}-1-{uuid.uuid4().hex[:8]}"
    artifact_dir = artifact_root / run_id
    entry = run_one_pass(
        peer=peer,
        profile=profile,
        orch=orch,
        artifact_dir=artifact_dir,
        runtime_fingerprint=runtime_fingerprint,
        prior_entries=prior_entries,
        invoker=invoker,
        timeout=timeout,
        now=pass_now,
    )
    write_score_entry(entry, scores_path)
    prior_entries.append(entry)
    new_entries.append(entry)

    invocation = entry.get("invocation", {})
    is_pty = (invocation.get("transport") == "pty")

    if is_pty:
        total_attempts = 1
        is_pass = (
            entry.get("base_passed") is True
            and entry.get("score", 0) >= PASS_SCORE
            and not entry.get("hard_failures")
            and runtime_fingerprint_valid(entry.get("runtime_fingerprint"))
            and invocation.get("transport") == "pty"
            and invocation.get("transport_error") is None
            and invocation.get("timeout_kind") is None
        )
        passing_count = 1 if is_pass else 0

        # If the first run failed but was not transient, break immediately
        if not is_pass:
            is_transient = (
                invocation.get("error") is not None
                or invocation.get("transport_error") is not None
                or invocation.get("timeout_kind") is not None
            )
            if not is_transient:
                return new_entries

        while passing_count < passes and total_attempts < 5:
            total_attempts += 1
            pass_now = run_started + timedelta(seconds=total_attempts)
            run_id = f"{pass_now.strftime('%Y%m%dT%H%M%S')}-{peer}-{profile}-{passing_count + 1}-{uuid.uuid4().hex[:8]}"
            artifact_dir = artifact_root / run_id
            entry = run_one_pass(
                peer=peer,
                profile=profile,
                orch=orch,
                artifact_dir=artifact_dir,
                runtime_fingerprint=runtime_fingerprint,
                prior_entries=prior_entries,
                invoker=invoker,
                timeout=timeout,
                now=pass_now,
            )
            write_score_entry(entry, scores_path)
            prior_entries.append(entry)
            new_entries.append(entry)

            invocation = entry.get("invocation", {})
            is_pass = (
                entry.get("base_passed") is True
                and entry.get("score", 0) >= PASS_SCORE
                and not entry.get("hard_failures")
                and runtime_fingerprint_valid(entry.get("runtime_fingerprint"))
                and invocation.get("transport") == "pty"
                and invocation.get("transport_error") is None
                and invocation.get("timeout_kind") is None
            )

            if is_pass:
                passing_count += 1
            else:
                is_transient = (
                    invocation.get("error") is not None
                    or invocation.get("transport_error") is not None
                    or invocation.get("timeout_kind") is not None
                )
                if not is_transient:
                    break
    else:
        for idx in range(1, passes):
            pass_now = run_started + timedelta(seconds=idx + 1)
            run_id = f"{pass_now.strftime('%Y%m%dT%H%M%S')}-{peer}-{profile}-{idx + 1}-{uuid.uuid4().hex[:8]}"
            artifact_dir = artifact_root / run_id
            entry = run_one_pass(
                peer=peer,
                profile=profile,
                orch=orch,
                artifact_dir=artifact_dir,
                runtime_fingerprint=runtime_fingerprint,
                prior_entries=prior_entries,
                invoker=invoker,
                timeout=timeout,
                now=pass_now,
            )
            write_score_entry(entry, scores_path)
            prior_entries.append(entry)
            new_entries.append(entry)
    return new_entries


def _load_orchestration(path: Path | None = None) -> dict:
    path = path or (_SYS_DIR / "ai" / "orchestration.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _split_peer_profile(value: str, explicit_profile: str | None) -> tuple[str, str]:
    if "." in value and explicit_profile is None:
        peer, profile = value.split(".", 1)
        return peer, profile
    return value, explicit_profile or "standard"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run direct-file-write UTF-8 capability canary")
    parser.add_argument("--peer", required=True, help="Peer id or peer.profile")
    parser.add_argument("--profile", default=None, help="Profile name; defaults to standard")
    parser.add_argument("--passes", type=int, default=REPEATABILITY_REQUIRED)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--scores-path", type=Path, default=SCORES_PATH)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--orchestration", type=Path, default=_SYS_DIR / "ai" / "orchestration.json")
    parser.add_argument("--transport", choices=["std", "pty"], default="std", help="Transport mode to use")
    parser.add_argument("--execute", action="store_true", help="Gated execute switch (mandatory for real writes)")
    args = parser.parse_args(argv)

    peer, profile = _split_peer_profile(args.peer, args.profile)
    orch = _load_orchestration(args.orchestration)

    try:
        profile_node = _profile_node(orch, peer, profile)
    except Exception as exc:
        print(f"Error resolving profile: {exc}", file=sys.stderr)
        return 1

    if args.transport == "pty":
        if not profile_node.get("requires_pty", False):
            print("Error: --transport pty is valid only when the node has requires_pty=true", file=sys.stderr)
            return 1

    if not args.execute:
        print("Dry-run mode: no changes will be written. Use --execute to run.")
        return 0

    invoker = invoke_peer_native_write
    if args.transport == "pty":
        invoker = invoke_peer_native_write_pty

    entries = run_canary(
        peer=peer,
        profile=profile,
        orch=orch,
        passes=args.passes,
        scores_path=args.scores_path,
        artifact_root=args.artifact_root,
        invoker=invoker,
        timeout=args.timeout,
    )
    latest = entries[-1]
    print(json.dumps(latest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if latest.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
