#!/usr/bin/env python3
"""Measured peer-CLI reality reconciliation and C11 observation store.

The hot dispatch path reads only ``.ai/cli-reality-observed.json``.  Binary
resolution, hashing, subprocess probes, and refreshes remain explicit or
background operations.  Missing or incomplete evidence is never promoted to a
negative; only a fresh, namespace-matched exhaustive catalog can hard-block a
dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from filelock import FileLock
except ImportError:  # pragma: no cover - portable runtime normally provides it
    FileLock = None  # type: ignore[assignment]


SYS_DIR = Path(__file__).resolve().parent.parent
_PORTABLE_ROOT = SYS_DIR.parent
_AI_DIR = _PORTABLE_ROOT / ".ai"
_CORE_DIR = SYS_DIR / "core"
_WRAPPER_DIR = (SYS_DIR / "cli").resolve()

if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from hub_peer import canonical_reality_model_key  # noqa: E402
from snapshot import CLI_REALITY_REFRESH_SLO_HOURS, telemetry_config  # noqa: E402


# Reconciliation verdicts retained for the drift-report interface.
VERDICT_MATCH = "MATCH"
VERDICT_DRIFT = "DRIFT"
VERDICT_ABSENT = "ABSENT"  # compatibility for non-model scalar probes
VERDICT_CONTRADICTED = "CONTRADICTED"
VERDICT_OBSERVED_ONLY = "OBSERVED_ONLY"
VERDICT_UNVERIFIED_INCOMPLETE = "UNVERIFIED_INCOMPLETE"
VERDICT_STALE_LAST_KNOWN_PRESENT = "STALE_LAST_KNOWN_PRESENT"
VERDICT_UNMEASURED = "UNMEASURED"

# Two-dimensional C11 evidence contract.
PROBE_COMPLETE = "COMPLETE"
PROBE_PARTIAL = "PARTIAL"
PROBE_FAILED = "FAILED"
PROBE_SKIPPED = "SKIPPED"
PROBE_ATTEMPT_STATUSES = {
    PROBE_COMPLETE,
    PROBE_PARTIAL,
    PROBE_FAILED,
    PROBE_SKIPPED,
}

EVIDENCE_COMPLETE_CATALOG = "COMPLETE_CATALOG"
EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY = "POSITIVE_CONFIRMATIONS_ONLY"
EVIDENCE_COMPLETENESS_VALUES = {
    EVIDENCE_COMPLETE_CATALOG,
    EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
}

REALITY_PRESENT = "PRESENT"
REALITY_CONTRADICTED = VERDICT_CONTRADICTED
REALITY_UNVERIFIED_INCOMPLETE = VERDICT_UNVERIFIED_INCOMPLETE
REALITY_STALE_LAST_KNOWN_PRESENT = VERDICT_STALE_LAST_KNOWN_PRESENT
REALITY_UNMEASURED = VERDICT_UNMEASURED

BOUNDARY_UNKNOWN_OR_DISABLED = "UNKNOWN_OR_DISABLED_PEER"
BOUNDARY_MISSING_CONFIGURED_PATH = "MISSING_CONFIGURED_PATH"
BOUNDARY_BARE_COMMAND_ABSENT = "BARE_COMMAND_ABSENT_FROM_PATH"
BOUNDARY_WRAPPER_REJECTED = "WRAPPER_TARGET_REJECTED"
BOUNDARY_BINARY_PRESENT = "BINARY_PRESENT"

OBSERVATION_STORE_SCHEMA_VERSION = 2
OBSERVATION_STORE_KIND = "cli_reality_observation_store"
OBSERVATION_STORE_FILENAME = "cli-reality-observed.json"

_VERSION_TOKEN_RE = re.compile(
    r"(?<![0-9A-Za-z.])v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)(?![0-9A-Za-z.])"
)
_PROCESS_STORE_LOCK = threading.RLock()
_STORE_MEMORY_LOCK = threading.RLock()
_STORE_MEMORY_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


@dataclass(frozen=True)
class BinaryObservationBoundary:
    """Read-only resolution result at the configured CLI boundary."""

    peer: str
    status: str
    configured_invoke: str | None
    launcher_path: Path | None
    fingerprint_path: Path | None
    fingerprint_kind: str | None
    detail: str | None = None

    @property
    def binary_present(self) -> bool:
        return self.status == BOUNDARY_BINARY_PRESENT and self.launcher_path is not None

    @property
    def provenance_verified(self) -> bool:
        if not self.binary_present or self.fingerprint_path is None:
            return False
        if self.launcher_path and self.launcher_path.suffix.casefold() == ".cmd":
            return self.fingerprint_path.resolve() != self.launcher_path.resolve()
        return True


@dataclass(frozen=True)
class VersionProbeResult:
    peer: str
    boundary: BinaryObservationBoundary
    attempt_status: str
    version: str | None
    returncode: int | None
    stdout: str
    stderr: str
    detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return (
            self.attempt_status == PROBE_COMPLETE
            and self.returncode == 0
            and self.version is not None
        )


@dataclass(frozen=True)
class CachedRealityStatus:
    """Cache-only dispatch verdict. ``hard_block`` is the authoritative gate."""

    profile_id: str
    peer_id: str
    reality_model_key: str
    status: str
    probe_attempt_status: str | None
    evidence_completeness: str | None
    identity_namespace: str | None
    captured_at: str | None
    age_seconds: float | None
    fresh: bool
    observed_present: bool
    hard_block: bool
    warning: bool
    reason: str

    @property
    def allow_dispatch(self) -> bool:
        return not self.hard_block


def _load_orchestration() -> dict[str, Any]:
    path = SYS_DIR / "ai" / "orchestration.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _enabled_peer_ids(orch: dict) -> list[str]:
    return [
        n["node_id"]
        for n in orch.get("hub_nodes", [])
        if n.get("type") == "peer"
        and n.get("enabled") is not False
        and n.get("node_id")
    ]


def is_wrapper(path: str | Path | BinaryObservationBoundary) -> bool:
    """True only for hub entry wrappers under ``_sys/cli``."""
    if isinstance(path, BinaryObservationBoundary):
        path = path.launcher_path or ""
    try:
        return Path(path).resolve().parent == _WRAPPER_DIR
    except (OSError, TypeError):
        return False


def _configured_path(invoke: str) -> tuple[Path | None, str | None]:
    if "/" not in invoke and "\\" not in invoke:
        resolved = shutil.which(invoke)
        return (Path(resolved).resolve(), None) if resolved else (None, "bare")
    path = Path(invoke)
    if not path.is_absolute():
        path = (_PORTABLE_ROOT / path).resolve()
    return path, None


def _codex_native_payload(codex_js: Path) -> Path | None:
    """Resolve @openai/codex's platform package to its native executable."""
    system = sys.platform
    machine = platform.machine().casefold()
    if system == "win32" and machine in {"amd64", "x86_64"}:
        package, triple, executable = (
            "@openai/codex-win32-x64",
            "x86_64-pc-windows-msvc",
            "codex.exe",
        )
    elif system == "win32" and machine in {"arm64", "aarch64"}:
        package, triple, executable = (
            "@openai/codex-win32-arm64",
            "aarch64-pc-windows-msvc",
            "codex.exe",
        )
    elif system == "darwin" and machine in {"arm64", "aarch64"}:
        package, triple, executable = (
            "@openai/codex-darwin-arm64",
            "aarch64-apple-darwin",
            "codex",
        )
    elif system == "darwin":
        package, triple, executable = (
            "@openai/codex-darwin-x64",
            "x86_64-apple-darwin",
            "codex",
        )
    elif machine in {"arm64", "aarch64"}:
        package, triple, executable = (
            "@openai/codex-linux-arm64",
            "aarch64-unknown-linux-musl",
            "codex",
        )
    else:
        package, triple, executable = (
            "@openai/codex-linux-x64",
            "x86_64-unknown-linux-musl",
            "codex",
        )

    package_parts = package.split("/")
    codex_root = codex_js.parent.parent
    candidates = [
        codex_root
        / "node_modules"
        / package_parts[0]
        / package_parts[1]
        / "vendor"
        / triple
        / "bin"
        / executable,
        codex_root / "vendor" / triple / "bin" / executable,
    ]
    return next((candidate.resolve() for candidate in candidates if candidate.exists()), None)


