"""Observe an explicitly scoped TEST_ONLY registry and its local ownership receipts."""
import hashlib
import re
import stat

from optional_pack_catalog import MAX_BYTES, decode_document, inspect_path, observe_slots

REGISTRY = "data/state/package-registry.json"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SHA = re.compile(r"[a-f0-9]{64}")
_FIELDS = {"package_id", "state", "slot_rel", "profile", "active_generation", "previous_generation",
           "release_manifest_sha256", "runtime_binding_ids", "ownership_receipt_sha256"}


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _read(path, limit=MAX_BYTES):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError("expected an ordinary metadata file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    return decode_document(data), data


def _entries(doc, descriptors):
    if (type(doc) is not dict or doc.keys() != {"fixture_only", "schema_version", "installation_id",
                                                "revision", "entries"}
            or doc["fixture_only"] is not True or doc["schema_version"] != "1.0"
            or not _matches(_ID, doc["installation_id"])
            or type(doc["revision"]) is not int or not 1 <= doc["revision"] <= 2**53 - 1
            or type(doc["entries"]) is not list or len(doc["entries"]) > 128):
        raise ValueError("invalid fixture registry")
    indexed = {}
    for row in doc["entries"]:
        if type(row) is not dict or row.keys() != _FIELDS:
            raise ValueError("invalid registry entry")
        package = row["package_id"]
        descriptor = descriptors.get(package) if type(package) is str else None
        if (descriptor is None or package in indexed or row["slot_rel"] != descriptor.slot_rel
                or row["profile"] not in [p.id for p in descriptor.profiles]
                or row["state"] not in ("DATA_RETAINED", "INSTALLED", "PARTIAL")
                or not _matches(_SHA, row["ownership_receipt_sha256"])):
            raise ValueError("unresolved descriptor or inconsistent registry entry")
        active, previous, release = (row[k] for k in ("active_generation", "previous_generation",
                                                     "release_manifest_sha256"))
        bindings = row["runtime_binding_ids"]
        if (type(bindings) is not list or len(bindings) > 64
                or not all(_matches(_ID, b) for b in bindings) or len(set(bindings)) != len(bindings)
                or any(g is not None and not _matches(_ID, g) for g in (active, previous))
                or (active is not None and active == previous)
                or (release is not None and not _matches(_SHA, release))):
            raise ValueError("invalid generation or reference")
        if row["state"] == "DATA_RETAINED" and (active or previous or release or bindings):
            raise ValueError("retained data carries active or managed references")
        if row["state"] == "INSTALLED" and (active is None or release is None):
            raise ValueError("installed claim has no generation or release")
        indexed[package] = row
    return indexed


def _observe(root, entry, owner):
    status, marker = inspect_path(root, entry["slot_rel"] + "/state/ownership.json")
    if status == "absent":
        return "PARTIAL"
    if status == "ambiguous":
        return "UNKNOWN"
    try:
        doc, raw = _read(marker, 4096)
    except (OSError, ValueError):
        return "CORRUPT"
    identity = {"installation_id": owner, "package_id": entry["package_id"], "slot_rel": entry["slot_rel"]}
    if doc != identity:
        return "FOREIGN"
    if hashlib.sha256(raw).hexdigest() != entry["ownership_receipt_sha256"]:
        return "CORRUPT"
    return "DATA_RETAINED" if entry["state"] == "DATA_RETAINED" else "PARTIAL"


def observe_registry(root, catalog, installation_id):
    if not _matches(_ID, installation_id):
        raise ValueError("invalid expected fixture installation identity")
    slots = observe_slots(root, catalog)
    status, path = inspect_path(root, REGISTRY)
    if status == "absent":
        return slots
    if status == "ambiguous":
        return dict.fromkeys(slots, "UNKNOWN")
    descriptors = {entry.package_id: entry for entry in catalog}
    try:
        doc, _ = _read(path)
        entries = _entries(doc, descriptors)
    except (OSError, ValueError):
        return dict.fromkeys(slots, "CORRUPT")
    if doc["installation_id"] != installation_id:
        return dict.fromkeys(slots, "FOREIGN")
    return {package: (_observe(root, entries[package], installation_id) if package in entries
                      else "ABSENT" if inspect_path(root, descriptor.slot_rel)[0] == "absent" else "UNKNOWN")
            for package, descriptor in descriptors.items()}
