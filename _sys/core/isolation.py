"""Provider-neutral isolation contracts; no OS providers are implemented here.

Providers must use validated profiles, read-only inputs and a separate writable
evidence mount. Each execution gets a fresh ID and directory. The guest writes
logs first, then flushes/closes result.json.tmp and atomically renames it to
result.json on that mount. Finalized evidence must remain immutable during
collection. Host process exit or temporary files are never canonical evidence.
"""
from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Literal, Mapping, Protocol, Sequence, runtime_checkable


AvailabilityStatus = Literal["AVAILABLE", "UNAVAILABLE"]
ExecutionStatus = Literal["COMPLETED", "TIMED_OUT", "CANCELLED"]
Outcome = Literal["passed", "failed", "timed-out", "cancelled"]
WorkspaceAccess = Literal["none", "read-only", "read-write"]
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_PROFILE_KEYS = frozenset({
    "schema_version", "name", "network", "clipboard", "vgpu",
    "input_read_only", "evidence_writable", "workspace_access", "allow_writable_share",
})
_RESULT_KEYS = frozenset({
    "schema_version", "handle_id", "execution_id", "complete",
    "outcome", "exit_code", "log_refs",
})


class ProfileValidationError(ValueError):
    """A profile cannot be used safely."""


class EvidenceValidationError(ValueError):
    """Canonical guest evidence is missing, invalid or outside its mount."""


class ExposureWarning(UserWarning):
    """An explicitly enabled writable share exposes host workspace data."""


@dataclass(frozen=True)
class Capabilities:
    backend: str
    capture: bool
    concurrency: int

    def __post_init__(self) -> None:
        if not isinstance(self.backend, str) or not self.backend.strip():
            raise ValueError("backend must be nonempty")
        if type(self.capture) is not bool:
            raise ValueError("capture must be a boolean")
        if type(self.concurrency) is not int or self.concurrency < 0:
            raise ValueError("concurrency must be a nonnegative integer")


@dataclass(frozen=True)
class Availability:
    status: AvailabilityStatus
    reason: str
    capabilities: Capabilities

    def __post_init__(self) -> None:
        if self.status not in ("AVAILABLE", "UNAVAILABLE"):
            raise ValueError("invalid availability status")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("availability requires a reason")
        if not isinstance(self.capabilities, Capabilities):
            raise ValueError("invalid capabilities")
        if self.status == "AVAILABLE" and self.capabilities.concurrency == 0:
            raise ValueError("available providers require positive concurrency")


# WIRING-EXEMPT: EXPORTED_API reason="Isolation provider detect API for planned PR 2/3 providers; roadmap: docs/design/blueprint-engram-architecture.md A2/A3"
def probe_availability(
    probe: Callable[[], Availability], *, backend: str,
) -> Availability:
    """Convert failed/invalid provider probes to UNAVAILABLE; never raise.

    Concrete providers must route detect() probes through this boundary.
    Interrupts and process termination are not ordinary probe failures.
    """
    safe_backend = backend if isinstance(backend, str) and backend.strip() else "unknown"
    try:
        result = probe()
        if not isinstance(result, Availability):
            raise ValueError("probe did not return Availability")
        return result
    except Exception as exc:
        try:
            detail = str(exc)
        except Exception:
            detail = "probe exception has no readable message"
        return Availability(
            "UNAVAILABLE", f"Probe failed: {type(exc).__name__}: {detail}",
            Capabilities(safe_backend, False, 0),
        )


