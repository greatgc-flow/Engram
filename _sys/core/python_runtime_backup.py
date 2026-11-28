"""Portable backup of one installation's Python registry and dependency locks."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from core import env_lock, env_manifest, env_ops, python_env_restore, python_registry

KIND = "python-runtime-metadata"
STEP = "restore-python-runtime-metadata"
_PREFIX = "python-runtime-v1/"
REGISTRY = _PREFIX + "registry.json"
_DIGEST = _PREFIX + "registry.sha256"
_MAX_FILES = 128
_MAX_BYTES = 4 * 1024 * 1024


def _inputs(root, raw):
    if len(raw) > python_registry._MAX_BYTES:
        raise ValueError("Python registry exceeds size limit.")
    registry = python_registry._decode(root, raw)
    paths = {}
    for env in registry["environments"].values():
        ref = env["lock_ref"]
        path = python_env_restore._lock_path(root, ref)
        identities = paths.setdefault(ref, (path, []))[1]
        build = registry["builds"][env["build_id"]]
        if build not in identities:
            identities.append(build)
    if len(paths) + 2 > _MAX_FILES:
        raise ValueError("Too many Python metadata entries for this archive version.")
    return registry, paths


def _validate(root, raw, locks):
    registry, paths = _inputs(root, raw)
    if set(locks) != paths.keys():
        raise ValueError("Backup lock entries do not match the Python registry.")
    if len(raw) + sum(map(len, locks.values())) > _MAX_BYTES - 64:
        raise ValueError("Python runtime backup exceeds size limit.")
    for ref, (_, builds) in paths.items():
        locks[ref].decode("utf-8")
        for build in builds:
            python_env_restore._decode_lock(locks[ref], ref, build)
    return registry, paths


def _read(path, limit=python_registry._MAX_BYTES):
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f"Python backup entry must be a regular file: {path.name}")
        with path.open("rb") as source:
            raw = source.read(limit + 1)
    except FileNotFoundError:
        return None
    if len(raw) > limit:
        raise ValueError(f"Python backup entry exceeds size limit: {path.name}")
    return raw


def _journal_clear(root):
    for name in (env_lock.LOCK_FILENAME, env_ops.JOURNAL_FILENAME):
        python_registry._state_file(root, name)
    if env_ops.active_journal(root) is not None:
        raise env_ops.JournalError("Run engram repair --resume or --rollback before using Python runtime backups.")


def _publish_new(source, target):
    # Windows rename fails if the target exists, including on removable FAT volumes.
    if os.name == "nt":
        os.rename(source, target)
    else:
        os.link(source, target)


def export(root, archive):
    if archive.suffix.lower() != ".zip":
        raise ValueError("Python runtime backup needs an explicit .zip output.")
    if os.path.lexists(archive):
        raise ValueError("Python runtime backup output already exists.")
    _journal_clear(root)
    raw = python_registry._read(root)
    if raw is None:
        raise ValueError("No registered Python runtime metadata.")
    _, paths = _inputs(root, raw)
    locks = {}
    remaining = _MAX_BYTES - 64 - len(raw)
    for ref, (path, _) in paths.items():
        data = _read(path, min(remaining, python_registry._MAX_BYTES))
        if data is None:
            raise ValueError(f"Missing offline lock: {path.name}")
        locks[ref] = data
        remaining -= len(data)
    registry, _ = _validate(root, raw, locks)
    with tempfile.TemporaryDirectory(prefix=".engram-runtime-", dir=archive.parent) as temporary:
        staged = Path(temporary) / "runtime.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(REGISTRY, raw)
            bundle.writestr(_DIGEST, hashlib.sha256(raw).hexdigest())
            for ref, data in locks.items():
                bundle.writestr(_PREFIX + ref + ".json", data)
        _journal_clear(root)
        if python_registry._read(root) != raw:
            raise ValueError("Python registry changed during backup. Retry the operation.")
        _publish_new(staged, archive)
    return registry["revision"]


def _read_bundle(root, source):
    if not source.is_file() or source.stat().st_size > _MAX_BYTES + 1024 * 1024:
        raise ValueError("Python runtime backup must be a ZIP within the archive size limit.")
    with zipfile.ZipFile(source) as bundle:
        entries = bundle.infolist()
        names = {entry.filename for entry in entries}
        if (len(names) != len(entries) or len(entries) > _MAX_FILES
                or sum(entry.file_size for entry in entries) > _MAX_BYTES
                or any(stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG) for entry in entries)
                or not {REGISTRY, _DIGEST} <= names):
            raise ValueError("Invalid Python runtime backup entries.")
        raw = bundle.read(REGISTRY)
        if hashlib.sha256(raw).hexdigest().encode("ascii") != bundle.read(_DIGEST):
            raise ValueError("Python runtime backup registry digest mismatch.")
        _, paths = _inputs(root, raw)
        expected = {_PREFIX + ref + ".json": ref for ref in paths}
        if names != {REGISTRY, _DIGEST, *expected}:
            raise ValueError("Unexpected or missing Python runtime backup entry.")
        locks = {ref: bundle.read(name) for name, ref in expected.items()}
    return raw, locks


def _check_destination(root, raw, locks):
    registry, paths = _validate(root, raw, locks)
    before = python_registry._read(root)
    if before not in (None, raw):
        raise ValueError("Existing Python registry differs from the backup. Preserve the live registry.")
    missing = []
    for ref, (path, _) in paths.items():
        existing = _read(path)
        if existing is None:
            missing.append(ref)
        elif existing != locks[ref]:
            raise ValueError(f"Existing Python lock differs from the backup: {path.name}")
    return registry["revision"], before, missing


def _step():
    def run(ctx):
        raw = ctx.data["after"].encode("utf-8")
        locks = {ref: data.encode("utf-8") for ref, data in ctx.data["locks"].items()}
        _, paths = _validate(ctx.sys_dir, raw, locks)
        for ref, (path, _) in paths.items():
            existing = _read(path)
            if existing is None:
                env_manifest._atomic_write_text(path, locks[ref].decode("utf-8"), replace=_publish_new)
            elif existing != locks[ref]:
                raise ValueError(f"Existing Python lock differs from the backup: {path.name}")
        python_registry._reconcile(ctx)

    def undo(ctx):
        # Content-addressed locks can safely remain available to any matching reference.
        python_registry._reconcile(ctx, undo=True)

    return env_ops.Step(STEP, run, undo=undo)


def recovery_steps(root, active, mode):
    try:
        data = active["data"]
        if not data and not active["steps"] and active["phase"] == "PLANNED":
            if mode == "rollback":
                return []
            raise ValueError("Publication intent was interrupted. Run engram repair --rollback.")
        if (active["kind"] != KIND or not isinstance(data.get("after"), str)
                or "before" not in data or data["before"] not in (None, data["after"])
                or not isinstance(data.get("locks"), dict)
                or not all(isinstance(value, str) for value in data["locks"].values())):
            raise ValueError("Invalid Python runtime metadata recovery images.")
        raw = data["after"].encode("utf-8")
        locks = {ref: value.encode("utf-8") for ref, value in data["locks"].items()}
        _validate(root, raw, locks)
        if mode == "resume" and active["steps"].get(STEP) == "done":
            _, before, missing = _check_destination(root, raw, locks)
            if before is None or missing:
                raise ValueError("Acknowledged Python metadata diverged from the backup.")
    except (OSError, ValueError) as exc:
        raise env_ops.JournalError(str(exc)) from exc
    return [_step()]


def restore(root, source, *, apply):
    _journal_clear(root)
    raw, locks = _read_bundle(root, source)
    revision, before, missing = _check_destination(root, raw, locks)
    if not apply:
        return f"Python runtime metadata preview. Revision {revision}, {len(missing)} locks to restore."
    if before is not None and not missing:
        return f"Python runtime metadata already matches revision {revision}."

    def prepare():
        _, current, _ = _check_destination(root, raw, locks)
        return {"before": current.decode("utf-8") if current is not None else None,
                "after": raw.decode("utf-8"),
                "locks": {ref: data.decode("utf-8") for ref, data in locks.items()}}

    result = env_ops.execute(root, KIND, [_step()], prepare=prepare)
    if result["phase"] != "COMMITTED":
        raise ValueError(result.get("detail") or "Python metadata restore did not commit.")
    return f"Restored Python runtime metadata revision {revision}."