def _cmd_payload_target(peer: str, launcher: Path) -> tuple[Path, str]:
    """Follow npm's stable .cmd shim to the peer-appropriate implementation."""
    try:
        text = launcher.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return launcher, "launcher_fallback"

    matches = re.findall(
        r"%dp0%[\\/]+([^\"\r\n]+?\.(?:exe|js|cjs|mjs))",
        text,
        flags=re.IGNORECASE,
    )
    payloads = [(launcher.parent / rel.replace("\\", os.sep)).resolve() for rel in matches]
    existing = [path for path in payloads if path.exists() and path.name.casefold() != "node.exe"]

    if peer == "cx":
        codex_js = next(
            (path for path in existing if path.name.casefold() == "codex.js"),
            None,
        )
        if codex_js:
            native = _codex_native_payload(codex_js)
            if native is not None:
                return native, "npm_native_payload"

    if existing:
        target = next((path for path in existing if path.suffix.casefold() == ".exe"), existing[0])
        return target, "npm_payload"
    return launcher, "launcher_fallback"


def real_binary(peer: str, orch: dict | None = None) -> BinaryObservationBoundary:
    """Resolve the configured CLI without raising or performing installation.

    This is an observation boundary, not a provisioning hook.  Every expected
    failure mode is returned structurally so callers cannot accidentally turn
    an unknown/missing CLI into an exception-driven hard failure.
    """
    orch = orch if isinstance(orch, dict) else _load_orchestration()
    node = next(
        (
            n
            for n in orch.get("hub_nodes", [])
            if n.get("type") == "peer"
            and n.get("node_id") == peer
            and n.get("enabled") is not False
        ),
        None,
    )
    if node is None:
        return BinaryObservationBoundary(
            peer,
            BOUNDARY_UNKNOWN_OR_DISABLED,
            None,
            None,
            None,
            None,
            f"unknown or disabled peer {peer!r}",
        )

    invoke = node.get("invoke")
    if not isinstance(invoke, str) or not invoke.strip():
        return BinaryObservationBoundary(
            peer,
            BOUNDARY_MISSING_CONFIGURED_PATH,
            None,
            None,
            None,
            None,
            f"no invoke field for peer {peer!r}",
        )

    launcher, resolution_kind = _configured_path(invoke)
    if launcher is None:
        return BinaryObservationBoundary(
            peer,
            BOUNDARY_BARE_COMMAND_ABSENT,
            invoke,
            None,
            None,
            None,
            f"bare command {invoke!r} for peer {peer!r} not found on PATH",
        )
    if is_wrapper(launcher):
        return BinaryObservationBoundary(
            peer,
            BOUNDARY_WRAPPER_REJECTED,
            invoke,
            launcher,
            None,
            None,
            f"invoke path {launcher} for peer {peer!r} is a hub wrapper",
        )
    if not launcher.exists():
        return BinaryObservationBoundary(
            peer,
            BOUNDARY_MISSING_CONFIGURED_PATH,
            invoke,
            launcher,
            None,
            None,
            f"configured invoke path {launcher} does not exist",
        )

    if launcher.suffix.casefold() == ".cmd":
        fingerprint_path, fingerprint_kind = _cmd_payload_target(peer, launcher)
    else:
        fingerprint_path, fingerprint_kind = launcher.resolve(), "direct_binary"
    return BinaryObservationBoundary(
        peer,
        BOUNDARY_BINARY_PRESENT,
        invoke,
        launcher.resolve(),
        fingerprint_path,
        fingerprint_kind or resolution_kind or "direct_binary",
        None,
    )


