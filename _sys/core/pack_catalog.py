"""Read-only admission of v1 TEST_ONLY package descriptors."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat

from core import cli_help

MAX_BYTES = 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9-]{0,47}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_DEVICE = re.compile(r"con|prn|aux|nul|(?:com|lpt)[1-9]")
_CAPS = {"python-extra", "ffmpeg", "nodejs", "local-llm", "local-gpu", "postgres",
         "browser", "tts", "asr", "cpu-render"}
_OPS = {"probe", "quiesce", "checkpoint", "migrate", "restore", "relocate", "health", "resume", "stop"}
_HEADER = {"fixture_only", "schema_version", "package_id", "slot_rel", "display_name", "host",
           "protocol_min", "protocol_max", "aliases", "profiles", "default_profile",
           "adapter_operations", "trust_key_ids"}
_PROFILE = {"id", "requires_capabilities", "optional_capabilities", "requires_packages"}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) and not _DEVICE.fullmatch(value)


def _strings(values, valid, minimum, maximum, field):
    _require(type(values) is list and minimum <= len(values) <= maximum, "invalid " + field)
    _require(all(type(v) is str and valid(v) for v in values), "invalid value in " + field)
    _require(len(set(values)) == len(values), "duplicate value in " + field)
    return tuple(values)


@dataclass(frozen=True)
class Profile:
    id: str
    required: tuple[str, ...]
    optional: tuple[str, ...]


@dataclass(frozen=True)
class Descriptor:
    package_id: str
    slot_rel: str
    aliases: tuple[str, ...]
    profiles: tuple[Profile, ...]
    default_profile: str
    operations: tuple[str, ...]


def _profile(row):
    _require(isinstance(row, dict) and row.keys() == _PROFILE, "invalid profile fields")
    _require(_identifier(row["id"]) and row["requires_packages"] == [], "invalid profile or dependency")
    required = _strings(row["requires_capabilities"], _CAPS.__contains__, 0, 32, "required capabilities")
    optional = _strings(row["optional_capabilities"], _CAPS.__contains__, 0, 32, "optional capabilities")
    _require(set(required).isdisjoint(optional), "ambiguous optional capability")
    return Profile(row["id"], required, optional)


def _descriptor(raw, slots):
    _require(type(raw) is bytes and len(raw) <= MAX_BYTES, "invalid descriptor payload")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except RecursionError as exc:
        raise ValueError("descriptor nesting exceeds parser limit") from exc
    _require(isinstance(doc, dict) and doc.keys() == _HEADER, "invalid descriptor fields")
    _require(doc["fixture_only"] is True and doc["host"] == "windows-x64", "unsupported fixture or host")
    _require(all(doc[k] == "1.0" for k in ("schema_version", "protocol_min", "protocol_max")),
             "unsupported descriptor or protocol version")
    package = doc["package_id"]
    _require(_identifier(package), "invalid package id")
    slot = doc["slot_rel"]
    _require(slot == slots.get(package, "packages/" + package), "slot differs from reviewed mapping")
    _require(isinstance(slot, str) and re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9-]{0,47}|packages/[a-z][a-z0-9-]{0,47})", slot)
             and not _DEVICE.fullmatch(slot.split("/")[-1].lower()), "invalid slot")
    label = doc["display_name"]
    _require(type(label) is str and 1 <= len(label) <= 512, "invalid display name")
    label.encode("utf-8")
    aliases = _strings(doc["aliases"], _identifier, 0, 8, "aliases")
    operations = _strings(doc["adapter_operations"], _OPS.__contains__, 0, 12, "adapter operations")
    _strings(doc["trust_key_ids"], _KEY.fullmatch, 1, 8, "key identifiers")
    rows = doc["profiles"]
    _require(type(rows) is list and 1 <= len(rows) <= 16, "invalid profiles")
    profiles = tuple(_profile(row) for row in rows)
    ids = [p.id for p in profiles]
    _require(len(set(ids)) == len(ids) and doc["default_profile"] in ids, "duplicate or missing profile")
    return Descriptor(package, slot, aliases, profiles, doc["default_profile"], operations)


def read_catalog(payloads, reviewed_slots):
    """The installation supplies slot policy independently of descriptor bytes."""
    claimed = set(cli_help.verbs()) | {"engram", "pack", "help", "start"}
    slots, catalog = set(), []
    for raw in payloads:
        entry = _descriptor(raw, reviewed_slots)
        names = {entry.package_id, *entry.aliases}
        _require(claimed.isdisjoint(names), "reserved or duplicate package/alias name")
        slot = entry.slot_rel.casefold()
        _require(not any(slot == old or slot.startswith(old + "/") or old.startswith(slot + "/")
                         for old in slots), "overlapping slots")
        claimed.update(names)
        slots.add(slot)
        catalog.append(entry)
    return tuple(sorted(catalog, key=lambda d: d.package_id))


def _ordinary_dir(path):
    info = path.lstat()
    return (stat.S_ISDIR(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _absent(root, rel):
    """A missing member proves absence only below an unambiguous ordinary directory."""
    current = root
    for part in rel.split("/"):
        if not _ordinary_dir(current):
            return False
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if not matches:
            return True
        if len(matches) != 1 or matches[0].name != part:
            return False
        current = matches[0]
    return False


def observe_slots(system_dir: Path, catalog):
    """Presence, ambiguous paths and any registry require further ownership evidence."""
    try:
        _require(_ordinary_dir(system_dir), "expected an ordinary physical system root")
        registry_absent = _absent(system_dir, "data/state/package-registry.json")
        return {d.package_id: "ABSENT" if registry_absent and _absent(system_dir, d.slot_rel)
                else "UNKNOWN" for d in catalog}
    except OSError as exc:
        raise ValueError("unable to inspect system root") from exc
