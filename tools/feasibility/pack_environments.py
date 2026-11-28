"""Probe the current CPython base in fresh package-specific venvs. No pip or external artifacts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import venv

from pack_catalog import load_fixtures

_INSPECT = """
import importlib, importlib.util, json, pathlib, sqlite3, sys, sysconfig
packages = json.loads(sys.argv[1])
visible = []
for package in packages:
    module = 'fixture_' + package.replace('-', '_')
    if importlib.util.find_spec(module) is not None:
        visible.append(importlib.import_module(module).OWNER)
print(json.dumps(dict(visible=visible, environment=str(pathlib.Path(sys.prefix).resolve()),
                      base_prefix=str(pathlib.Path(sys.base_prefix).resolve()),
                      purelib=sysconfig.get_path('purelib'), version=sys.version.split()[0],
                      sqlite=sqlite3.sqlite_version)))
"""


def inspect(executable, packages, cwd):
    process = subprocess.run([str(executable), "-IB", "-c", _INSPECT, json.dumps(packages)],
                             cwd=cwd, capture_output=True, text=True, check=True, timeout=30)
    return json.loads(process.stdout)


def probe(root, catalog):
    packages = [entry.package_id for entry in catalog]
    executables, state_paths = {}, {}
    expected_base = str(Path(sys.base_prefix).resolve())
    for entry in catalog:
        owner = entry.package_id
        env = root / "env/python-envs" / ("pack-" + owner + "-main") / "probe-1"
        builder = venv.EnvBuilder(with_pip=False)
        context = builder.ensure_directories(env)
        builder.create(env)
        executable = Path(context.env_exe)
        row = inspect(executable, packages, root)
        purelib = Path(row["purelib"]).resolve()
        if (row["visible"] or row["environment"] != str(env.resolve())
                or row["base_prefix"] != expected_base or not purelib.is_relative_to(env.resolve())):
            raise ValueError("fixture runtime isolation failed")
        module = "fixture_" + owner.replace("-", "_") + ".py"
        (purelib / module).write_text(f"OWNER = {owner!r}\n", encoding="utf-8")
        state = root / entry.slot_rel / "workspaces" / "fixture.bin"
        state.parent.mkdir(parents=True)
        state.write_bytes(owner.encode("ascii"))
        executables[owner], state_paths[owner] = executable, state

    result = {}
    for owner, executable in executables.items():
        row = inspect(executable, packages, root)
        if row["visible"] != [owner] or state_paths[owner].read_bytes() != owner.encode("ascii"):
            raise ValueError("package fixture isolation failed")
        result[owner] = row | {"fixture_data_unchanged": True}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptors", type=Path, nargs="+")
    args = parser.parse_args()
    catalog = load_fixtures(args.descriptors)
    with TemporaryDirectory(prefix="engram pack probe ") as tmp:
        result = probe(Path(tmp), catalog)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