def fingerprint(
    path: str | Path | BinaryObservationBoundary,
) -> dict[str, Any]:
    """SHA-256 provenance for an explicit/background observation.

    Passing a ``BinaryObservationBoundary`` hashes its real implementation
    payload, not an npm launcher shim.
    """
    if isinstance(path, BinaryObservationBoundary):
        selected = path.fingerprint_path
    else:
        selected = Path(path)
    if selected is None:
        return {
            "path": None,
            "exists": False,
            "sha256": None,
            "size": None,
            "mtime": None,
            "mtime_ns": None,
        }
    p = Path(selected)
    if not p.exists():
        return {
            "path": str(p),
            "exists": False,
            "sha256": None,
            "size": None,
            "mtime": None,
            "mtime_ns": None,
        }

    digest = hashlib.sha256()
    size = 0
    with p.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    stat = p.stat()
    return {
        "path": str(p.resolve()),
        "exists": True,
        "sha256": digest.hexdigest(),
        "size": size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "mtime_ns": stat.st_mtime_ns,
    }


def fingerprint_changed(current: dict, baseline: dict | None) -> bool:
    if not baseline:
        return True
    return current.get("sha256") != baseline.get("sha256")


def _fingerprint_hint(boundary: BinaryObservationBoundary) -> dict[str, Any]:
    """Cheap invalidation hint. Never treated as provenance evidence."""
    path = boundary.fingerprint_path
    if path is None:
        return {"path": None, "size": None, "mtime_ns": None}
    try:
        stat = path.stat()
    except OSError:
        return {"path": str(path), "size": None, "mtime_ns": None}
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _empty_store() -> dict[str, Any]:
    return {
        "schema_version": OBSERVATION_STORE_SCHEMA_VERSION,
        "kind": OBSERVATION_STORE_KIND,
        "updated_at": None,
        "peers": {},
    }


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if isinstance(item, str) and item.strip()})


def _model_keys(models: list[str]) -> list[str]:
    return sorted(
        {
            key
            for key in (canonical_reality_model_key(model) for model in models)
            if key
        }
    )


def _normalize_entry(peer: str, raw: Any, *, legacy: bool = False) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    models = _strings(raw.get("models"))
    confirmed = _strings(raw.get("confirmed_models")) or list(models)
    catalog = _strings(raw.get("catalog_models"))
    models_source = raw.get("models_source")

    attempt = raw.get("probe_attempt_status")
    evidence = raw.get("evidence_completeness")
    if attempt not in PROBE_ATTEMPT_STATUSES:
        attempt = PROBE_PARTIAL if models else PROBE_FAILED
    if evidence not in EVIDENCE_COMPLETENESS_VALUES:
        evidence = (
            EVIDENCE_COMPLETE_CATALOG
            if models_source == "enumerated"
            else EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY
        )
    if evidence == EVIDENCE_COMPLETE_CATALOG and not catalog:
        catalog = list(models)

    raw_binary = raw.get("binary")
    if isinstance(raw_binary, dict):
        binary = copy.deepcopy(raw_binary)
    else:
        old_fp = raw.get("fingerprint")
        fp = (
            copy.deepcopy(old_fp)
            if isinstance(old_fp, dict)
            else {"sha256": old_fp} if isinstance(old_fp, str) else {}
        )
        binary = {
            "launcher_path": None,
            "fingerprint_target_path": fp.get("path"),
            "fingerprint_kind": "legacy_unknown",
            "provenance_verified": False,
            "fingerprint": fp,
        }

    captured_at = raw.get("captured_at")
    last_attempt_at = raw.get("last_attempt_at") or captured_at
    last_success_at = raw.get("last_success_at")
    if not isinstance(last_success_at, str) and models:
        last_success_at = captured_at
    namespace = raw.get("identity_namespace") or f"peer:{peer}"
    all_models = sorted(set(models) | set(confirmed) | set(catalog))
    return {
        "peer_id": peer,
        "identity_namespace": str(namespace),
        "models": all_models,
        "model_keys": _strings(raw.get("model_keys")) or _model_keys(all_models),
        "confirmed_models": confirmed,
        "confirmed_model_keys": (
            _strings(raw.get("confirmed_model_keys")) or _model_keys(confirmed)
        ),
        "catalog_models": catalog,
        "catalog_model_keys": (
            _strings(raw.get("catalog_model_keys")) or _model_keys(catalog)
        ),
        "probe_attempt_status": attempt,
        "evidence_completeness": evidence,
        "captured_at": captured_at if isinstance(captured_at, str) else None,
        "last_attempt_at": last_attempt_at if isinstance(last_attempt_at, str) else None,
        "last_success_at": last_success_at if isinstance(last_success_at, str) else None,
        "provenance": copy.deepcopy(raw.get("provenance"))
        if isinstance(raw.get("provenance"), list)
        else [],
        "binary": binary,
        "legacy_migrated": bool(legacy or raw.get("legacy_migrated")),
    }


def _normalize_store(raw: Any) -> dict[str, Any]:
    store = _empty_store()
    if not isinstance(raw, dict):
        return store
    unified = (
        raw.get("kind") == OBSERVATION_STORE_KIND
        and isinstance(raw.get("peers"), dict)
    )
    source = raw.get("peers", {}) if unified else raw
    for peer, entry in source.items():
        if peer in {"schema_version", "kind", "updated_at", "peers"}:
            continue
        if not isinstance(peer, str):
            continue
        normalized = _normalize_entry(peer, entry, legacy=not unified)
        if normalized is not None:
            store["peers"][peer] = normalized
    if unified and isinstance(raw.get("updated_at"), str):
        store["updated_at"] = raw["updated_at"]
    return store


def _store_path(ai_root: Path) -> Path:
    return Path(ai_root) / OBSERVATION_STORE_FILENAME


def _lock_path(ai_root: Path) -> Path:
    return Path(ai_root) / ".lock" / f"{OBSERVATION_STORE_FILENAME}.lock"


@contextmanager
def _observation_store_lock(ai_root: Path, *, create: bool) -> Iterator[None]:
    lock_path = _lock_path(ai_root)
    if create:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    if FileLock is not None and lock_path.parent.exists():
        with FileLock(str(lock_path), timeout=10):
            yield
        return
    with _PROCESS_STORE_LOCK:
        yield


