"""T44a shared, fail-closed reservation ledger for token-spending canaries."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
if str(_SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR / "core"))

from hub import _get_lock  # noqa: E402
from snapshot import _quota_family_for_profile  # noqa: E402


LEDGER_NAME = "canary_budget.json"
SCHEMA_VERSION = 2
VALID_KINDS = {"cli_canary", "capability_core", "long_context", "pty_spike"}
VALID_SOURCE_TAGS = {"app_server", "statusline", "cli_live", "absent"}


def _as_utc(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _ledger_path(ai_root: Path) -> Path:
    return Path(ai_root) / LEDGER_NAME


def _read_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    if not isinstance(loaded, dict) or not isinstance(loaded.get("entries"), list):
        return {"schema_version": SCHEMA_VERSION, "entries": []}
    return {"schema_version": SCHEMA_VERSION, "entries": list(loaded["entries"])}


def _atomic_write(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(ledger, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _prune_expired(entries: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    kept = []
    for entry in entries:
        expires_at = _parse_iso(entry.get("expires_at")) if isinstance(entry, dict) else None
        if expires_at is not None and expires_at > now:
            kept.append(entry)
    return kept


def _quota_pool(subject: str, orchestration: dict | None) -> str:
    if not isinstance(subject, str) or "." not in subject:
        return "absent"
    peer, profile = subject.split(".", 1)
    prefixes = _quota_family_for_profile(peer, profile, orchestration)
    if not prefixes:
        return "absent"
    return "+".join(prefix.rstrip("-") for prefix in prefixes)


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def reserve_canary_invocation(
    ai_root: Path,
    *,
    kind: str,
    subject: str,
    now: datetime | None = None,
    cap: int | None = None,
    window_hours: float | None = None,
    reserve_floor: float | None = None,
    quota_source_tag: str = "absent",
    quota_remaining: float | None = None,
    orchestration: dict | None = None,
) -> dict[str, Any]:
    """Atomically reserve one canary invocation, or return a denial reason.

    Unratified controls intentionally have no permissive defaults: omitted cap,
    window, or reserve floor means no invocation can be reserved.
    """
    if kind not in VALID_KINDS or not isinstance(subject, str) or not subject:
        return {"granted": False, "reason": "invalid_request"}
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        return {"granted": False, "reason": "budget_disabled"}
    if not _valid_number(window_hours) or float(window_hours) <= 0:
        return {"granted": False, "reason": "budget_disabled"}
    if not _valid_number(reserve_floor):
        return {"granted": False, "reason": "budget_disabled"}
    if quota_source_tag not in VALID_SOURCE_TAGS or quota_source_tag == "absent" or not _valid_number(quota_remaining):
        return {"granted": False, "reason": "quota_absent"}
    if float(quota_remaining) <= float(reserve_floor):
        return {"granted": False, "reason": "quota_below_reserve_floor"}

    now = _as_utc(now)
    ai_root = Path(ai_root)
    path = _ledger_path(ai_root)
    with _get_lock(ai_root, "canary_budget"):
        ledger = _read_ledger(path)
        entries = _prune_expired(ledger["entries"], now)
        cutoff = now - timedelta(hours=float(window_hours))
        used = sum(
            int(entry.get("reserved_invocations", 0))
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("state") in {"reserved", "consumed"}
            and (_parse_iso(entry.get("reserved_at")) or now) >= cutoff
        )
        if used >= cap:
            ledger["entries"] = entries
            _atomic_write(path, ledger)
            return {"granted": False, "reason": "budget"}

        entry = {
            "reservation_id": str(uuid.uuid4()),
            "kind": kind,
            "subject": subject,
            "reserved_at": _iso(now),
            "expires_at": _iso(now + timedelta(hours=float(window_hours))),
            "state": "reserved",
            "reserved_invocations": 1,
            "actual_tokens": None,
            "quota_source_tag": quota_source_tag,
            "quota_remaining": float(quota_remaining),
            "reserve_floor": float(reserve_floor),
            "quota_pool": _quota_pool(subject, orchestration),
        }
        entries.append(entry)
        ledger["entries"] = entries
        _atomic_write(path, ledger)
        return {"granted": True, "reservation_id": entry["reservation_id"], "entry": entry}


def _finalize(ai_root: Path, reservation_id: str, state: str, now: datetime | None, actual_tokens: Any = None) -> dict[str, Any] | None:
    now = _as_utc(now)
    ai_root = Path(ai_root)
    path = _ledger_path(ai_root)
    with _get_lock(ai_root, "canary_budget"):
        ledger = _read_ledger(path)
        entries = _prune_expired(ledger["entries"], now)
        for entry in entries:
            if entry.get("reservation_id") != reservation_id:
                continue
            if entry.get("state") != "reserved":
                return None
            entry["state"] = state
            if state == "consumed":
                entry["actual_tokens"] = float(actual_tokens) if _valid_number(actual_tokens) else None
            ledger["entries"] = entries
            _atomic_write(path, ledger)
            return dict(entry)
        ledger["entries"] = entries
        _atomic_write(path, ledger)
    return None


def consume_canary_reservation(
    ai_root: Path, reservation_id: str, *, actual_tokens: float | None = None, now: datetime | None = None
) -> dict[str, Any] | None:
    """Mark a successful invocation consumed; token count stays null unless supplied."""
    return _finalize(ai_root, reservation_id, "consumed", now, actual_tokens)


def release_canary_reservation(
    ai_root: Path, reservation_id: str, *, now: datetime | None = None
) -> dict[str, Any] | None:
    """Release an unused reservation after a launch failure or cancellation."""
    return _finalize(ai_root, reservation_id, "released", now)
