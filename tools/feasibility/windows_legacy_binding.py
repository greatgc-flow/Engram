"""T58 gate for a disposable, bootstrapped Windows Engram checkout with no extra runtimes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = ROOT / "_sys"
sys.path.insert(0, str(SYSTEM))
from core import python_registry  # noqa: E402


def state_digests():
    state = SYSTEM / "data" / "state"
    return {path.relative_to(state): hashlib.sha256(path.read_bytes()).digest()
            for path in state.rglob("*") if path.is_file()}


def run(args):
    result = subprocess.run(args, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=120, encoding="utf-8", errors="replace",
                            env={**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                                 "PYTHONDONTWRITEBYTECODE": "1"})
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} {args[1:3]} exited {result.returncode}")
    return result.stdout


def main():
    if os.name != "nt":
        raise RuntimeError("requires a disposable bootstrapped Windows checkout")
    before = state_digests()
    view = python_registry.inventory(SYSTEM)
    assert view["registry"] is None and view["legacy"]["status"] == "PRESENT", "expected legacy-only checkout"
    base = SYSTEM / view["legacy"]["base_rel"]
    exe = SYSTEM / view["legacy"]["executable_rel"]
    probe = ("import json,sys,pip; print(json.dumps([sys.executable, sys.prefix, sys.base_prefix,"
             "pip.__file__, sys.version.split()[0]]))")
    actual, prefix, base_prefix, pip_file, version = json.loads(run([exe, "-B", "-c", probe]))
    assert Path(actual).samefile(exe), "unexpected interpreter"
    assert Path(prefix).samefile(exe.parents[1]), "unexpected venv prefix"
    # Engram's embedded virtualenv copies the interpreter and stdlib beside the venv exe.
    # The source base used for spawning is identified by pyvenv.cfg home (S-9/S-12).
    assert Path(base_prefix).samefile(exe.parent), "unexpected embedded-copy base prefix"
    cfg = (Path(prefix) / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    homes = [line.split("=", 1)[1].strip() for line in cfg
             if "=" in line and line.split("=", 1)[0].strip() == "home"]
    assert len(homes) == 1 and (Path(homes[0]) / "python.exe").samefile(base), "unexpected venv home"
    assert Path(pip_file).resolve().is_relative_to(Path(prefix).resolve()), "unexpected pip location"
    assert run([base, "-B", "--version"]).strip() == f"Python {version}"
    assert run([exe, "-B", "-m", "pip", "--version"]).startswith("pip ")
    for verb, options in [("repair", ["--only", "manifest"]),
                          ("update", ["--only", "python", "--to", version])]:
        result = json.loads(run(["cmd.exe", "/d", "/c", "engram.cmd", verb,
                                 *options, "--offline", "--dry-run", "--json"]))
        assert result["status"] == "success" and result["exit_code"] == 0, verb
        assert result["plan"]["kind"] == verb, verb
    assert state_digests() == before, "legacy read or dry-run changed lifecycle state"
    assert python_registry.inventory(SYSTEM) == view, "legacy binding changed"
    print(json.dumps({"legacy_binding": "PASS", "python": version, "venv_prefix_and_pip": "PASS",
                      "base_prefix": "env/venv/Scripts", "venv_home": "env/python",
                      "offline_update_and_repair_json": "PASS", "state_file_bytes_equal": True}))


if __name__ == "__main__":
    main()
