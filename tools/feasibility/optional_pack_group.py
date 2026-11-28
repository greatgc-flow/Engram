"""Exercise Engram's lifecycle journal with two synthetic package activation pointers."""
from hashlib import sha256
from io import BytesIO
import json
import re
from zipfile import BadZipFile, ZipFile

from core import env_lock, env_manifest, env_ops
from core.python_registry import _plain

_KIND = "fixture-pack-group"
_ID = re.compile(r"[a-z][a-z0-9-]{0,47}")
_LIMIT = 4096
_MARKER = "fixture-root.txt"
_MARKER_BYTES = b"ENGRAM_GROUP_TEST_ONLY_V1\n"


def initialize_fixture(root):
    if not root.is_dir() or root.is_symlink() or list(root.iterdir()):
        raise ValueError("expected an empty fixture directory")
    with (root / _MARKER).open("xb") as stream:
        stream.write(_MARKER_BYTES)


def _fixture_root(root):
    try:
        with _plain(root, _MARKER).open("rb") as stream:
            if stream.read(len(_MARKER_BYTES) + 1) != _MARKER_BYTES:
                raise ValueError("unrecognized fixture root")
    except FileNotFoundError as exc:
        raise ValueError("unrecognized fixture root") from exc
    for path in (env_lock.lock_path(root), env_ops.journal_path(root)):
        _plain(root, path.relative_to(root).as_posix())


def _payload(archive, digest):
    if len(archive) > 16384 or sha256(archive).hexdigest() != digest:
        raise ValueError("fixture archive digest or length mismatch")
    try:
        with ZipFile(BytesIO(archive)) as zipped:
            members = zipped.infolist()
            if (len(members) != 1 or members[0].filename != "app.txt"
                    or members[0].file_size > _LIMIT):
                raise ValueError("fixture archive must contain exactly one bounded app.txt")
            with zipped.open(members[0]) as stream:
                raw = stream.read(_LIMIT + 1)
            if len(raw) != members[0].file_size:
                raise ValueError("fixture member length mismatch")
            return raw
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("invalid fixture archive") from exc


def _check_journal(root):
    journal = env_ops.journal_path(root)
    if journal.exists() and not env_ops.read_journal(root):
        raise ValueError("fixture journal is unreadable")


def _path(root, package, leaf):
    if not _ID.fullmatch(package):
        raise ValueError("invalid fixture package identity")
    return _plain(root, f"data/state/fixture-packs/{package}/{leaf}")


def _read(path):
    try:
        with path.open("r", encoding="ascii", newline="") as stream:
            data = stream.read(16385)
    except FileNotFoundError:
        return None
    if len(data) > 16384:
        raise ValueError("oversized fixture state")
    return data


def _wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _paths(root, package):
    return [_path(root, package, leaf) for leaf in ("runtime.json", "package.json")]


def _current(root, package):
    runtime, app = map(_read, _paths(root, package))
    if runtime is None and app is None:
        return None, None
    if runtime is None or app is None:
        raise ValueError("incomplete fixture pointers")
    binding, pointer = json.loads(runtime), json.loads(app)
    if type(binding) is not dict or type(pointer) is not dict:
        raise ValueError("invalid fixture pointers")
    generation = binding.get("revision")
    runtime_id = binding.get("runtime")
    sha = pointer.get("sha256")
    if (type(generation) is not int or not 1 <= generation <= 2**53 - 1
            or type(runtime_id) is not str or not _ID.fullmatch(runtime_id)
            or type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha)
            or binding != {"revision": generation, "runtime": runtime_id}
            or pointer != {"revision": generation, "runtime": runtime_id, "sha256": sha}):
        raise ValueError("incoherent fixture pointers")
    stored = _read(_path(root, package, sha + ".hex"))
    if stored is None:
        raise ValueError("fixture artifact is missing")
    raw = bytes.fromhex(stored)
    if len(raw) > _LIMIT or sha256(raw).hexdigest() != sha:
        raise ValueError("fixture artifact digest mismatch")
    return (generation, runtime_id, raw), [runtime, app]


