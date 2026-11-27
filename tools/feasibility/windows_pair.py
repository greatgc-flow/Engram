"""Probe two pinned CPython minors under a limited token, offline on two physical volumes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from windows_python import LOCK, footprint, require, stage


IDENTITY = """
import ctypes, json, sqlite3, ssl, sys, sysconfig
from pathlib import Path
from markupsafe import _speedups
base, env, expected = sys.argv[1:]
assert sys.version.split()[0] == expected
assert sysconfig.get_platform() == 'win-amd64'
assert Path(sys.executable).samefile(Path(env) / 'Scripts' / 'python.exe')
assert Path(sys.base_prefix).samefile(base) and Path(sys.prefix).samefile(env)
assert Path(_speedups.__file__).resolve().is_relative_to(Path(env).resolve())
assert sqlite3.connect(':memory:').execute('SELECT 3').fetchone() == (3,)
assert ssl.OPENSSL_VERSION and ctypes.sizeof(ctypes.c_void_p) == 8
print(json.dumps({'python': expected, 'abi': sys.implementation.cache_tag}))
"""


def probe(cache, first, second):
    require(not ctypes.windll.shell32.IsUserAnAdmin(), "limited token required")
    require(first.stat().st_dev != second.stat().st_dev, "separate volumes required")
    before = footprint()
    child_env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC") if k in os.environ}
    child_env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"), TMP=str(first),
                     TEMP=str(first), PIP_CONFIG_FILE=os.devnull)

    def run(exe, *args, reject=None):
        result = subprocess.run([exe, "-I", "-B", *args], env=child_env, cwd=first,
                                timeout=120, capture_output=True, text=True, errors="replace")
        if reject:
            require(result.returncode != 0 and reject in result.stderr, "unexpected negative result")
        elif result.returncode:
            raise RuntimeError(result.stderr[-1500:])
        return result.stdout

    pins = [("3.13.18", LOCK.with_name("windows-pair.lock.json")), ("3.14.10", LOCK)]
    wheels = {}
    for version, lock_path in pins:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        archive = stage(cache / lock["archive"]["filename"], lock["archive"], first)
        wheels[version] = stage(cache / lock["wheel"]["filename"], lock["wheel"], first)
        base = first / version
        with tarfile.open(archive) as bundle:
            bundle.extractall(base, filter="data")
        # Model an offline full-tree relocation. Rebuild venvs from the pins.
        shutil.copytree(base, second / version)

    pip = ("-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir")
    versions = list(wheels)

    def canary(root, version, other):
        base = root / version / "python"
        venv = root / version / "isolated env"
        run(base / "python.exe", "-m", "venv", "--copies", str(venv))
        exe = venv / "Scripts" / "python.exe"
        install = (*pip, "install", "--no-index", "--no-deps", "--no-compile")
        run(exe, *install, "markupsafe==3.0.3", reject="No matching distribution")
        run(exe, *install, str(wheels[other]), reject="not a supported wheel")
        run(exe, *install, str(wheels[version]))
        run(exe, *pip, "check")
        return json.loads(run(exe, "-c", IDENTITY, str(base), str(venv), version))

    reports = []
    for root in (first, second):
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports.append(list(pool.map(lambda pair: canary(root, *pair), zip(versions, reversed(versions)))))
        if root == first:
            # Both original bases become inaccessible by their initial bindings.
            for version in versions:
                (first / version).rename(first / (version + "-retired"))
    require(footprint() == before, "sampled host footprint changed")
    return {"effective_admin": False, "distinct_volumes": True, "side_by_side": reports,
            "missing_wheel_rejected": True, "wrong_abi_rejected": True, "sampled_footprint_equal": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--second-temp-parent", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="engram-pair-") as first:
        with tempfile.TemporaryDirectory(prefix="moved 한글 ", dir=args.second_temp_parent) as second:
            print(json.dumps(probe(args.cache, Path(first), Path(second)), sort_keys=True))