def _store_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _read_store_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    return _normalize_store(raw)


def read_observation_store(*, ai_root: Path) -> dict[str, Any]:
    """Read and normalize the single C11 store without probing or hashing."""
    path = _store_path(ai_root)
    signature = _store_signature(path)
    if signature is None:
        return _empty_store()
    key = str(path.resolve())
    with _STORE_MEMORY_LOCK:
        cached = _STORE_MEMORY_CACHE.get(key)
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])

    with _observation_store_lock(ai_root, create=False):
        store = _read_store_file(path)
        signature = _store_signature(path)
    if signature is not None:
        with _STORE_MEMORY_LOCK:
            _STORE_MEMORY_CACHE[key] = (signature, copy.deepcopy(store))
    return store


def _atomic_write_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _binary_sha(entry: dict[str, Any] | None) -> str | None:
    binary = (entry or {}).get("binary")
    fp = binary.get("fingerprint") if isinstance(binary, dict) else None
    return fp.get("sha256") if isinstance(fp, dict) else None


def _merge_entry(peer: str, prior: dict[str, Any] | None, update: dict[str, Any]) -> dict[str, Any]:
    normalized_update = _normalize_entry(peer, update) or _normalize_entry(peer, {})
    assert normalized_update is not None
    prior = _normalize_entry(peer, prior) if prior else None

    prior_sha = _binary_sha(prior)
    update_sha = _binary_sha(normalized_update)
    same_binary_namespace = (
        prior is not None
        and prior.get("identity_namespace") == normalized_update.get("identity_namespace")
        and (not prior_sha or not update_sha or prior_sha == update_sha)
    )

    prior_confirmed = prior.get("confirmed_models", []) if same_binary_namespace and prior else []
    confirmed = sorted(
        set(prior_confirmed) | set(normalized_update.get("confirmed_models", []))
    )

    update_attempt = normalized_update["probe_attempt_status"]
    update_evidence = normalized_update["evidence_completeness"]
    if (
        update_attempt == PROBE_COMPLETE
        and update_evidence == EVIDENCE_COMPLETE_CATALOG
    ):
        catalog = list(normalized_update.get("catalog_models") or normalized_update["models"])
        effective_evidence = EVIDENCE_COMPLETE_CATALOG
    else:
        # Retain the previous exact catalog only as provenance. A later
        # partial/failed/skipped attempt can never refresh a hard negative.
        catalog = (
            list(prior.get("catalog_models", []))
            if same_binary_namespace and prior
            else []
        )
        effective_evidence = EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY

    models = sorted(set(confirmed) | set(catalog) | set(normalized_update["models"]))
    prior_provenance = prior.get("provenance", []) if same_binary_namespace and prior else []
    provenance = (list(prior_provenance) + list(normalized_update.get("provenance", [])))[-500:]
    binary = normalized_update.get("binary") or (prior.get("binary") if prior else {})
    update_has_positive_evidence = bool(
        normalized_update.get("confirmed_models")
        or (
            update_attempt == PROBE_COMPLETE
            and update_evidence == EVIDENCE_COMPLETE_CATALOG
        )
    )
    # ``captured_at`` timestamps the evidence used by the dispatch verdict,
    # not merely the latest attempt. A failed/skipped refresh must not make
    # old confirmations look fresh; ``last_attempt_at`` records that event.
    captured_at = (
        normalized_update.get("captured_at")
        if update_has_positive_evidence
        else prior.get("captured_at") if same_binary_namespace and prior else None
    )
    last_success_at = (
        normalized_update.get("captured_at")
        if update_has_positive_evidence
        else prior.get("last_success_at") if same_binary_namespace and prior else None
    )
    return {
        "peer_id": peer,
        "identity_namespace": normalized_update.get("identity_namespace") or f"peer:{peer}",
        "models": models,
        "model_keys": _model_keys(models),
        "confirmed_models": confirmed,
        "confirmed_model_keys": _model_keys(confirmed),
        "catalog_models": sorted(set(catalog)),
        "catalog_model_keys": _model_keys(catalog),
        "probe_attempt_status": update_attempt,
        "evidence_completeness": effective_evidence,
        "captured_at": captured_at,
        "last_attempt_at": normalized_update.get("last_attempt_at") or captured_at,
        "last_success_at": last_success_at,
        "provenance": provenance,
        "binary": copy.deepcopy(binary),
        "legacy_migrated": False,
    }