def _validate_profile(data: object) -> None:
    """Dependency-free validation of isolation-profile.schema.json version 1."""
    if not isinstance(data, dict) or data.keys() != _PROFILE_KEYS:
        raise ProfileValidationError("profile requires exactly the version 1 fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ProfileValidationError("unsupported profile schema_version")
    if data["name"] not in ("clean-room", "online-test", "dev"):
        raise ProfileValidationError("unknown profile name")
    for key in ("network", "clipboard", "vgpu", "input_read_only", "evidence_writable", "allow_writable_share"):
        if type(data[key]) is not bool:
            raise ProfileValidationError(f"{key} must be a boolean")
    if data["clipboard"] or data["vgpu"] or not data["input_read_only"] or not data["evidence_writable"]:
        raise ProfileValidationError("clipboard/vGPU must be off; inputs read-only and evidence writable")
    if data["workspace_access"] not in ("none", "read-only", "read-write"):
        raise ProfileValidationError("invalid workspace_access")
    if data["name"] != "dev":
        if data["network"] != (data["name"] == "online-test"):
            raise ProfileValidationError("network conflicts with profile")
        if data["workspace_access"] != "none":
            raise ProfileValidationError("workspace sharing is dev-only")
    if data["allow_writable_share"] != (data["workspace_access"] == "read-write"):
        raise ProfileValidationError("writable workspace sharing requires explicit opt-in")


@dataclass(frozen=True)
class Profile:
    schema_version: int
    name: Literal["clean-room", "online-test", "dev"]
    network: bool
    clipboard: bool
    vgpu: bool
    input_read_only: bool
    evidence_writable: bool
    workspace_access: WorkspaceAccess
    allow_writable_share: bool
    warnings: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        _validate_profile({key: getattr(self, key) for key in _PROFILE_KEYS})
        if self.allow_writable_share:
            message = "Writable share exposes the host workspace to guest modification."
            object.__setattr__(self, "warnings", (message,))
            warnings.warn(message, ExposureWarning, stacklevel=2)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _read_json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


# WIRING-EXEMPT: EXPORTED_API reason="Isolation profile loader for planned PR 2/3 providers; roadmap: docs/design/blueprint-engram-architecture.md A2/A3"
def load_profile(path: Path, *, overrides: Mapping[str, object] | None = None) -> Profile:
    """Load version 1 JSON, rejecting unknown/missing fields and unsafe settings.

    Only dev accepts explicit network/workspace overrides. There are no implicit
    environment overrides or fallback profiles on load/validation failure.
    """
    try:
        data = _read_json(Path(path))
        _validate_profile(data)
        assert isinstance(data, dict)
        if overrides:
            allowed = {"network", "workspace_access", "allow_writable_share"}
            if data["name"] != "dev" or not set(overrides).issubset(allowed):
                raise ProfileValidationError("only explicit dev network/workspace overrides are allowed")
            data.update(overrides)
        _validate_profile(data)
        return Profile(**data)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise ProfileValidationError(f"Invalid isolation profile: {exc}") from exc


@dataclass(frozen=True)
class Handle:
    id: str
    evidence_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise ValueError("invalid handle id")
        object.__setattr__(self, "evidence_root", Path(self.evidence_root).resolve())


@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None
    execution_id: str
    status: ExecutionStatus

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or not _ID.fullmatch(self.execution_id):
            raise ValueError("invalid execution id")
        if self.status not in ("COMPLETED", "TIMED_OUT", "CANCELLED"):
            raise ValueError("invalid execution status")
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise ValueError("exit_code must be an integer or null")
        if self.status == "COMPLETED" and self.exit_code is None:
            raise ValueError("completed execution requires an exit code")


@dataclass(frozen=True)
class Evidence:
    reference: Path
    outcome: Outcome
    exit_code: int | None
    log_refs: tuple[Path, ...]


def _contained_path(root: Path, reference: str) -> Path:
    if not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference:
        raise EvidenceValidationError("invalid evidence reference")
    if PurePosixPath(reference).is_absolute() or PureWindowsPath(reference).drive:
        raise EvidenceValidationError("absolute evidence reference")
    if any(part in ("", ".", "..") or part.endswith((" ", ".")) for part in reference.split("/")):
        raise EvidenceValidationError("evidence path traversal or ambiguous component")
    path = (root / reference).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise EvidenceValidationError("evidence must be a file inside its execution directory")
    return path


# WIRING-EXEMPT: EXPORTED_API reason="Canonical evidence collector for planned PR 2/3 providers; roadmap: docs/design/blueprint-engram-architecture.md A2/A3"
def collect_guest_evidence(handle: Handle, execution_id: str) -> Evidence:
    """Read only the finalized guest result and validate schema, IDs and paths.

    Providers delegate collect_evidence here. Atomic publication is a producer
    obligation; a collector cannot infer write history from a finalized file.
    References are relative to evidence_root/execution_id and cannot escape it,
    including through symlinks/junctions. Both IDs reject stale evidence.
    """
    try:
        if not isinstance(execution_id, str) or not _ID.fullmatch(execution_id):
            raise EvidenceValidationError("invalid execution id")
        directory = (handle.evidence_root / execution_id).resolve(strict=True)
        if not directory.is_relative_to(handle.evidence_root) or directory == handle.evidence_root:
            raise EvidenceValidationError("execution directory escapes evidence mount")
        reference = _contained_path(directory, "result.json")
        data = _read_json(reference)
        if not isinstance(data, dict) or data.keys() != _RESULT_KEYS:
            raise EvidenceValidationError("result requires exactly the version 1 fields")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise EvidenceValidationError("unsupported result schema_version")
        if data["handle_id"] != handle.id or data["execution_id"] != execution_id:
            raise EvidenceValidationError("stale or mismatched execution identity")
        if data["complete"] is not True:
            raise EvidenceValidationError("guest result is incomplete")
        outcome, exit_code = data["outcome"], data["exit_code"]
        if outcome not in ("passed", "failed", "timed-out", "cancelled"):
            raise EvidenceValidationError("invalid guest outcome")
        if exit_code is not None and type(exit_code) is not int:
            raise EvidenceValidationError("exit_code must be an integer or null")
        if outcome == "passed" and (type(exit_code) is not int or exit_code != 0):
            raise EvidenceValidationError("passed result requires exit code zero")
        if outcome == "failed" and (type(exit_code) is not int or exit_code == 0):
            raise EvidenceValidationError("failed result requires nonzero exit code")
        if not isinstance(data["log_refs"], list):
            raise EvidenceValidationError("log_refs must be an array")
        log_refs = tuple(_contained_path(directory, value) for value in data["log_refs"])
        return Evidence(reference, outcome, exit_code, log_refs)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise EvidenceValidationError(f"Invalid guest evidence: {exc}") from exc


@runtime_checkable
class IsolationProvider(Protocol):
    """Structural provider port. Runtime conformance checks methods, not behavior."""

    def detect(self) -> Availability:
        """Never raise on probe failure; return UNAVAILABLE with a reason."""
        ...

    def create(self, profile: Profile, inputs: Sequence[Path], evidence_root: Path) -> Handle:
        """Create isolation; reject overlapping input/workspace/evidence mounts.

        Inputs are always read-only. Evidence is a dedicated writable mount.
        Reserve a fresh handle ID; never reuse execution directories or IDs.
        """
        ...

    def exec(self, handle: Handle, argv: Sequence[str], timeout: float) -> ExecResult:
        """Run argv with a positive timeout; report status, not canonical evidence."""
        ...

    def collect_evidence(self, handle: Handle, execution_id: str) -> Evidence:
        """Validate finalized guest evidence or raise EvidenceValidationError."""
        ...

    def destroy(self, handle: Handle) -> None:
        """Return only after verified teardown; any failure MUST raise."""
        ...
