"""Exercise Engram's lifecycle journal with two synthetic package activation pointers."""
from contextlib import ExitStack, contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
import re
import subprocess
import sys
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from core import env_lock, env_manifest, env_ops, python_registry
from core.python_registry import _plain

_KIND = "fixture-pack-group"
_REGISTRY_KEY = "python_registry"
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


def _guard_idle(root, package):
    path = _path(root, package, "execution.json")
    if _read(path) is not None:
        raise ValueError("fixture package has an outstanding execution lease")
    return path


@contextmanager
def _execution_lease(root, package, revision):
    """Record intent under the activation gate and release after the owned child exits."""
    path = _guard_idle(root, package)
    token = _wire({"revision": revision, "launcher_pid": os.getpid(), "token": uuid4().hex})
    env_manifest._atomic_write_text(path, token)
    try:
        yield
    finally:
        if _read(_path(root, package, "execution.json")) == token:
            path.unlink()


def _retained(revision, retired_digest, registered):
    marker = {"state": "DATA_RETAINED", "revision": revision, "retired_sha256": retired_digest}
    if registered:
        marker["registered"] = True
    return marker


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
    if type(generation) is not int or not 1 <= generation <= 2**53 - 1:
        raise ValueError("invalid fixture pointer revision")
    if binding.get("state") == "DATA_RETAINED":
        retired = binding.get("retired_sha256")
        retained = _retained(generation, retired, binding.get("registered") is True)
        if (type(retired) is not str or not re.fullmatch(r"[0-9a-f]{64}", retired)
                or binding != retained or pointer != retained):
            raise ValueError("incoherent fixture retention pointers")
        return None, [runtime, app]
    runtime_id = binding.get("runtime")
    sha = pointer.get("sha256")
    expected = {"revision": generation, "runtime": runtime_id}
    if binding.get("registered") is True:
        expected["registered"] = True
    if (type(runtime_id) is not str or not _ID.fullmatch(runtime_id)
            or type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha)
            or binding != expected
            or pointer != expected | {"sha256": sha}):
        raise ValueError("incoherent fixture pointers")
    if expected.get("registered"):
        registry = python_registry.inventory(root)["registry"]
        _require_binding(registry, package, runtime_id)
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


def _require_binding(registry, package, runtime_id):
    binding = registry["bindings"].get(package, {}) if registry else {}
    if binding.get("kind") != "app" or binding.get("build_id") != runtime_id:
        raise ValueError("fixture Python registry binding mismatch")


def _steps(package, registry_step=None, *, removing=False):
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
        observed, images = _current(ctx.sys_dir, package)
        if images != ctx.data["after"] or (removing and observed is not None) or (
                not removing and (observed is None or observed[2].hex() != ctx.data["payload"])):
            raise ValueError("fixture activation failed validation")

    return [*([] if removing else [env_ops.Step("fixture-stage", stage)]),
            *([registry_step] if registry_step is not None else []),
            env_ops.Step("fixture-runtime", pointer(0), undo=pointer(0, True)),
            env_ops.Step("fixture-package", pointer(1), undo=pointer(1, True)),
            env_ops.Step("fixture-verify", verify)]


def publish(root, descriptor, expected_revision, runtime_id, archive, digest, *,
            registry_proposal=None, crash_after=None, reuse_retained=False, verify_artifact=None):
    package = descriptor.package_id
    if (type(expected_revision) is not int or not 0 <= expected_revision < 2**53 - 1
            or not isinstance(runtime_id, str) or not _ID.fullmatch(runtime_id)):
        raise ValueError("invalid fixture generation or runtime")
    _fixture_root(root)
    raw = _payload(archive, digest)
    sha = sha256(raw).hexdigest()
    next_binding = {"revision": expected_revision + 1, "runtime": runtime_id}

    registry_step = None
    if registry_proposal is not None:
        next_binding["registered"] = True
        registry_step = python_registry.publication_step(journal_key=_REGISTRY_KEY)

    def prepare():
        _check_journal(root)
        _guard_idle(root, package)
        observed, before = _current(root, package)
        previous = json.loads(before[0]) if before is not None else {}
        retained = before is not None and observed is None
        if previous.get("revision", 0) != expected_revision:
            raise ValueError("fixture generation conflict")
        if retained and (reuse_retained is not True or previous["retired_sha256"] != sha):
            raise ValueError("fixture reinstall requires explicit reuse with the exact retained program")
        if previous.get("registered") and registry_proposal is None:
            raise ValueError("registered package publication requires an exact registry proposal")
        data = {"package": package, "before": before or [None, None],
                "after": [_wire(next_binding), _wire(next_binding | {"sha256": sha})],
                "payload": raw.hex(), "sha256": sha}
        if registry_proposal is not None:
            revision, document = registry_proposal
            images = python_registry.prepare_publication(root, revision, document)
            _require_binding(json.loads(images["after"]), package, runtime_id)
            data[_REGISTRY_KEY] = images
        if verify_artifact is not None:
            verify_artifact()
        return data

    return env_ops.execute(root, _KIND, _steps(package, registry_step), prepare=prepare, crash_after=crash_after)


