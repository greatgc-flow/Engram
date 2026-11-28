"""Prove locked managed environment reconstruction across two Windows volumes."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = ROOT / "_sys"
sys.path.insert(0, str(SYSTEM))
from core import env_manifest, python_cli, python_registry, repair  # noqa: E402

_FIXTURE = Path(__file__).with_name("windows-python.lock.json")
_LOCKS = "data/setup-files/python-locks"
_WHEELS = "data/setup-files/python-wheels"
_ENV = "AI/apps/demo/envs/locked-demo"
_PROBE = """
import json, ssl, sqlite3, sys
from markupsafe import _speedups
print(json.dumps({"prefix": sys.prefix, "base": sys.base_prefix, "extension": _speedups.__file__}))
"""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def volumes(stack):
    roots = [Path(tempfile.gettempdir()), ROOT, Path.home()]
    if os.environ.get("RUNNER_TEMP"):
        roots.append(Path(os.environ["RUNNER_TEMP"]))
    paths = {}
    for parent in roots:
        try:
            key = parent.stat().st_dev
            if key not in paths:
                directory = stack.enter_context(tempfile.TemporaryDirectory(prefix="engram-env-", dir=parent))
                paths[key] = Path(directory)
        except OSError:
            continue
        if len(paths) == 2:
            return tuple(paths.values())
    raise RuntimeError("BLOCKED: two writable Windows volumes are required.")


def repair_scope(root, *flags, verb="repair"):
    handler = repair.relocate_main if verb == "relocate" else repair.repair_main
    return handler({"sys_dir": root, "base_dir": root.parent, "command": verb,
                               "args": ["--only", "python-envs", "--offline", "--json", *flags]})


def probe(root, base):
    environment = root / _ENV
    exe = environment / "Scripts/python.exe"
    result = json.loads(subprocess.check_output([exe, "-I", "-B", "-c", _PROBE], timeout=30))
    assert Path(result["prefix"]).samefile(environment)
    assert Path(result["base"]).samefile(base)
    extension = Path(result["extension"]).resolve()
    assert extension.is_relative_to(environment.resolve())
    output = subprocess.check_output([environment / "Scripts/pip.exe", "--version"], timeout=30, text=True)
    assert "markupsafe" in {p.name.casefold() for p in extension.parent.parent.iterdir()}
    assert " (python 3.14)" in output
    return extension


def main(wheel):
    if sys.platform != "win32":
        raise RuntimeError("The managed environment move gate requires Windows.")
    pins = json.loads(_FIXTURE.read_bytes())
    assert wheel.name == pins["wheel"]["filename"] and digest(wheel) == pins["wheel"]["sha256"]
    actual = python_registry.inventory(SYSTEM)["registry"]
    build_id = actual["series"]["3.14"]["active_build"]
    build = actual["builds"][build_id]
    assert build["sha256"] == pins["archive"]["sha256"]
    with ExitStack() as stack:
        first, second = volumes(stack)
        source = first / "source 한글" / "_sys"
        target = second / "relocated 한글" / "_sys"
        assert first.stat().st_dev != second.stat().st_dev
        project = first / "fixture project"
        (project / ".git").mkdir(parents=True)
        os.environ["ENGRAM_CALLER_CWD"] = str(project)
        env_manifest.write_manifest(source, {"schema_version": 1, "install_id": "fixture-cross-volume",
                                             "root": {"physical": str(source.parent), "logical": str(source.parent)}})
        source_build = source / build["executable_rel"]
        shutil.copytree((SYSTEM / build["executable_rel"]).parent, source_build.parent)
        document = python_registry.new_document(source)
        document["series"]["3.14"] = actual["series"]["3.14"]
        document["builds"][build_id] = build
        lock = json.dumps({"schema": 1, "build_sha256": build["sha256"],
                           "wheels": [{"filename": wheel.name, "sha256": digest(wheel)}]},
                          sort_keys=True).encode()
        ref = "sha256-" + hashlib.sha256(lock).hexdigest()
        document["environments"]["locked-demo"] = {"build_id": build_id, "root_rel": _ENV, "lock_ref": ref,
                                                    "owner": "demo", "generation": 1}
        document["bindings"]["demo"] = {"kind": "app", "build_id": build_id, "env_id": "locked-demo",
                                         "constraint_ref": "fixture"}
        document["revision"] = 1
        assert python_registry.publish(source, 0, document)["phase"] == "COMMITTED"
        (source / _LOCKS).mkdir(parents=True)
        (source / _LOCKS / (ref + ".json")).write_bytes(lock)
        (source / _WHEELS).mkdir(parents=True)
        shutil.copyfile(wheel, source / _WHEELS / wheel.name)
        pin = python_cli.run({"sys_dir": source, "args": ["pin", "3.14", "--json"]})
        assert pin["exit_code"] == 0
        pin_path = Path(pin["pin"])
        original_pin = pin_path.read_bytes()

        assert repair_scope(source, "--apply", "--yes")["exit_code"] == 0
        source_extension = probe(source, source_build.parent)
        extension_rel = source_extension.relative_to(source.resolve())
        original_extension = digest(source_extension)
        original_registry = python_registry.registry_path(source).read_bytes()

        shutil.copytree(source, target)
        stale = repair_scope(target, "--dry-run")
        assert stale["exit_code"] == 11 and "stale base path" in stale["detail"]
        stale_before = (target / _ENV / "pyvenv.cfg").read_bytes()
        (target / _WHEELS / wheel.name).rename(second / wheel.name)
        missing = repair_scope(target, "--apply", "--yes", verb="relocate")
        assert missing["exit_code"] == 11 and wheel.name in missing["detail"]
        assert (target / _ENV / "pyvenv.cfg").read_bytes() == stale_before
        (second / wheel.name).rename(target / _WHEELS / wheel.name)
        # Make the old absolute runtime paths unavailable during the build and execution.
        held_source = first / "held-source"
        source.rename(held_source)
        assert not source.exists()
        planned = repair_scope(target, "--dry-run", verb="relocate")
        assert planned["exit_code"] == 0 and len(planned["plan"]["steps"]) == 1
        assert (target / _ENV / "pyvenv.cfg").read_bytes() == stale_before
        assert repair_scope(target, "--apply", "--yes", verb="relocate")["exit_code"] == 0
        archived, = (target / _ENV).parent.glob(".locked-demo.previous-*")
        assert (archived / "pyvenv.cfg").read_bytes() == stale_before
        active = target / build["executable_rel"]
        assert digest(probe(target, active.parent)) == original_extension
        selected = python_cli.run({"sys_dir": target, "args": ["where", "--json"]})
        assert selected["exit_code"] == 0 and Path(selected["executable"]).samefile(active)
        health = python_cli.run({"sys_dir": target, "args": ["doctor", "3.14", "--json"]})
        assert health["exit_code"] == 0
        assert set(health["builds"][0]["references"]) == {
            "ACTIVE_SERIES", "REGISTERED_ENVIRONMENT", "CONSUMER_BINDING", "PROJECT_PIN",
        }
        assert health["coverage"]["external_projects"] == "UNKNOWN"
        assert python_registry.registry_path(target).read_bytes() == original_registry
        assert digest(held_source / extension_rel) == original_extension
        assert pin_path.read_bytes() == original_pin
        print(json.dumps({"managed_env_move": "PASS", "different_volumes": True,
                          "stale_directory_preserved": True, "missing_wheel_blocked": True,
                          "offline_wheel": wheel.name, "project_pin_preserved": True,
                          "exact_build_registry_preserved": True,
                          "native_wheel_and_regenerated_pip_launcher": True}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