def merge_observation_updates(
    updates: dict[str, dict[str, Any]],
    *,
    ai_root: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically merge producer updates into the unified observation store."""
    now = now or datetime.now(timezone.utc)
    root = Path(ai_root)
    path = _store_path(root)
    with _observation_store_lock(root, create=True):
        store = _read_store_file(path)
        peers = store.setdefault("peers", {})
        for peer, update in updates.items():
            if not isinstance(peer, str) or not isinstance(update, dict):
                continue
            peers[peer] = _merge_entry(peer, peers.get(peer), update)
        store["schema_version"] = OBSERVATION_STORE_SCHEMA_VERSION
        store["kind"] = OBSERVATION_STORE_KIND
        store["updated_at"] = now.astimezone(timezone.utc).isoformat()
        _atomic_write_store(path, store)
        signature = _store_signature(path)
    if signature is not None:
        with _STORE_MEMORY_LOCK:
            _STORE_MEMORY_CACHE[str(path.resolve())] = (
                signature,
                copy.deepcopy(store),
            )
    return copy.deepcopy(store)


def _refresh_slo_hours() -> float:
    try:
        value = telemetry_config()["cli_reality"]["refresh_slo_hours"]
        parsed = float(value)
        return parsed if parsed > 0 else float(CLI_REALITY_REFRESH_SLO_HOURS)
    except (KeyError, TypeError, ValueError):
        return float(CLI_REALITY_REFRESH_SLO_HOURS)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # Observation-store v2 writes aware UTC. Legacy naive captures have no
        # trustworthy timezone provenance and therefore cannot hard-block.
        return None
    return parsed.astimezone(timezone.utc)


def _coerce_now(now: datetime | float | int) -> datetime:
    if isinstance(now, datetime):
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
    return datetime.fromtimestamp(float(now), timezone.utc)


def classify_reality_evidence(
    *,
    model_present: bool,
    probe_attempt_status: str,
    evidence_completeness: str,
    fresh: bool,
    provenance_verified: bool = True,
) -> tuple[str, bool]:
    """Pure 4x2 evidence matrix. Returns ``(status, hard_block)``."""
    if not fresh:
        return REALITY_STALE_LAST_KNOWN_PRESENT, False
    if model_present:
        return REALITY_PRESENT, False
    if (
        probe_attempt_status == PROBE_COMPLETE
        and evidence_completeness == EVIDENCE_COMPLETE_CATALOG
        and provenance_verified
    ):
        return REALITY_CONTRADICTED, True
    return REALITY_UNVERIFIED_INCOMPLETE, False


def _dispatch_target_parts(dispatch_target: Any) -> tuple[str, str, str]:
    if isinstance(dispatch_target, dict):
        profile_id = str(dispatch_target.get("profile_id") or "")
        reality_key = str(dispatch_target.get("reality_model_key") or "")
    else:
        profile_id = str(getattr(dispatch_target, "profile_id", "") or "")
        reality_key = str(getattr(dispatch_target, "reality_model_key", "") or "")
    peer_id = profile_id.split(".", 1)[0] if profile_id else ""
    return profile_id, peer_id, canonical_reality_model_key(reality_key)


def get_cached_reality_status(
    dispatch_target: Any,
    *,
    ai_root: Path,
    now: datetime | float | int,
) -> CachedRealityStatus:
    """Pure cache reader for dispatch (<1ms warm; no subprocess or SHA-256)."""
    profile_id, peer_id, reality_key = _dispatch_target_parts(dispatch_target)

    def unmeasured(reason: str, *, namespace: str | None = None) -> CachedRealityStatus:
        return CachedRealityStatus(
            profile_id=profile_id,
            peer_id=peer_id,
            reality_model_key=reality_key,
            status=REALITY_UNMEASURED,
            probe_attempt_status=None,
            evidence_completeness=None,
            identity_namespace=namespace,
            captured_at=None,
            age_seconds=None,
            fresh=False,
            observed_present=False,
            hard_block=False,
            warning=True,
            reason=reason,
        )

    if not profile_id or not peer_id or not reality_key:
        return unmeasured("dispatch_identity_incomplete")
    store = read_observation_store(ai_root=Path(ai_root))
    entry = store.get("peers", {}).get(peer_id)
    if not isinstance(entry, dict):
        return unmeasured("no_cache_entry")

    expected_namespace = f"peer:{peer_id}"
    namespace = entry.get("identity_namespace")
    if namespace != expected_namespace:
        return unmeasured("identity_namespace_mismatch", namespace=str(namespace))

    captured = _parse_utc(entry.get("captured_at"))
    if captured is None:
        return unmeasured("invalid_or_legacy_naive_capture_timestamp", namespace=namespace)
    now_utc = _coerce_now(now)
    age_seconds = max(0.0, (now_utc - captured).total_seconds())
    fresh = age_seconds <= (_refresh_slo_hours() * 3600.0)

    attempt = entry.get("probe_attempt_status")
    evidence = entry.get("evidence_completeness")
    if attempt not in PROBE_ATTEMPT_STATUSES or evidence not in EVIDENCE_COMPLETENESS_VALUES:
        return unmeasured("invalid_evidence_dimensions", namespace=namespace)

    # An exhaustive catalog is authoritative for negatives. Older positive
    # confirmations are retained in the store for provenance/merge purposes,
    # but cannot mask an absence in a newer complete catalog.
    if (
        attempt == PROBE_COMPLETE
        and evidence == EVIDENCE_COMPLETE_CATALOG
    ):
        keys = set(_strings(entry.get("catalog_model_keys")))
    else:
        keys = set(_strings(entry.get("model_keys")))
    model_present = reality_key in keys
    binary = entry.get("binary") if isinstance(entry.get("binary"), dict) else {}
    binary_fp = (
        binary.get("fingerprint")
        if isinstance(binary.get("fingerprint"), dict)
        else {}
    )
    sha256 = binary_fp.get("sha256")
    provenance_verified = bool(
        binary.get("provenance_verified")
        and isinstance(sha256, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
    )
    status, hard_block = classify_reality_evidence(
        model_present=model_present,
        probe_attempt_status=attempt,
        evidence_completeness=evidence,
        fresh=fresh,
        provenance_verified=provenance_verified,
    )
    reason = {
        REALITY_PRESENT: "model_key_present_in_cached_evidence",
        REALITY_CONTRADICTED: "fresh_verified_complete_catalog_missing_model_key",
        REALITY_UNVERIFIED_INCOMPLETE: "missing_model_key_without_complete_successful_catalog",
        REALITY_STALE_LAST_KNOWN_PRESENT: "refresh_slo_exceeded",
    }[status]
    return CachedRealityStatus(
        profile_id=profile_id,
        peer_id=peer_id,
        reality_model_key=reality_key,
        status=status,
        probe_attempt_status=attempt,
        evidence_completeness=evidence,
        identity_namespace=namespace,
        captured_at=entry.get("captured_at"),
        age_seconds=age_seconds,
        fresh=fresh,
        observed_present=model_present,
        hard_block=hard_block,
        warning=status != REALITY_PRESENT,
        reason=reason,
    )


def load_observed_models(peer: str, *, ai_root: Path) -> list[str] | None:
    """Compatibility reader that retains the unified store's metadata elsewhere."""
    entry = read_observation_store(ai_root=ai_root).get("peers", {}).get(peer)
    if not isinstance(entry, dict):
        return None
    models = _strings(entry.get("models"))
    return models or None


def classify_model(
    declared: str,
    actual_list: list[str] | None,
    *,
    probe_attempt_status: str = PROBE_COMPLETE,
    evidence_completeness: str = EVIDENCE_COMPLETE_CATALOG,
    fresh: bool = True,
    provenance_verified: bool = True,
) -> str:
    if actual_list is None:
        return VERDICT_UNMEASURED
    present = canonical_reality_model_key(declared) in set(_model_keys(actual_list))
    status, _ = classify_reality_evidence(
        model_present=present,
        probe_attempt_status=probe_attempt_status,
        evidence_completeness=evidence_completeness,
        fresh=fresh,
        provenance_verified=provenance_verified,
    )
    return VERDICT_MATCH if status == REALITY_PRESENT else status


def classify_scalar(declared: Any, observed: Any) -> str:
    if observed is None:
        return VERDICT_ABSENT
    if declared is None:
        return VERDICT_OBSERVED_ONLY
    return VERDICT_MATCH if str(declared) == str(observed) else VERDICT_DRIFT


def _severity(verdict: str) -> str:
    return {
        VERDICT_CONTRADICTED: "P0",
        VERDICT_DRIFT: "P1",
        VERDICT_ABSENT: "P2",
        VERDICT_UNMEASURED: "P2",
        VERDICT_UNVERIFIED_INCOMPLETE: "P2",
        VERDICT_STALE_LAST_KNOWN_PRESENT: "P2",
        VERDICT_MATCH: "ok",
        VERDICT_OBSERVED_ONLY: "info",
    }[verdict]


def _model_observation(entry: dict[str, Any] | None, declared: str) -> tuple[str, Any]:
    if not isinstance(entry, dict):
        return VERDICT_UNMEASURED, None
    models = _strings(entry.get("models"))
    attempt = entry.get("probe_attempt_status", PROBE_FAILED)
    evidence = entry.get("evidence_completeness", EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY)
    if (
        attempt == PROBE_COMPLETE
        and evidence == EVIDENCE_COMPLETE_CATALOG
        and "catalog_models" in entry
    ):
        compared_models = _strings(entry.get("catalog_models"))
    else:
        compared_models = models
    captured = _parse_utc(entry.get("captured_at"))
    fresh = bool(
        captured
        and (datetime.now(timezone.utc) - captured).total_seconds()
        <= _refresh_slo_hours() * 3600.0
    )
    binary = entry.get("binary") if isinstance(entry.get("binary"), dict) else {}
    binary_fp = (
        binary.get("fingerprint")
        if isinstance(binary.get("fingerprint"), dict)
        else {}
    )
    sha256 = binary_fp.get("sha256")
    verdict = classify_model(
        declared,
        compared_models,
        probe_attempt_status=attempt,
        evidence_completeness=evidence,
        fresh=fresh,
        provenance_verified=bool(
            binary.get("provenance_verified")
            and isinstance(sha256, str)
            and re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
        ),
    )
    observed = (
        declared
        if canonical_reality_model_key(declared) in set(_model_keys(compared_models))
        else None
    )
    return verdict, observed


def reconcile_peer(
    peer: str,
    declared_models: list[str],
    observed: dict[str, Any],
    orch: dict | None = None,
) -> dict[str, Any]:
    entry = observed.get("observation_entry")
    if entry is None and observed.get("actual_models") is not None:
        # Compatibility for pure callers that explicitly supply a complete list.
        entry = {
            "models": observed["actual_models"],
            "catalog_models": observed["actual_models"],
            "probe_attempt_status": PROBE_COMPLETE,
            "evidence_completeness": EVIDENCE_COMPLETE_CATALOG,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "binary": {
                "provenance_verified": True,
                "fingerprint": {"sha256": "0" * 64},
            },
        }
    model_probes = []
    for model in declared_models:
        verdict, observed_value = _model_observation(entry, model)
        model_probes.append(
            {
                "kind": "model",
                "declared": model,
                "observed": observed_value,
                "verdict": verdict,
            }
        )

    version_value = observed.get("version")
    version_result = observed.get("version_result")
    if isinstance(version_result, VersionProbeResult):
        version_value = version_result.version
    version_verdict = classify_scalar(observed.get("declared_version"), version_value)
    probes = [
        {
            "kind": "version",
            "declared": observed.get("declared_version"),
            "observed": version_value,
            "verdict": version_verdict,
        },
        *model_probes,
    ]
    for probe in probes:
        probe["severity"] = _severity(probe["verdict"])

    boundary = observed.get("binary_boundary")
    if not isinstance(boundary, BinaryObservationBoundary):
        boundary = real_binary(peer, orch)
    return {
        "peer": peer,
        "binary": str(boundary.launcher_path) if boundary.launcher_path else None,
        "binary_boundary_status": boundary.status,
        "fingerprint": observed.get("fingerprint"),
        "probes": probes,
        "drift": [
            probe
            for probe in probes
            if probe["verdict"] in (VERDICT_DRIFT, VERDICT_CONTRADICTED)
        ],
        "warnings": [
            probe
            for probe in probes
            if probe["verdict"]
            in {
                VERDICT_ABSENT,
                VERDICT_UNMEASURED,
                VERDICT_UNVERIFIED_INCOMPLETE,
                VERDICT_STALE_LAST_KNOWN_PRESENT,
            }
        ],
    }


def build_report(peer_reports: list[dict], observed_at: str | None = None) -> dict[str, Any]:
    all_drift = [
        {"peer": report["peer"], **item}
        for report in peer_reports
        for item in report["drift"]
    ]
    warnings = [
        {"peer": report["peer"], **item}
        for report in peer_reports
        for item in report.get("warnings", [])
    ]
    return {
        "schema_version": 2,
        "kind": "cli_reality_drift_report",
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "peers": peer_reports,
        "drift_summary": {
            "total": len(all_drift),
            "p0": sum(1 for item in all_drift if item["severity"] == "P0"),
            "p1": sum(1 for item in all_drift if item["severity"] == "P1"),
            "items": all_drift,
            "warnings": warnings,
        },
        "note": "Overlay only. Never mutates orchestration.json; declaration changes require consensus.",
    }


def probe_version(
    peer: str,
    orch: dict | None = None,
    timeout: int = 20,
) -> VersionProbeResult:
    """Probe ``--version`` and require rc=0 plus a token in stdout+stderr."""
    boundary = real_binary(peer, orch)
    if not boundary.binary_present or boundary.launcher_path is None:
        return VersionProbeResult(
            peer,
            boundary,
            PROBE_SKIPPED,
            None,
            None,
            "",
            "",
            boundary.detail,
        )
    try:
        result = subprocess.run(
            [str(boundary.launcher_path), "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return VersionProbeResult(
            peer,
            boundary,
            PROBE_FAILED,
            None,
            None,
            "",
            "",
            f"{type(exc).__name__}: {exc}",
        )

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        return VersionProbeResult(
            peer,
            boundary,
            PROBE_FAILED,
            None,
            result.returncode,
            stdout,
            stderr,
            "nonzero_exit",
        )
    match = _VERSION_TOKEN_RE.search(f"{stdout}\n{stderr}")
    if not match:
        return VersionProbeResult(
            peer,
            boundary,
            PROBE_FAILED,
            None,
            result.returncode,
            stdout,
            stderr,
            "version_token_absent",
        )
    return VersionProbeResult(
        peer,
        boundary,
        PROBE_COMPLETE,
        match.group(1),
        result.returncode,
        stdout,
        stderr,
        None,
    )


def probe_enumerated_models(
    peer: str,
    orch: dict | None = None,
    timeout: int = 20,
) -> list[str] | None:
    """Run only an explicitly declared, non-interactive catalog command."""
    orch = orch if isinstance(orch, dict) else _load_orchestration()
    node = next((n for n in orch.get("hub_nodes", []) if n.get("node_id") == peer), None)
    argv = (node or {}).get("model_enumeration_argv")
    if not isinstance(argv, list) or not argv:
        return None
    boundary = real_binary(peer, orch)
    if not boundary.binary_present or boundary.launcher_path is None:
        return None
    try:
        result = subprocess.run(
            [str(boundary.launcher_path), *[str(item) for item in argv]],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    models = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return sorted(set(models)) or None


def _declared(orch: dict, peer: str) -> tuple[list[str], str | None]:
    node = next((n for n in orch.get("hub_nodes", []) if n.get("node_id") == peer), None)
    if not node:
        return [], None
    models: list[str] = []
    for profile_cfg in (node.get("profiles") or {}).values():
        model_id = profile_cfg.get("model_id") or profile_cfg.get("runtime_model")
        if model_id:
            models.append(str(model_id))
    return models, None


def run(
    orch: dict | None = None,
    live: bool = True,
    *,
    ai_root: Path,
) -> dict[str, Any]:
    """Reconcile enabled peers; only ``live=True`` hashes or spawns."""
    orch = orch if isinstance(orch, dict) else _load_orchestration()
    store = read_observation_store(ai_root=ai_root)
    reports = []
    for peer in _enabled_peer_ids(orch):
        declared_models, declared_version = _declared(orch, peer)
        boundary = real_binary(peer, orch)
        version_result = probe_version(peer, orch) if live else None
        if live and boundary.binary_present:
            fp = fingerprint(boundary)
        else:
            entry_binary = (
                store.get("peers", {}).get(peer, {}).get("binary", {})
                if isinstance(store.get("peers", {}).get(peer), dict)
                else {}
            )
            fp = entry_binary.get("fingerprint") if isinstance(entry_binary, dict) else None
        reports.append(
            reconcile_peer(
                peer,
                declared_models,
                {
                    "binary_boundary": boundary,
                    "fingerprint": fp,
                    "declared_version": declared_version,
                    "version_result": version_result,
                    "version": version_result.version if version_result else None,
                    "observation_entry": store.get("peers", {}).get(peer),
                },
                orch,
            )
        )
    return build_report(reports)


def _entry_age_seconds(entry: dict[str, Any] | None, now_ts: float) -> float | None:
    if not isinstance(entry, dict):
        return None
    captured = _parse_utc(entry.get("last_success_at"))
    if captured is None:
        return None
    return max(0.0, now_ts - captured.timestamp())


def _hint_matches(entry: dict[str, Any] | None, hint: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    binary = entry.get("binary")
    fp = binary.get("fingerprint") if isinstance(binary, dict) else None
    if not isinstance(fp, dict):
        return False
    return (
        fp.get("path") == hint.get("path")
        and fp.get("size") == hint.get("size")
        and fp.get("mtime_ns") == hint.get("mtime_ns")
        and fp.get("sha256") is not None
    )


def binary_observation_block(
    boundary: BinaryObservationBoundary,
    fp: dict[str, Any],
) -> dict[str, Any]:
    sha256 = fp.get("sha256")
    provenance_verified = bool(
        boundary.provenance_verified
        and fp.get("exists")
        and isinstance(sha256, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
    )
    return {
        "launcher_path": str(boundary.launcher_path) if boundary.launcher_path else None,
        "fingerprint_target_path": (
            str(boundary.fingerprint_path) if boundary.fingerprint_path else None
        ),
        "fingerprint_kind": boundary.fingerprint_kind,
        "provenance_verified": provenance_verified,
        "fingerprint": copy.deepcopy(fp),
    }


def auto_refresh_observed(
    orch: dict | None = None,
    *,
    ai_root: Path,
    interval_hours: float | None = None,
    now_ts: float | None = None,
) -> dict[str, str]:
    """Budgeted background refresh; no automatic scheduler is created here."""
    orch = orch if isinstance(orch, dict) else _load_orchestration()
    now_ts = (
        float(now_ts)
        if now_ts is not None
        else datetime.now(timezone.utc).timestamp()
    )
    now_dt = datetime.fromtimestamp(now_ts, timezone.utc)
    slo_hours = float(interval_hours) if interval_hours is not None else _refresh_slo_hours()
    store = read_observation_store(ai_root=ai_root)
    existing = store.get("peers", {})

    import check_cli_canary

    results: dict[str, str] = {}
    updates: dict[str, dict[str, Any]] = {}
    nodes = {
        node.get("node_id"): node
        for node in orch.get("hub_nodes", [])
        if node.get("node_id")
    }

    for peer in _enabled_peer_ids(orch):
        prior = existing.get(peer) if isinstance(existing, dict) else None
        boundary = real_binary(peer, orch)
        if not boundary.binary_present:
            updates[peer] = {
                "identity_namespace": f"peer:{peer}",
                "models": [],
                "confirmed_models": [],
                "probe_attempt_status": PROBE_FAILED,
                "evidence_completeness": EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
                "captured_at": now_dt.isoformat(),
                "last_attempt_at": now_dt.isoformat(),
                "provenance": [
                    {
                        "kind": "binary_boundary",
                        "status": boundary.status,
                        "ts": now_dt.isoformat(),
                        "detail": boundary.detail,
                    }
                ],
                "binary": binary_observation_block(boundary, {}),
            }
            results[peer] = f"boundary_{boundary.status.lower()}"
            continue

        age = _entry_age_seconds(prior, now_ts)
        interval_expired = age is None or age >= slo_hours * 3600.0
        hint = _fingerprint_hint(boundary)
        if not interval_expired and _hint_matches(prior, hint):
            results[peer] = "interval_not_expired"
            continue

        fp_info = fingerprint(boundary)
        prior_sha = _binary_sha(prior if isinstance(prior, dict) else None)
        current_sha = fp_info.get("sha256")
        if not interval_expired and prior_sha and current_sha == prior_sha:
            results[peer] = "interval_not_expired"
            continue

        verdicts = check_cli_canary.run_canary(
            orch=orch,
            peers=[peer],
            all_profiles=True,
            force=True,
            ai_root=ai_root,
        )
        capture = check_cli_canary.build_observed_capture(
            verdicts,
            now=now_dt,
            expected_peers=[peer],
        )
        update = capture.get(peer) or {
            "identity_namespace": f"peer:{peer}",
            "models": [],
            "confirmed_models": [],
            "probe_attempt_status": PROBE_FAILED,
            "evidence_completeness": EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
            "captured_at": now_dt.isoformat(),
            "last_attempt_at": now_dt.isoformat(),
            "provenance": [],
        }

        enumerated = probe_enumerated_models(peer, orch)
        enumeration_configured = bool((nodes.get(peer) or {}).get("model_enumeration_argv"))
        if enumerated:
            update["models"] = sorted(set(enumerated))
            update["catalog_models"] = sorted(set(enumerated))
            update["probe_attempt_status"] = PROBE_COMPLETE
            update["evidence_completeness"] = EVIDENCE_COMPLETE_CATALOG
            update.setdefault("provenance", []).append(
                {
                    "kind": "catalog_enumeration",
                    "status": "PASS",
                    "models": sorted(set(enumerated)),
                    "ts": now_dt.isoformat(),
                }
            )
        elif enumeration_configured and update.get("probe_attempt_status") == PROBE_COMPLETE:
            # The positive canary fan-out completed, but the exhaustive
            # namespace probe failed. The overall attempt is therefore partial.
            update["probe_attempt_status"] = PROBE_PARTIAL
            update.setdefault("provenance", []).append(
                {
                    "kind": "catalog_enumeration",
                    "status": "FAIL",
                    "ts": now_dt.isoformat(),
                }
            )

        update["binary"] = binary_observation_block(boundary, fp_info)
        update["last_attempt_at"] = now_dt.isoformat()
        updates[peer] = update

        positive_models = _strings(update.get("confirmed_models")) or _strings(update.get("models"))
        attempt = update.get("probe_attempt_status")
        if enumerated or positive_models:
            results[peer] = "refreshed"
        elif attempt == PROBE_SKIPPED:
            peer_verdicts = [v for v in verdicts if v.get("peer") == peer]
            reasons = sorted({str(v.get("reason") or "unknown") for v in peer_verdicts})
            results[peer] = f"skipped_{'+'.join(reasons)}"
        else:
            results[peer] = "probe_failed"

    if updates:
        merge_observation_updates(updates, ai_root=ai_root, now=now_dt)
    return results


_PEER_KEY_BY_NODE_ID = {
    "cc": "claude",
    "ca": "claude",
    "cx": "codex",
    "ag": "antigravity",
}


def _repair_missing_peers(orch: dict) -> dict[str, dict]:
    sys.path.insert(0, str(SYS_DIR / "core"))
    import provisioner  # noqa: E402

    repaired = {}
    for peer in _enabled_peer_ids(orch):
        boundary = real_binary(peer, orch)
        if boundary.binary_present:
            continue
        peer_key = _PEER_KEY_BY_NODE_ID.get(peer, peer)
        result = provisioner.ensure_peer_cli(peer_key)
        repaired[peer] = result
        print(f"[cli-reality] repaired {peer} ({peer_key}): {result}")
    return repaired


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--auto-refresh" in argv:
        refresh_results = auto_refresh_observed(ai_root=_AI_DIR)
        print(
            f"[cli-reality] auto-refresh: "
            f"{json.dumps(refresh_results, ensure_ascii=False)}"
        )

    live = "--no-live" not in argv
    if "--repair-missing" in argv:
        _repair_missing_peers(_load_orchestration())

    report = run(live=live, ai_root=_AI_DIR)
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        summary = report["drift_summary"]
        print(
            f"[cli-reality] drift: {summary['total']} "
            f"(P0={summary['p0']} P1={summary['p1']}) "
            f"checked_at={report['observed_at']}"
        )
        for item in summary["items"]:
            print(
                f"  {item['severity']:>2} {item['peer']}.{item['kind']}: "
                f"{item['verdict']} declared={item['declared']!r} "
                f"observed={item['observed']!r}"
            )
        if not summary["items"]:
            print("  (no hard drift; unmeasured/incomplete evidence remains warning-only)")
    return 2 if report["drift_summary"]["p0"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
