"""
launcher.py - Thin wrapper. Logic moved to core.launcher.
Kept for backward compatibility.
"""
import sys
from pathlib import Path

_sys = Path(__file__).parent.parent.resolve()
if str(_sys) not in sys.path:
    sys.path.insert(0, str(_sys))

from core.launcher import main

if __name__ == "__main__":
    import traceback, os
    ctx = {
        "base_dir": _sys.parent,
        "sys_dir":  _sys,
        "paths":    {"state": _sys / "data" / "state"},
        "args":     sys.argv[1:],
        "state":    {},
    }
    try:
        main(ctx)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