def _reconcile(path, before, after, undo=False):
    current = _read(path)
    if current not in (before, after):
        raise ValueError("fixture pointer diverged")
    target = before if undo else after
    if target != current:
        if target is None:
            path.unlink()
        else:
            env_manifest._atomic_write_text(path, target)


def _steps(package):
    def stage(ctx):
        raw = ctx.data["payload"]
        path = _path(ctx.sys_dir, package, ctx.data["sha256"] + ".hex")
        found = _read(path)
        if found is None:
            env_manifest._atomic_write_text(path, raw)
        elif found != raw:
            raise ValueError("fixture stage diverged")

    def pointer(index, undo=False):
        def act(ctx):
            data = ctx.data
            path = _paths(ctx.sys_dir, package)[index]
            _reconcile(path, data["before"][index], data["after"][index], undo)
        return act

    def verify(ctx):
        observed, _ = _current(ctx.sys_dir, package)
        if observed is None or observed[2].hex() != ctx.data["payload"]:
            raise ValueError("fixture activation failed validation")

    return [env_ops.Step("fixture-stage", stage),
            env_ops.Step("fixture-runtime", pointer(0), undo=pointer(0, True)),
            env_ops.Step("fixture-package", pointer(1), undo=pointer(1, True)),
            env_ops.Step("fixture-verify", verify)]


def publish(root, descriptor, expected_revision, runtime_id, archive, digest, *, crash_after=None):
    package = descriptor.package_id
    if (type(expected_revision) is not int or not 0 <= expected_revision < 2**53 - 1
            or not isinstance(runtime_id, str) or not _ID.fullmatch(runtime_id)):
        raise ValueError("invalid fixture generation or runtime")
    _fixture_root(root)
    raw = _payload(archive, digest)
    sha = sha256(raw).hexdigest()
    next_binding = {"revision": expected_revision + 1, "runtime": runtime_id}

    def prepare():
        _check_journal(root)
        observed, before = _current(root, package)
        if (observed[0] if observed else 0) != expected_revision:
            raise ValueError("fixture generation conflict")
        return {"package": package, "before": before or [None, None],
                "after": [_wire(next_binding), _wire(next_binding | {"sha256": sha})],
                "payload": raw.hex(), "sha256": sha}

    return env_ops.execute(root, _KIND, _steps(package), prepare=prepare, crash_after=crash_after)


def recover(root, descriptor, mode):
    _fixture_root(root)
    package = descriptor.package_id

    def factory(active):
        data = active["data"]
        if active["kind"] != _KIND or data.get("package") != package:
            raise ValueError("fixture recovery scope mismatch")
        sha = data["sha256"]
        if (not re.fullmatch(r"[0-9a-f]{64}", sha)
                or sha256(bytes.fromhex(data["payload"])).hexdigest() != sha):
            raise ValueError("fixture journal payload mismatch")
        for index, path in enumerate(_paths(root, package)):
            current = _read(path)
            before, after = data["before"][index], data["after"][index]
            if current not in (before, after):
                raise ValueError("fixture pointer diverged")
            step = ("fixture-runtime", "fixture-package")[index]
            if mode == "resume" and active["steps"].get(step) == "done" and current != after:
                raise ValueError("acknowledged fixture pointer was reverted")
        if mode == "resume":
            staged = _read(_path(root, package, sha + ".hex"))
            if active["steps"].get("fixture-stage") == "done" and staged != data["payload"]:
                raise ValueError("acknowledged fixture stage diverged")
        return _steps(package)

    if mode == "resume":
        return env_ops.resume(root, factory)
    if mode == "rollback":
        return env_ops.rollback(root, factory)
    raise ValueError("unknown fixture recovery mode")


def activate(root, descriptor):
    """Return a verified fixture snapshot while holding the lifecycle lock."""
    _fixture_root(root)
    try:
        with env_lock.guard(root, "fixture-inspect"):
            _check_journal(root)
            if env_ops.journal_blocks(root):
                raise ValueError("fixture group recovery required")
            current, _ = _current(root, descriptor.package_id)
            return current
    except env_lock.EnvLockBusy as exc:
        raise ValueError("fixture lifecycle is busy") from exc
