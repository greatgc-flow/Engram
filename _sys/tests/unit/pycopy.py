"""Test helper: place a runnable copy of the *base* interpreter at ``dest_exe``.

``sys.executable`` is a DLL-less launcher when pytest runs under a venv, so copying it alone fails with
0xC0000135. The base interpreter is copied together with its top-level DLLs / stdlib zip / ``._pth``; a full
(non-embeddable) install additionally gets a ``pyvenv.cfg`` whose ``home`` points at the base install.
"""
import shutil
import sys
from pathlib import Path


def base_python_exe() -> Path:
    return Path(getattr(sys, "_base_executable", None) or sys.executable)


def copy_python(dest_exe) -> Path:
    dest_exe = Path(dest_exe)
    dest_exe.parent.mkdir(parents=True, exist_ok=True)
    base = base_python_exe()
    base_dir = base.parent
    for f in base_dir.iterdir():
        if f.is_file() and (f == base or f.suffix.lower() in (".dll", ".zip", "._pth") or f.name.endswith("._pth")):
            shutil.copy(f, dest_exe.parent / (dest_exe.name if f == base else f.name))
    if not any(base_dir.glob("python*._pth")):
        (dest_exe.parent / "pyvenv.cfg").write_text(f"home = {base_dir}\n", encoding="utf-8")
    return dest_exe
