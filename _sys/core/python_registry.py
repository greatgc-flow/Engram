"""Local inventory and journaled metadata publication for optional CPython builds."""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path

from core import env_lock, env_manifest, env_ops, provisioner

KIND = "python-registry"
STEP = "publish-python-registry"
FILENAME = "python-registry.json"
DEFAULT = "legacy-default"
_MAX_BYTES = 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SERIES = re.compile(r"3\.(?:0|[1-9][0-9]*)")
_FIELDS = "schema_version revision installation_id default_binding series builds bindings environments external_refs vendor_exceptions rollback_refs"
_BUILD = "implementation series version abi arch provider flavor sha256 artifact_ref executable_rel state owner"


class RegistryError(ValueError):
    """Registry metadata cannot be accepted or the expected revision changed."""


def _require(condition, detail):
    if not condition:
        raise RegistryError(detail)


def _shape(record, fields):
    _require(isinstance(record, dict) and record.keys() == set(fields.split()),
             f"expected registry fields: {fields}")


def _identifier(value):
    _require(isinstance(value, str) and _ID.fullmatch(value) and not value.endswith(".")
             and not re.match(r"(?i)^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:[.]|$)", value), "invalid registry identifier")
    return value


def _plain(root, relative):
    """Inspect each existing component without following a Windows reparse point."""
    path = root
    for part in ("", *relative.split("/")):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        _require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
            "registry path traverses a link or reparse point")
    return path


def _state_file(root, name=FILENAME):
    return _plain(root, "data/state/" + name)


def _installation(root):
    _state_file(root, env_manifest.MANIFEST_FILENAME)
    current = env_manifest.read_manifest(root)
    _require(current.status == "ok" and type(current.data["schema_version"]) is int
             and current.data["schema_version"] == env_manifest.SCHEMA_VERSION,
             "a supported Engram environment manifest is required for registry ownership")
    return _identifier(current.data["install_id"])


def _table(doc, name):
    table = doc[name]
    _require(isinstance(table, dict), f"{name} must be an object")
    folded = {_identifier(key).casefold() for key in table}
    _require(len(folded) == len(table), f"case-insensitive {name} collision")
    return table