def retire(root, descriptor, expected_revision, expected_payload, *, verify_artifact=None, crash_after=None):
    """Retire exactly the selected program and unbind its runtime without deleting data."""
    _fixture_root(root)
    package = descriptor.package_id
    if (type(expected_revision) is not int or not 1 <= expected_revision < 2**53 - 1
            or type(expected_payload) is not bytes or len(expected_payload) > _LIMIT):
        raise ValueError("invalid fixture retirement precondition")

    def prepare():
        _check_journal(root)
        _guard_idle(root, package)
        observed, before = _current(root, package)
        if observed is None or observed[0] != expected_revision or observed[2] != expected_payload:
            raise ValueError("fixture retirement generation conflict")
        registered = json.loads(before[0]).get("registered") is True
        marker = _wire(_retained(expected_revision + 1, sha256(expected_payload).hexdigest(), registered))
        data = {"package": package, "before": before, "after": [marker, marker], "remove": True}
        if registered:
            registry = python_registry.inventory(root)["registry"]
            _require_binding(registry, package, observed[1])
            revision = registry["revision"]
            del registry["bindings"][package]
            registry["revision"] += 1
            data[_REGISTRY_KEY] = python_registry.prepare_publication(root, revision, registry)
        if verify_artifact is not None:
            verify_artifact()
        return data

    # The presence of a registry image is decided by the initial prepare under the gate.
    registry_step = _optional_registry_step()
    return env_ops.execute(root, _KIND, _steps(package, registry_step, removing=True),
                           prepare=prepare, crash_after=crash_after)


def _optional_registry_step():
    step = python_registry.publication_step(journal_key=_REGISTRY_KEY)
    return env_ops.Step(step.name,
                        lambda ctx: step.do(ctx) if _REGISTRY_KEY in ctx.data else None,
                        undo=lambda ctx: step.undo(ctx) if _REGISTRY_KEY in ctx.data else None)


def recover(root, descriptor, mode):
    _fixture_root(root)
    package = descriptor.package_id

    def factory(active):
        data = active["data"]
        if active["kind"] != _KIND or data.get("package") != package:
            raise ValueError("fixture recovery scope mismatch")
        _guard_idle(root, package)
        removing = data.get("remove") is True
        if removing:
            binding, pointer = map(json.loads, data["before"])
            registered = binding.get("registered") is True
            marker = _wire(_retained(binding["revision"] + 1, pointer["sha256"], registered))
            if data["after"] != [marker, marker] or registered != (_REGISTRY_KEY in data):
                raise ValueError("fixture retirement journal images mismatch")
        else:
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
        if mode == "resume" and not removing:
            staged = _read(_path(root, package, sha + ".hex"))
            if active["steps"].get("fixture-stage") == "done" and staged != data["payload"]:
                raise ValueError("acknowledged fixture stage diverged")
        registry_step = _optional_registry_step() if removing else None
        if _REGISTRY_KEY in data:
            registry_step, = python_registry.recovery_steps(
                root, active, mode, kind=_KIND, journal_key=_REGISTRY_KEY)
        return _steps(package, registry_step, removing=removing)

    if mode == "resume":
        return env_ops.resume(root, factory)
    if mode == "rollback":
        return env_ops.rollback(root, factory)
    raise ValueError("unknown fixture recovery mode")


@contextmanager
def _activation(root, descriptor):
    _fixture_root(root)
    try:
        with env_lock.guard(root, "fixture-inspect"):
            _check_journal(root)
            if env_ops.journal_blocks(root):
                raise ValueError("fixture group recovery required")
            current, _ = _current(root, descriptor.package_id)
            yield current
    except env_lock.EnvLockBusy as exc:
        raise ValueError("fixture lifecycle is busy") from exc


def activate(root, descriptor):
    """Return a verified fixture snapshot while holding the lifecycle lock."""
    with _activation(root, descriptor) as current:
        return current


_READER = (
    "import hashlib, sys; "
    "data = sys.stdin.buffer.read(4097); "
    "assert len(data) <= 4096; "
    "sys.stdout.write(hashlib.sha256(data).hexdigest())"
)


def launch(root, descriptor):
    """Start a fixed reader and hand it the verified immutable fixture bytes."""
    with ExitStack() as process:
        with _activation(root, descriptor) as current:
            if current is None:
                raise ValueError("fixture package is not installed")
            revision, runtime, payload = current
            environment = {key: value for key, value in os.environ.items()
                           if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
            child = process.enter_context(subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", _READER], cwd=root, env=environment,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        try:
            observed, _ = child.communicate(payload, timeout=15)
        except BaseException:
            child.kill()
            child.communicate()
            raise
        expected = sha256(payload).hexdigest()
        if child.returncode != 0 or observed != expected.encode("ascii"):
            raise ValueError("fixture subprocess did not confirm admitted payload")
    return {"revision": revision, "runtime": runtime, "sha256": expected}
