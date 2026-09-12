"""
build_exe.py - Compiles Engram.exe wrapper from wrapper.cs using csc.exe.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

_TOOLS_WINGET_DIR = Path(__file__).resolve().parent
REPO_ROOT = _TOOLS_WINGET_DIR.parent.parent


def find_csc() -> str | None:
    """Find csc.exe on PATH or in standard .NET Framework installation directories."""
    csc = shutil.which("csc.exe") or shutil.which("csc")
    if csc:
        return csc

    candidates = [
        r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def build_wrapper_exe(source_path: Path | None = None, output_path: Path | None = None) -> int:
    csc = find_csc()
    if not csc:
        print("[Error] csc.exe compiler not found on PATH or standard Framework directories.")
        return 1

    source = Path(source_path) if source_path else _TOOLS_WINGET_DIR / "wrapper.cs"
    target = Path(output_path) if output_path else REPO_ROOT / "Engram.exe"

    if not source.exists():
        print(f"[Error] Source file not found: {source}")
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        csc,
        "/target:exe",
        "/optimize+",
        f"/out:{target}",
        str(source),
    ]

    print(f"Building {target.name} from {source}...")
    print(f"Compiler: {csc}")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"[Error] Compilation failed (exit code {proc.returncode}):")
        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr)
        return proc.returncode

    print(f"[OK] Built {target} ({target.stat().st_size} bytes)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Build Engram.exe wrapper")
    parser.add_argument("--source", default=None, help="Path to wrapper.cs")
    parser.add_argument("--output", default=None, help="Path to output Engram.exe")
    args = parser.parse_args()

    rc = build_wrapper_exe(args.source, args.output)
    sys.exit(rc)


if __name__ == "__main__":
    main()