def _validate(root, doc):
    _shape(doc, _FIELDS)
    _require(doc["schema_version"] == "1.0", "unsupported Python registry schema")
    _require(type(doc["revision"]) is int and doc["revision"] >= 1, "invalid registry revision")
    _require(doc["installation_id"] == _installation(root), "foreign installation identity")
    _require(doc["default_binding"] == DEFAULT, "legacy default is protected")
    for field in ("external_refs", "vendor_exceptions", "rollback_refs"):
        _require(doc[field] == [], f"unsupported nonempty {field}")
    series = _table(doc, "series")
    builds = _table(doc, "builds")
    envs = _table(doc, "environments")
    bindings = _table(doc, "bindings")
    legacy_exe = provisioner.venv_python_exe(root).relative_to(root).as_posix()
    _require(bindings.get(DEFAULT) == {"kind": "legacy", "executable_rel": legacy_exe},
             "missing or changed legacy binding")
    _plain(root, legacy_exe)

    for key, build in builds.items():
        _shape(build, _BUILD)
        minor = build["series"]
        _require(isinstance(minor, str) and _SERIES.fullmatch(minor) and minor in series,
                 "build has no compatible series")
        _require(isinstance(build["version"], str) and
                 re.fullmatch(re.escape(minor) + r"\.(?:0|[1-9][0-9]*)", build["version"]),
                 "build needs an exact stable patch")
        _require((build["implementation"], build["abi"], build["arch"], build["flavor"], build["owner"])
                 == ("cpython", "cp" + minor.replace(".", ""), "win_amd64", "full", "engram"),
                 "unsupported CPython build identity")
        _require(isinstance(build["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", build["sha256"]),
                 "invalid artifact SHA-256")
        _identifier(build["provider"])
        _identifier(build["artifact_ref"])
        _require(build["state"] in ("ACTIVE", "RETAINED"), "unsupported build state")
        expected = f"env/python-versions/{minor}/{key}/python.exe"
        _require(build["executable_rel"] == expected, "invalid build executable path")
        _plain(root, expected)
    for minor, row in series.items():
        _shape(row, "channel active_build policy")
        active = builds.get(_identifier(row["active_build"]), {})
        _require(row["channel"] == "stable" and row["policy"] == "compatible_patch"
                 and active.get("series") == minor and active.get("state") == "ACTIVE",
                 "invalid series selection")
    for key, build in builds.items():
        _require((series[build["series"]]["active_build"] == key) == (build["state"] == "ACTIVE"),
                 "inconsistent active build")
    for key, env in envs.items():
        _shape(env, "build_id root_rel lock_ref owner generation")
        _require(_identifier(env["build_id"]) in builds, "unknown environment build")
        owner = _identifier(env["owner"])
        _identifier(env["lock_ref"])
        _require(type(env["generation"]) is int and env["generation"] > 0, "invalid generation")
        _require(env["root_rel"] in (f"env/python-envs/{owner}/{key}", f"AI/apps/{owner}/envs/{key}"),
                 "invalid managed environment path")
        if env["root_rel"].startswith("AI/"):
            _require(all(p.name == "AI" for p in root.iterdir() if p.name.casefold() == "ai"),
                     "legacy AI directory collision")
        _plain(root, env["root_rel"])
    for key, binding in bindings.items():
        if key == DEFAULT:
            continue
        _shape(binding, "kind build_id env_id constraint_ref")
        env = envs.get(_identifier(binding["env_id"]))
        _require(binding["kind"] in ("app", "project") and env is not None
                 and binding["build_id"] == env["build_id"] and env["owner"] == key,
                 "unresolved consumer binding")
        _identifier(binding["constraint_ref"])


def _unique(pairs):
    result = dict(pairs)
    _require(len(result) == len(pairs), "duplicate registry JSON key")
    return result


def _decode(root, raw):
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        doc = json.loads(text, object_pairs_hook=_unique)
    except RegistryError:
        raise
    except (ValueError, RecursionError) as exc:
        raise RegistryError("unreadable Python registry JSON") from exc
    _validate(root, doc)
    return doc


def _read(root):
    try:
        with _state_file(root).open("rb") as stream:
            data = stream.read(_MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    _require(len(data) <= _MAX_BYTES, "Python registry exceeds size limit")
    return data


def registry_path(root: Path) -> Path:
    return _state_file(root)


def inventory(root: Path) -> dict:
    """Observe physical paths without starting Python, fetching data or adopting an install."""
    base = provisioner.portable_python_exe(root).relative_to(root).as_posix()
    exe = provisioner.venv_python_exe(root).relative_to(root).as_posix()
    present = sum(_plain(root, rel).is_file() for rel in (base, exe))
    raw = _read(root)
    doc = _decode(root, raw) if raw is not None else None
    return {"revision": doc["revision"] if doc else 0, "registry": doc,
            "legacy": {"status": ("ABSENT", "PARTIAL", "PRESENT")[present],
                       "base_rel": base, "executable_rel": exe}}


def new_document(root):
    """Start an empty registry for a provisioned Engram installation."""
    legacy = provisioner.venv_python_exe(root).relative_to(root).as_posix()
    return {"schema_version": "1.0", "revision": 0, "installation_id": _installation(root),
            "default_binding": DEFAULT, "series": {}, "builds": {},
            "bindings": {DEFAULT: {"kind": "legacy", "executable_rel": legacy}},
            "environments": {}, "external_refs": [], "vendor_exceptions": [], "rollback_refs": []}


def _transition(old, new):
    previous = old["revision"] if old else 0
    _require(new["revision"] == previous + 1, "registry revision must advance by one")
    if old is None:
        return
    for key, build in old["builds"].items():
        successor = new["builds"].get(key, {})
        _require(all(successor.get(k) == v for k, v in build.items() if k != "state"),
                 "immutable build changed or disappeared")
    for key, env in old["environments"].items():
        _require(new["environments"].get(key) == env, "immutable environment changed or disappeared")


def _reconcile(ctx, *, undo=False):
    before, after = ctx.data["before"], ctx.data["after"]
    current = _read(ctx.sys_dir)
    old = before.encode("utf-8") if before is not None else None
    new = after.encode("utf-8")
    target = old if undo else new
    if current == target:
        return
    # Only the recorded images and a torn prefix of this write belong to the transaction.
    torn_write = current is not None and new.startswith(current)
    torn_undo = undo and old is not None and current is not None and old.startswith(current)
    _require(current in (old, new) or torn_write or torn_undo,
             "registry diverged from journal images")
    path = _state_file(ctx.sys_dir)
    if target is None:
        path.unlink()
    else:
        env_manifest._atomic_write_text(path, target.decode("utf-8"))


def _step():
    return env_ops.Step(STEP, _reconcile, undo=lambda ctx: _reconcile(ctx, undo=True))


def recovery_steps(root, active, mode):
    """Reconstruct the fixed operation under the lifecycle lock before replay."""
    try:
        data = active["data"]
        _require(active["kind"] == KIND, "unexpected recovery operation")
        if not data and not active["steps"] and active["phase"] == "PLANNED":
            if mode == "rollback":
                return []
            raise RegistryError("publication intent was interrupted before effects; run repair --rollback")
        _require(isinstance(data.get("after"), str)
                 and "before" in data and (data["before"] is None or isinstance(data["before"], str)),
                 "invalid registry journal images")
        before = _decode(root, data["before"]) if data["before"] is not None else None
        after = _decode(root, data["after"])
        _transition(before, after)
        if mode == "resume" and active["steps"].get(STEP) == "done" and active["phase"] == "STEPS_RUNNING":
            _require(_read(root) == data["after"].encode("utf-8"), "acknowledged registry diverged")
    except (OSError, RegistryError) as exc:
        raise env_ops.JournalError(str(exc)) from exc
    return [_step()]


# WIRING-EXEMPT: EXPORTED_API reason="WP1 transaction interface for explicit provider apply planners; discovery and doctor are read-only."
def publish(root: Path, expected_revision: int, document: dict) -> dict:
    """Publish already verified build metadata, called only by an explicit apply planner."""
    _require(type(expected_revision) is int and expected_revision >= 0, "invalid expected revision")
    _validate(root, document)
    proposed = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    _require(len(proposed.encode("utf-8")) <= _MAX_BYTES, "Python registry exceeds size limit")
    for name in (FILENAME, env_lock.LOCK_FILENAME, env_ops.JOURNAL_FILENAME):
        _state_file(root, name)

    def prepare():
        raw = _read(root)
        current = _decode(root, raw) if raw is not None else None
        _require(expected_revision == (current["revision"] if current else 0), "stale registry revision")
        _transition(current, _decode(root, proposed))
        return {"before": raw.decode("utf-8") if raw is not None else None, "after": proposed}

    return env_ops.execute(root, KIND, [_step()], prepare=prepare)
