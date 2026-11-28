"""Restore an entirely missing, registered extra build from its exact archive."""
import json
from pathlib import Path
import re
import shutil
import tempfile

from core import env_manifest, env_ops, provisioner, python_install, python_provider, python_registry
from core.python_artifact import Artifact, ProviderError

_CACHE = "data/setup-files/python-archives"
_MARKER = ".engram-restored-build.json"


def _target(root, build):
    return python_registry._plain(root, build["executable_rel"]).parent


def archive_identity(root, build):
    reference = re.fullmatch(r"pbs-([0-9]{8})-([1-9][0-9]*)", build["artifact_ref"])
    if build["provider"] != "python-build-standalone" or reference is None:
        raise ProviderError("This build has no supported offline archive identity.")
    tag, ident = reference.groups()
    artifact = Artifact(tag, build["version"], int(ident), build["sha256"], 1)
    name = python_provider.asset_name(artifact)
    if any(build[key] != value for key, value in artifact.identity().items()):
        raise ProviderError("Offline archive identity conflicts with the registered build.")
    return python_registry._plain(root, f"{_CACHE}/{name}"), artifact


def _source(root, build):
    path, identity = archive_identity(root, build)
    if not path.is_file():
        raise ProviderError(f"Missing offline archive: {path.name}")
    return path, Artifact(identity.tag, identity.version, identity.asset_id, identity.sha256, path.stat().st_size)


def plan(root):
    registry = python_registry.inventory(root)["registry"]
    if registry is None:
        return []
    specs = []
    for key, build in registry["builds"].items():
        destination = _target(root, build)
        if (destination / "python.exe").is_file():
            continue
        if destination.exists():
            raise ProviderError(f"Incomplete build directory: {key}. Preserve it before restoring from cache.")
        path, artifact = _source(root, build)
        if provisioner._hash_file(path, "sha256") != artifact.sha256:
            raise ProviderError(f"Offline archive digest mismatch: {path.name}")
        specs.append({"kind": "python-versions", "name": "restore-build-" + key, "group": "A",
                      "params": {"build_id": key, "revision": registry["revision"],
                                 "installation_id": registry["installation_id"]}})
    return specs


def step(root, *, build_id, revision, installation_id):
    def current():
        registry = python_registry.inventory(root)["registry"]
        if (registry is None or registry["revision"] != revision
                or registry["installation_id"] != installation_id or build_id not in registry["builds"]):
            raise ProviderError("The restore plan no longer matches the Python registry.")
        return registry["builds"][build_id]

    def stamp(ctx, build):
        return json.dumps({"op_id": ctx.op_id, "sha256": build["sha256"], "build_id": build_id}, sort_keys=True)

    def done(ctx):
        build = current()
        destination = _target(root, build)
        marker = python_registry._plain(root, (destination / _MARKER).relative_to(root).as_posix())
        if not marker.is_file() or not (destination / "python.exe").is_file():
            return False
        with marker.open("rb") as stream:
            return stream.read(4096) == stamp(ctx, build).encode("utf-8")

    def restore(ctx):
        build = current()
        destination = _target(root, build)
        if destination.exists():
            raise ProviderError(f"Restore destination already exists: {build_id}")
        source, artifact = _source(root, build)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=destination.parent) as temporary:
            scratch = Path(temporary)
            python_install.extract_verified(source, artifact, scratch)
            payload = scratch / "python"
            python_install._probe(payload, scratch, artifact)
            env_manifest._atomic_write_text(payload / _MARKER, stamp(ctx, build))
            payload.rename(destination)

    def undo(ctx):
        if done(ctx):
            shutil.rmtree(_target(root, current()))

    return env_ops.Step("restore-build-" + build_id, do=restore, undo=undo, done=done)
