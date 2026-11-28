"""Pure install preview for reviewed TEST_ONLY records. No runtime or filesystem effects."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re

from optional_pack_catalog import Descriptor
from optional_pack_registry import _ID, _SHA, _matches

_MAX_INT = 2**53 - 1
_GENERATION = re.compile(r"gen-[a-z0-9][a-z0-9-]{0,63}")


@dataclass(frozen=True)
class Evidence:
    installation_id: str
    root_fingerprint: str
    pack_revision: int
    runtime_revision: int
    trust_revision: int
    policy_revision: int
    available_bytes: int
    slot_status: str


@dataclass(frozen=True)
class Intent:
    op_id: str
    target_generation: str
    manifest_sha256: str
    archive_bytes: int
    expanded_bytes: int
    environment_bytes: int
    created_at: datetime
    expires_at: datetime


def _number(value, low=0):
    return type(value) is int and low <= value <= _MAX_INT


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError("expected a UTC timestamp")
    return value.isoformat().removesuffix("+00:00") + "Z"


def _wire(document):
    return json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def install_preview(descriptor: Descriptor, evidence: Evidence, intent: Intent):
    """Compose one synthetic staging step for a validated descriptor and absent slot."""
    if (evidence.slot_status != "ABSENT" or not _matches(_ID, evidence.installation_id)
            or not _matches(_SHA, evidence.root_fingerprint)
            or not all(_number(n) for n in (evidence.pack_revision, evidence.runtime_revision,
                                            evidence.available_bytes))
            or not all(_number(n, 1) for n in (evidence.trust_revision, evidence.policy_revision))):
        raise ValueError("fixture root, slot or revision is unresolved")
    if (not _matches(_ID, intent.op_id) or not _matches(_GENERATION, intent.target_generation)
            or not _matches(_SHA, intent.manifest_sha256)):
        raise ValueError("invalid operation, generation or release identity")
    sizes = intent.archive_bytes, intent.expanded_bytes, intent.environment_bytes
    if not all(_number(n) for n in sizes) or sum(sizes) > evidence.available_bytes:
        raise ValueError("insufficient or invalid fixture storage")
    created, expires = _utc(intent.created_at), _utc(intent.expires_at)
    if intent.expires_at <= intent.created_at:
        raise ValueError("invalid preview interval")
    plan = {
        "fixture_only": True, "schema_version": "1.0", "op_id": intent.op_id,
        "installation_id": evidence.installation_id, "operation": "install",
        "expected_pack_revision": evidence.pack_revision, "expected_runtime_revision": evidence.runtime_revision,
        "root_fingerprint": evidence.root_fingerprint, "scope": [descriptor.package_id],
        "current_generation": None, "target_generation": intent.target_generation,
        "actions": [{"sequence": 1, "package_id": descriptor.package_id, "action": "stage",
                     "effect_class": "PROGRAM",
                     "target_rel": descriptor.slot_rel + "/app/generations/" + intent.target_generation,
                     "expected_digest": intent.manifest_sha256}],
        "required_bytes": sum(sizes), "risk": "normal", "trust_revision": evidence.trust_revision,
        "policy_revision": evidence.policy_revision, "created_at": created, "expires_at": expires,
    }
    plan["plan_digest"] = hashlib.sha256(b"EPP-PREVIEW-1\0" + _wire(plan)).hexdigest()
    return plan


def check_preview(plan, descriptor, evidence, intent, now):
    """Rebuild against fresh observations and reject altered or expired previews."""
    _utc(now)
    expected = install_preview(descriptor, evidence, intent)
    if not intent.created_at <= now < intent.expires_at:
        raise ValueError("fixture preview is outside its validity interval")
    if _wire(plan) != _wire(expected):
        raise ValueError("fixture preview is stale or altered")
