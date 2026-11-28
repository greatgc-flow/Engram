"""Stream the exact interpreter and wheel cache files referenced by a recovery pack."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from core import python_env_restore, python_registry, python_restore
from core.python_artifact import BLOCK, MAX_COMPRESSED

MARKER = "python-runtime-v1/artifacts"
VERSION = b"1\n"
PREFIX = "python-runtime-v1/cache/"
MAX_BYTES = 32 * 1024**3
MAX_ENTRIES = 4096
_MAX_WHEEL = 2 * 1024**3


def entries(root, registry, locks):
    files = {}

    def add(value, category):
        path, digest, limit = value
        name = PREFIX + category + "/" + path.name
        previous = files.setdefault(name.casefold(), (name, path, digest, limit))
        if previous != (name, path, digest, limit):
            raise ValueError(f"Conflicting artifact cache identity: {path.name}")

    for build in registry["builds"].values():
        path, identity = python_restore.archive_identity(root, build)
        add((path, identity.sha256, MAX_COMPRESSED), "archives")
    for env in registry["environments"].values():
        ref = env["lock_ref"]
        build = registry["builds"][env["build_id"]]
        for name, digest in python_env_restore._decode_lock(locks[ref], ref, build)["wheels"]:
            path = python_registry._plain(root, f"{python_env_restore._WHEELS}/{name}")
            add((path, digest, _MAX_WHEEL), "wheels")
    if len(files) > MAX_ENTRIES:
        raise ValueError("Too many offline artifacts for one Python runtime pack.")
    return {name: (path, digest, limit) for name, path, digest, limit in files.values()}


def _stream(source, name, expected, limit, target=None):
    digest = hashlib.sha256()
    size = 0
    while block := source.read(BLOCK):
        size += len(block)
        if size > limit:
            raise ValueError(f"Offline artifact exceeds size limit: {name}")
        digest.update(block)
        if target is not None:
            target.write(block)
    if not size or digest.hexdigest() != expected:
        raise ValueError(f"Offline artifact digest mismatch: {name}")
    return size


def _file(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Offline artifact must be a regular file: {path.name}")
    return info


def write(bundle, files):
    bundle.writestr(MARKER, VERSION)
    remaining = MAX_BYTES
    for name, (path, digest, limit) in files.items():
        info = _file(path)
        if info is None:
            raise ValueError(f"Missing offline artifact: {path.name}")
        if not 0 < info.st_size <= min(limit, remaining):
            raise ValueError(f"Invalid offline artifact size: {path.name}")
        member = zipfile.ZipInfo(name)  # Wheels and interpreter tarballs are already compressed.
        with path.open("rb") as source, bundle.open(member, "w", force_zip64=True) as target:
            remaining -= _stream(source, path.name, digest, min(limit, remaining), target)


def check(bundle, files, *, verify_payload):
    remaining = MAX_BYTES
    missing = []
    for name, (path, digest, limit) in files.items():
        member = bundle.getinfo(name)
        if member.compress_type != zipfile.ZIP_STORED or not 0 < member.file_size <= min(limit, remaining):
            raise ValueError(f"Invalid offline artifact member: {path.name}")
        remaining -= member.file_size
        if verify_payload:
            with bundle.open(member) as source:
                _stream(source, path.name, digest, member.file_size)
        existing = _file(path)
        if existing is None:
            missing.append(name)
        elif existing.st_size != member.file_size:
            raise ValueError(f"Existing offline artifact has a conflicting size: {path.name}")
        else:
            with path.open("rb") as source:
                _stream(source, path.name, digest, member.file_size)
    return missing


def populate(bundle, files, missing, publish):
    # These are verified additive cache entries. An interrupted attempt can reuse them.
    for name in missing:
        path, digest, _ = files[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-cache-", dir=path.parent) as directory:
            staged = Path(directory) / path.name
            with bundle.open(name) as source, staged.open("xb") as target:
                _stream(source, path.name, digest, bundle.getinfo(name).file_size, target)
                target.flush()
                os.fsync(target.fileno())
            publish(staged, path)
