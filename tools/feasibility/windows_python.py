"""Offline WP0 probe for ONE pinned Windows x64 interpreter and native wheel."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

LOCK = Path(__file__).with_name("windows-python.lock.json")
REQUIRED = {"python/python.exe", "python/python314.dll", "python/DLLs/_ssl.pyd",
            "python/DLLs/_sqlite3.pyd", "python/DLLs/_ctypes.pyd", "python/LICENSE.txt",
            "python/Lib/venv/__init__.py", "python/Lib/ensurepip/_bundled/pip-26.3-py3-none-any.whl"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stage(source, pin, root):
    dest = root / pin["filename"]
    require(source.stat().st_size == pin["size"], "artifact size mismatch")
    shutil.copyfile(source, dest)
    with dest.open("rb") as f:
        require(hashlib.file_digest(f, "sha256").hexdigest() == pin["sha256"], "artifact digest mismatch")
    return dest


def inspect_archive(archive):
    members = archive.getmembers()
    names = {m.name for m in members}
    require(all(m.isfile() for m in members) and REQUIRED <= names, "unexpected archive layout")
    require(len(names) == len(members), "duplicate member")
    with archive.extractfile("python/python.exe") as exe:
        require(exe.read(2) == b"MZ", "missing DOS header")
        exe.seek(60)
        exe.seek(struct.unpack("<I", exe.read(4))[0])
        require(exe.read(6) == b"PE\0\0\x64\x86", "not AMD64 PE")
    return {"regular_files": len(members), "uncompressed_bytes": sum(m.size for m in members),
            "python_pe_machine": "AMD64"}


def footprint():
    # Compare digests privately; registry contents never appear in receipts.
    system = Path(os.environ["SystemRoot"]) / "System32"
    commands = [[system / "reg.exe", "query", key, "/s"] for key in
                (r"HKCU\Software\Python", r"HKLM\Software\Python", r"HKCU\Environment",
                 r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment")]
    commands.append([system / "subst.exe"])
    result = []
    for command in commands:
        proc = subprocess.run(command, capture_output=True, timeout=30)
        result.append((proc.returncode, hashlib.sha256(proc.stdout + proc.stderr).hexdigest()))
    return result


CANARY = """
import ctypes, json, os, sqlite3, ssl, sys, sysconfig
from pathlib import Path
from markupsafe import _speedups
base, env = map(Path, sys.argv[1:])
def check(condition, name):
    if not condition:
        raise RuntimeError('runtime mismatch: ' + name)
check(Path(sys.executable).samefile(env / 'Scripts' / 'python.exe'), 'executable')
check(Path(sys.prefix).samefile(env) and Path(sys.base_prefix).samefile(base), 'prefixes')
check(sys.version_info[:3] == (3, 14, 10) and sysconfig.get_platform() == 'win-amd64', 'version or platform')
check(Path(_speedups.__file__).resolve().is_relative_to(env.resolve()), 'wheel location')
with sqlite3.connect(':memory:') as db:
    check(db.execute('SELECT 17').fetchone() == (17,), 'SQLite query')
check(bool(ssl.OPENSSL_VERSION) and ctypes.sizeof(ctypes.c_void_p) == 8, 'OpenSSL or pointer size')
print(json.dumps({'python': sys.version.split()[0], 'abi': sys.implementation.cache_tag,
                  'sqlite': sqlite3.sqlite_version, 'ssl': ssl.OPENSSL_VERSION, 'wheel': 'MarkupSafe 3.0.3'}))
"""


def native(root, archive_path, wheel):
    work = root / "fixture one"
    work.mkdir()
    # All bytes come from the verified private stage; no network or updater.
    before = footprint()
    with tarfile.open(archive_path) as archive:
        archive.extractall(work, filter="data")
    child_env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC") if k in os.environ}
    child_env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
                     TMP=str(root), TEMP=str(root), PIP_CONFIG_FILE=os.devnull)

    def run(exe, *args):
        result = subprocess.run([exe, "-I", "-B", *args], cwd=work, env=child_env,
                                capture_output=True, timeout=120, text=True, errors="replace")
        if result.returncode:
            raise RuntimeError(f"offline child exited {result.returncode}: {result.stderr[-1500:]}")
        return result.stdout

    receipts = []
    for i in range(2):
        base = work / "python"
        env = work / f"venv-{i}"
        run(base / "python.exe", "-m", "venv", "--copies", str(env))
        exe = env / "Scripts" / "python.exe"
        pip = ("-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir")
        run(exe, *pip, "install", "--no-index", "--no-deps", "--no-compile", str(wheel))
        run(exe, *pip, "check")
        receipts.append(json.loads(run(exe, "-c", CANARY, str(base), str(env))))
        if i == 0:
            relocated = root / "moved 한글"
            work.rename(relocated)
            work = relocated
    require(footprint() == before, "observed registry or drive mapping changed")
    return {"native": "PASS", "effective_admin": bool(ctypes.windll.shell32.IsUserAnAdmin()),
            "fresh_and_rebuilt": receipts, "sampled_host_footprint_equal": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--inventory-only", action="store_true", help="Verify archive without native execution")
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="engram-wp0-") as temp:
        root = Path(temp)
        archive_path = stage(args.archive, lock["archive"], root)
        wheel = stage(args.wheel, lock["wheel"], root)
        with tarfile.open(archive_path) as archive:
            receipt = inspect_archive(archive)
        receipt.update(artifact_bytes="PASS", native="NOT_RUN")
        if not args.inventory_only:
            if sys.platform != "win32":
                receipt.update(native="BLOCKED", reason="Windows execution required")
            else:
                receipt.update(native(root, archive_path, wheel))
        print(json.dumps(receipt, sort_keys=True))
        return 2 if receipt["native"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
