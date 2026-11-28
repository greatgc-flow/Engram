"""Rebuild missing registered Python environments from exact local wheel locks."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from core import env_manifest, env_ops, provisioner, python_registry

_LOCKS = "data/setup-files/python-locks"
_WHEELS = "data/setup-files/python-wheels"
_MARKER = ".engram-env-recovery.json"
_HASH = r"[a-f0-9]{64}"
_WHEEL = r"[A-Za-z0-9][A-Za-z0-9_.+!-]{0,175}\.whl"
_PROBE = """
import ctypes, sqlite3, ssl, sys, sysconfig
from pathlib import Path
import pip
exe, base, prefix, expected = sys.argv[1:]
assert Path(sys.executable).samefile(exe)
assert Path(sys.base_prefix).samefile(base)
assert Path(sys.prefix).samefile(prefix)
assert sys.version.split()[0] == expected
assert sysconfig.get_platform() == "win-amd64" and ctypes.sizeof(ctypes.c_void_p) == 8
assert Path(pip.__file__).resolve().is_relative_to(Path(prefix).resolve())
assert ssl.OPENSSL_VERSION
with sqlite3.connect(":memory:") as db:
    assert db.execute("SELECT 1").fetchone() == (1,)
"""


def _paths(root, registry, environment):
    build = registry["builds"][environment["build_id"]]
    base = python_registry._plain(root, build["executable_rel"])
    if not base.is_file():
        raise ValueError(f"Missing registered base: {environment['build_id']}. Repair python-versions first.")
    return base, python_registry._plain(root, environment["root_rel"]), build


def _lock_path(root, ref):
    if not re.fullmatch("sha256-" + _HASH, ref):
        raise ValueError(f"Unsupported managed environment lock reference: {ref}")
    return python_registry._plain(root, f"{_LOCKS}/{ref}.json")


def _decode_lock(raw, ref, build):
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != ref[7:]:
        raise ValueError(f"Lock digest mismatch: {ref}.json")
    locked = json.loads(raw, object_pairs_hook=python_registry._unique)
    if (not isinstance(locked, dict) or locked.keys() != {"schema", "build_sha256", "wheels"}
            or type(locked["schema"]) is not int or locked["schema"] != 1
            or locked["build_sha256"] != build["sha256"] or not isinstance(locked["wheels"], list)):
        raise ValueError("Invalid lock schema or registered base digest.")
    wheels = {}
    for wheel in locked["wheels"]:
        if (not isinstance(wheel, dict) or wheel.keys() != {"filename", "sha256"}
                or not isinstance(wheel["filename"], str) or not re.fullmatch(_WHEEL, wheel["filename"])
                or not isinstance(wheel["sha256"], str) or not re.fullmatch(_HASH, wheel["sha256"])):
            raise ValueError("Wheel locks require an exact filename and SHA-256.")
        name = wheel["filename"]
        segments = name[:-4].split("-")
        if len(segments) not in (5, 6) or not all(segments):
            raise ValueError(f"Invalid wheel filename: {name}")
        package = re.sub(r"[-_.]+", "-", segments[0]).lower()
        if package in wheels:
            raise ValueError(f"Duplicate project in wheel lock: {package}")
        wheels[package] = (name, wheel["sha256"])
    return {"version": build["version"], "wheels": tuple(wheels.values())}


def _lock(root, environment, build):
    ref = environment["lock_ref"]
    path = _lock_path(root, ref)
    if not path.is_file():
        raise ValueError(f"Missing offline lock: {path.name}")
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    return _decode_lock(raw, ref, build)


def _wheel_path(root, name):
    path = python_registry._plain(root, f"{_WHEELS}/{name}")
    if not path.is_file():
        raise ValueError(f"Missing offline wheel: {name}")
    return path


def _existing(root, destination, executable):
    relative = destination.relative_to(root).as_posix()
    config = python_registry._plain(root, relative + "/pyvenv.cfg")
    interpreter = python_registry._plain(root, relative + "/Scripts/python.exe")
    if not config.is_file() or not interpreter.is_file():
        raise ValueError(f"Incomplete managed environment: {relative}. Preserve it before rebuilding.")
    with config.open(encoding="utf-8") as stream:
        homes = [line.partition("=")[2].strip() for line in stream if line.partition("=")[0].strip() == "home"]
    return (len(homes) == 1 and Path(homes[0]).is_absolute() and Path(homes[0]).is_dir()
            and Path(homes[0]).samefile(executable.parent))


def _previous_marker(root, destination, env_id, lock_ref):
    marker = python_registry._plain(root, (destination / _MARKER).relative_to(root).as_posix())
    if not marker.is_file():
        raise ValueError(f"Stale environment has no Engram ownership marker: {env_id}.")
    with marker.open("rb") as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError(f"Invalid environment ownership marker: {env_id}.")
    value = json.loads(raw, object_pairs_hook=python_registry._unique)
    if (not isinstance(value, dict) or value.keys() != {"op_id", "env_id", "lock_ref", "state"}
            or value["env_id"] != env_id or value["lock_ref"] != lock_ref or value["state"] != "complete"):
        raise ValueError(f"Invalid environment ownership marker: {env_id}.")
    python_registry._identifier(value["op_id"])
    return hashlib.sha256(raw).hexdigest()


def plan(root, *, relocate=False):
    registry = python_registry.inventory(root)["registry"]
    if registry is None:
        return []
    specs = []
    for key, environment in registry["environments"].items():
        base, destination, build = _paths(root, registry, environment)
        previous = None
        if destination.exists():
            if _existing(root, destination, base):
                continue
            if not relocate:
                raise ValueError(f"Managed environment has a stale base path: {environment['root_rel']}. Use relocate.")
            previous = _previous_marker(root, destination, key, environment["lock_ref"])
        lock = _lock(root, environment, build)
        for name, expected in lock["wheels"]:
            if provisioner._hash_file(_wheel_path(root, name), "sha256") != expected:
                raise ValueError(f"Wheel digest mismatch: {name}")
        specs.append({"kind": "python-envs", "name": "restore-env-" + key, "group": "A",
                      "params": {"env_id": key, "revision": registry["revision"],
                                 "installation_id": registry["installation_id"],
                                 "previous": previous}})
    return specs


def _rebuild(base, target, work, lock):
    windows = Path(os.environ["SystemRoot"])
    env = {"SYSTEMROOT": str(windows), "PATH": str(windows / "System32"),
           "TEMP": str(work), "TMP": str(work), "PIP_CONFIG_FILE": os.devnull}

    def checked(label, interpreter, *args):
        result = subprocess.run([str(interpreter), "-I", "-B", *map(str, args)], cwd=work,
                                env=env, capture_output=True, timeout=180)
        if result.returncode:
            raise ValueError(f"Managed environment {label} failed with exit {result.returncode}.")

    checked("venv creation", base, "-m", "venv", "--copies", target)
    python = target / "Scripts/python.exe"
    pip = ("-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir")
    if lock["wheels"]:
        requirements = work / "requirements.txt"
        requirements.write_text("".join(f"{(work / name).as_uri()} --hash=sha256:{digest}\n"
                                        for name, digest in lock["wheels"]), encoding="ascii")
        checked("wheel installation", python, *pip, "install", "--no-index", "--no-deps",
                "--require-hashes", "--only-binary=:all:", "--no-compile", "-r", requirements)
    checked("dependency check", python, *pip, "check")
    checked("interpreter probe", python, "-c", _PROBE, python, base.parent, target, lock["version"])


def step(root, *, env_id, revision, installation_id, previous=None):
    def current():
        registry = python_registry.inventory(root)["registry"]
        if (registry is None or registry["revision"] != revision or registry["installation_id"] != installation_id
                or env_id not in registry["environments"]):
            raise ValueError("The rebuild plan no longer matches the Python registry.")
        environment = registry["environments"][env_id]
        return environment, _paths(root, registry, environment)

    def mark_data(ctx, environment, state):
        return json.dumps({"op_id": ctx.op_id, "env_id": env_id, "lock_ref": environment["lock_ref"],
                           "state": state}, sort_keys=True)

    def owner(ctx, environment, destination):
        marker = python_registry._plain(root, (destination / _MARKER).relative_to(root).as_posix())
        if not marker.is_file():
            return None
        with marker.open(encoding="utf-8") as stream:
            value = stream.read(4096)
        for state in ("creating", "complete"):
            if value == mark_data(ctx, environment, state):
                return state
        return None

    def backup_path(ctx, destination):
        op_id = python_registry._identifier(ctx.op_id)
        backup = destination.with_name(f".{destination.name}.previous-{op_id}")
        return python_registry._plain(root, backup.relative_to(root).as_posix())

    def verify_previous(path, environment):
        if _previous_marker(root, path, env_id, environment["lock_ref"]) != previous:
            raise ValueError(f"The preserved environment changed during relocation: {env_id}.")

    def done(ctx):
        environment, (_, destination, _) = current()
        if owner(ctx, environment, destination) != "complete" or not (destination / "Scripts/python.exe").is_file():
            return False
        if previous is not None:
            verify_previous(backup_path(ctx, destination), environment)
        return True

    def restore(ctx):
        environment, (base, destination, build) = current()
        owned = owner(ctx, environment, destination) == "creating"
        backup = backup_path(ctx, destination) if previous is not None else None
        if backup is not None and backup.exists():
            verify_previous(backup, environment)
        if destination.exists() and not owned and (backup is None or backup.exists()):
            raise ValueError(f"Restore destination already exists: {env_id}")
        lock = _lock(root, environment, build)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-env-", dir=destination.parent) as temporary:
            work = Path(temporary)
            for name, expected in lock["wheels"]:
                target = work / name
                shutil.copyfile(_wheel_path(root, name), target)
                if provisioner._hash_file(target, "sha256") != expected:
                    raise ValueError(f"Wheel digest mismatch: {name}")
            if backup is not None and not backup.exists():
                if _existing(root, destination, base):
                    raise ValueError(f"Environment already resolves at the new path: {env_id}.")
                verify_previous(destination, environment)
                destination.rename(backup)
            if not destination.exists():
                payload = work / "owner"
                payload.mkdir()
                env_manifest._atomic_write_text(payload / _MARKER, mark_data(ctx, environment, "creating"))
                payload.rename(destination)
            # Windows console launchers embed the destination's absolute path.
            _rebuild(base, destination, work, lock)
            env_manifest._atomic_write_text(destination / _MARKER, mark_data(ctx, environment, "complete"))

    def undo(ctx):
        environment, (_, destination, _) = current()
        backup = backup_path(ctx, destination) if previous is not None else None
        if backup is not None and backup.exists():
            verify_previous(backup, environment)
        if owner(ctx, environment, destination):
            shutil.rmtree(destination)
        if backup is not None and backup.exists():
            if destination.exists():
                raise ValueError(f"Cannot return preserved environment to occupied path: {env_id}.")
            backup.rename(destination)

    return env_ops.Step("restore-env-" + env_id, do=restore, undo=undo, done=done)
