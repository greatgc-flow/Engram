"""
setup.py - Thin wrapper. Logic moved to core.provisioner.
Kept for backward compatibility (legacy callers). 
Modern entry points (_sys/core/bootstrap.bat) route through dispatch.bat -> dispatcher.py -> core.provisioner.deploy.
"""
import sys
from pathlib import Path

_SYS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SYS_DIR / "core"))
from root import bootstrap_root_package  # noqa: E402
bootstrap_root_package(_SYS_DIR)

if str(_SYS_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS_DIR))

from core.provisioner import deploy  # noqa: F401

if __name__ == "__main__":
    import traceback
    from core.provisioner import deploy

    _base = _SYS_DIR.parent
    ctx = {
        "base_dir": _base,
        "sys_dir":  _SYS_DIR,
        "paths":    {
            "state":     _SYS_DIR / "data" / "state",
            "generated": _SYS_DIR / "data" / "generated",
        },
        "args":  sys.argv[1:],
        "state": {},
    }
    try:
        from core.provisioner import _exit_code
        result = deploy(ctx)
        sys.exit(_exit_code(result))
    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
