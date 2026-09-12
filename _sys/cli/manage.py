"""
manage.py - Thin wrapper. Logic moved to core.virtualizer + core.registrar.
Kept for backward compatibility and direct CLI invocation.
"""
import subprocess
import sys
import traceback
from pathlib import Path

_sys = Path(__file__).parent.parent.resolve()
if str(_sys) not in sys.path:
    sys.path.insert(0, str(_sys))


def get_subst_mappings() -> dict[str, str]:
    """Return current SUBST mappings as {drive_letter: physical_path}.
    Uses encoding='oem' because Windows cmd tools output in OEM code page (cp949 on Korean locales).
    """
    try:
        raw = subprocess.check_output(["subst"], encoding='oem', stderr=subprocess.DEVNULL)
        result = {}
        for line in raw.splitlines():
            parts = line.split("=>")
            if len(parts) == 2:
                drive = parts[0].strip().rstrip(":\\")
                path  = parts[1].strip()
                result[drive] = path
        return result
    except Exception:
        return {}


def _make_ctx(base_dir: Path, extra_args: list) -> dict:
    sys_dir = base_dir / "_sys"
    return {
        "base_dir": base_dir,
        "sys_dir":  sys_dir,
        "paths": {
            "state":      sys_dir / "data" / "state",
            "generated":  sys_dir / "data" / "generated",
            "localappdata": Path(__import__("os").environ.get("LOCALAPPDATA", "")),
        },
        "args":  extra_args,
        "state": {},
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portable Dev Environment Manager")
    parser.add_argument("action", choices=["register", "unregister", "cleanup"])
    parser.add_argument("target",   nargs="?", default="")
    parser.add_argument("--base-dir", default="")
    args, unknown = parser.parse_known_args()

    base_dir = Path(args.base_dir).resolve() if args.base_dir else _sys.parent
    ctx      = _make_ctx(base_dir, unknown)

    try:
        if args.action == "register":
            from core.virtualizer import mount
            from core.registrar   import apply
            import datetime, json
            mount(ctx)
            apply(ctx)
            # Persist state
            state_dir = ctx["paths"]["state"]
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "register.state.json"
            payload = {"timestamp": datetime.datetime.now().isoformat(), "base_dir": str(base_dir), **ctx["state"]}
            state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  [OK] State saved → {state_file.relative_to(base_dir)}")

        elif args.action == "unregister":
            from core.registrar   import remove
            from core.virtualizer import unmount
            remove(ctx)
            unmount(ctx)
            for f in ("register.state.json",):
                sf = ctx["paths"]["state"] / f
                if sf.exists():
                    sf.unlink()
                    print(f"  [OK] State pruned: {f}")

        elif args.action == "cleanup":
            from core.scrubber import run
            run(ctx)

    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



