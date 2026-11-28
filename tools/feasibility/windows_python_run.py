"""Exercise the public WP2 command through CMD, PowerShell and Git Bash."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "_sys/env/venv/Scripts/python.exe"
PROBE = """
import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "exe": sys.executable,
                  "pip_target": os.environ.get("PIP_TARGET"),
                  "venv": os.environ.get("VIRTUAL_ENV")}))
raise SystemExit(75)
"""


def main():
    if os.name != "nt" or not LEGACY.is_file():
        raise RuntimeError("Requires a bootstrapped disposable Windows checkout.")
    git = shutil.which("git.exe")
    if not git:
        raise RuntimeError("Git for Windows is required for the shell matrix.")
    candidates = [base / "bin/bash.exe" for base in Path(git).parents]
    bash = next((path for path in candidates if path.is_file()), None)
    if not bash:
        raise RuntimeError("Git Bash executable not found beside Git for Windows.")
    entry = ROOT / "engram.cmd"
    sample = "한글 space"
    with tempfile.TemporaryDirectory(prefix="engram-run-") as folder:
        cwd = Path(folder) / sample
        cwd.mkdir()
        (cwd / "probe.py").write_text(PROBE, encoding="ascii")
        env = {**os.environ, "ENGRAM_TEST_ENTRY": str(entry), "ENGRAM_TEST_ARG": sample,
               "PIP_TARGET": str(cwd / "must-not-use"), "PYTHONPATH": str(cwd / "foreign")}
        commands = {
            "cmd": 'cmd.exe /d /s /c ""%ENGRAM_TEST_ENTRY%" python run -- probe.py --help "%ENGRAM_TEST_ARG%""',
            "powershell": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                           "& $env:ENGRAM_TEST_ENTRY python run -- probe.py --help $env:ENGRAM_TEST_ARG; exit $LASTEXITCODE"],
            "git_bash": [str(bash), "-c",
                         '"$(cygpath -u "$ENGRAM_TEST_ENTRY")" python run -- probe.py --help "$ENGRAM_TEST_ARG"'],
        }
        for shell, command in commands.items():
            proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, encoding="utf-8",
                                  errors="replace", timeout=60)
            if proc.returncode != 75:
                raise RuntimeError(f"{shell}: expected child exit 75, got {proc.returncode}: {proc.stderr}")
            result = json.loads(proc.stdout)
            assert Path(result["cwd"]).samefile(cwd), shell
            assert Path(result["exe"]).samefile(LEGACY), shell
            assert Path(result["venv"]).samefile(LEGACY.parents[1]), shell
            assert result["argv"] == ["--help", sample], shell
            assert result["pip_target"] is None, shell
    print(json.dumps({"python_run": "PASS", "shells": list(commands), "forwarded_exit": 75,
                      "caller_directory": True, "unicode_argv": True, "legacy_venv": True}))


if __name__ == "__main__":
    main()
