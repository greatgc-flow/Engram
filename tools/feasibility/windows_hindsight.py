"""Test one offline Hindsight dependency closure in a disposable Engram base and venv."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from windows_python import Artifact, LOCK, footprint, open_verified

REQUIREMENTS = Path(__file__).with_name("windows-hindsight-cp314.lock.txt")
EXPECTED_WHEELS = 186

SMOKE = r"""
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys
import sysconfig

def deny_effect(event, args):
    # platform.uname() reads the local hostname during asyncpg import.
    network_event = event.startswith("socket.") and event != "socket.gethostname"
    if network_event or event in ("subprocess.Popen", "os.system", "os.startfile"):
        raise RuntimeError("Unexpected side effect during dependency smoke: " + event)

sys.addaudithook(deny_effect)
base, env = (Path(arg).resolve() for arg in sys.argv[1:])
if (Path(sys.base_prefix).resolve() != base or Path(sys.prefix).resolve() != env
        or sys.version_info[:3] != (3, 14, 10) or sysconfig.get_platform() != "win-amd64"):
    raise RuntimeError("Unexpected Python identity or environment binding.")
native = ("asyncpg.protocol.protocol", "psycopg2._psycopg", "toktok._toktok",
          "numpy._core._multiarray_umath")
for name in native:
    origin = Path(importlib.import_module(name).__file__).resolve()
    if origin.suffix.lower() != ".pyd" or not origin.is_relative_to(env):
        raise RuntimeError("Native module resolved outside the fixture venv: " + name)
hindsight = importlib.metadata.distribution("hindsight-api-slim")
if hindsight.version != "1.3.0":
    raise RuntimeError("Unexpected Hindsight version.")
from hindsight_api.main import main
sys.argv = ["hindsight-api", "--help"]
try:
    main()
except SystemExit as exit_signal:
    if exit_signal.code:
        raise
else:
    raise RuntimeError("The CLI help did not exit before startup.")
print(json.dumps({"native_extensions": native, "python": "3.14.10",
                  "hindsight": hindsight.version, "help_entrypoint": "PASS"}))
"""


def command(executable, cwd, env, *args, timeout=120):
    result = subprocess.run([str(executable), "-I", "-B", "-X", "utf8", *map(str, args)],
                            cwd=cwd, env=env, capture_output=True, encoding="utf-8",
                            errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"Isolated child exited {result.returncode}: {result.stderr[-3000:]}")
    return result.stdout.strip()


def probe(root, archive, wheels):
    if ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("A Windows Basic User token is required.")
    pin = json.loads(LOCK.read_bytes())["archive"]
    artifact = Artifact("20261124", "3.14.10", pin["asset_id"], pin["sha256"], pin["size"])
    wheel_files = list(wheels.glob("*.whl"))
    if len(wheel_files) != EXPECTED_WHEELS:
        raise RuntimeError(f"Expected {EXPECTED_WHEELS} selected Windows wheels.")
    baseline = footprint()
    with open_verified(archive, artifact, artifact.identity()) as (payload, _):
        with tarfile.open(fileobj=payload, mode="r:gz") as contents:
            contents.extractall(root, filter="data")
    system = Path(os.environ["SystemRoot"])
    home = root / "empty-home"
    home.mkdir()
    child_env = {"SystemRoot": str(system), "WINDIR": str(system),
                 "COMSPEC": str(system / "System32/cmd.exe"), "PATH": str(system / "System32"),
                 "APPDATA": str(home), "LOCALAPPDATA": str(home), "USERPROFILE": str(home), "HOME": str(home),
                 "TMP": str(root), "TEMP": str(root), "PIP_CONFIG_FILE": os.devnull,
                 "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                 # Placeholder endpoints are never contacted by this help/import probe.
                 "HINDSIGHT_API_DATABASE_URL": "postgresql://wp0@127.0.0.1:1/wp0",
                 "HINDSIGHT_API_LLM_PROVIDER": "ollama",
                 "HINDSIGHT_API_LLM_BASE_URL": "http://127.0.0.1:1/v1",
                 "HINDSIGHT_API_LLM_MODEL": "fixture-only",
                 "HINDSIGHT_API_EMBEDDINGS_PROVIDER": "tei",
                 "HINDSIGHT_API_EMBEDDINGS_TEI_URL": "http://127.0.0.1:1",
                 "HINDSIGHT_API_RERANKER_PROVIDER": "none",
                 "HINDSIGHT_API_KB_EMBEDDINGS_PROVIDER": "text"}
    base, target = root / "python", root / "app venv"
    command(base / "python.exe", root, child_env, "-m", "venv", "--copies", target)
    executable = target / "Scripts/python.exe"
    pip = ("-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir")
    command(executable, root, child_env, *pip, "install", "--no-index", "--find-links", wheels,
            "--only-binary", ":all:", "--no-deps", "--require-hashes", "--no-compile",
            "-r", REQUIREMENTS, timeout=300)
    command(executable, root, child_env, *pip, "check")
    stdout = command(executable, root, child_env, "-c", SMOKE, base, target)
    if "usage: hindsight-api" not in stdout:
        raise RuntimeError("Pinned Hindsight entrypoint did not print CLI help.")
    result = json.loads(stdout.splitlines()[-1])
    if footprint() != baseline:
        raise RuntimeError("Sampled registry or drive mappings changed.")
    return {**result, "status": "PASS", "effective_admin": False, "wheel_count": len(wheel_files),
            "wheel_bytes": sum(path.stat().st_size for path in wheel_files),
            "requirements_sha256": hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest(),
            "pip_check": "PASS", "sampled_host_footprint_equal": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("wheels", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="engram-hindsight-") as temporary:
        result = probe(Path(temporary).resolve(), args.archive.resolve(), args.wheels.resolve())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
