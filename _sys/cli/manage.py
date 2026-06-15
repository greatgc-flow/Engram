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
    parser.add_argument("action", choices=["register", "unregister", "cleanup", "workspace-init"])
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

        elif args.action in ("workspace-init", "workspace_init"):
            if not args.target:
                print("[Error] workspace-init requires a workspace name or path.")
                sys.exit(1)
            t = Path(args.target)
            ws_path = t if t.is_absolute() else base_dir / "workspace" / t
            # workspace-init is out of scope for this refactor; delegate to legacy logic
            _workspace_init_legacy(base_dir, ws_path)

    except Exception as e:
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)


def _workspace_init_legacy(base_dir: Path, ws_path: Path):
    """Minimal workspace init (junction + glue file creation) driven by peers.json."""
    import json, os, shutil
    sys_dir = base_dir / "_sys"
    peers_path = sys_dir / "ai" / "peers.json"
    peers = json.loads(peers_path.read_text(encoding="utf-8")).get("peers", {}) if peers_path.exists() else {}

    print(f"\n{'='*50}\n Workspace Init: {ws_path}\n{'='*50}")
    if not ws_path.exists():
        template_dir = sys_dir / "templates" / "workspace"
        if template_dir.exists():
            shutil.copytree(str(template_dir), str(ws_path))
            print(f"  [OK] Created from template: {ws_path.name}")
        else:
            ws_path.mkdir(parents=True)
            print(f"  [OK] Created: {ws_path.name}")
    else:
        print("  [Info] Workspace exists — adding .ai/ structure only")

    ai_dir = ws_path / ".ai"
    ai_dir.mkdir(exist_ok=True)

    from core.virtualizer import _ensure_junction
    common_src  = sys_dir / "ai" / "common"
    common_link = ai_dir / "common"
    if common_src.exists() and not common_link.exists():
        try:
            _ensure_junction(common_link, common_src)
            print("  [OK] .ai/common → _sys/ai/common")
        except Exception as e:
            print(f"  [Warn] common junction: {e}")

    for peer_id, cfg in peers.items():
        ws_cfg    = cfg.get("workspace", {})
        shadow    = ws_path / Path(ws_cfg.get("shadow_subdir", f".ai/{peer_id}"))
        junction  = ws_path / ws_cfg.get("junction_name", cfg.get("root_dir", f".{peer_id}"))
        shadow.mkdir(parents=True, exist_ok=True)
        glue_file = ws_cfg.get("glue_file")
        if glue_file:
            glue_dest = shadow / glue_file
            if not glue_dest.exists():
                tmpl_rel = ws_cfg.get("glue_template")
                glue_src = sys_dir / cfg.get("sys_subdir", peer_id) / tmpl_rel if tmpl_rel else None
                if glue_src and glue_src.exists():
                    glue_dest.write_text(
                        glue_src.read_text(encoding="utf-8").replace("{{PROJECT_NAME}}", ws_path.name),
                        encoding="utf-8"
                    )
                else:
                    glue_dest.write_text(
                        f"# {peer_id.capitalize()} — {ws_path.name}\n> Context: see [CONTEXT.md](../CONTEXT.md)\n",
                        encoding="utf-8"
                    )
                print(f"  [OK] {peer_id}: {glue_file}")
        npm_global = sys_dir / "env" / "nodejs" / "npm-global"
        if (npm_global / f"{peer_id}.cmd").exists() and not junction.exists():
            try:
                _ensure_junction(junction, shadow)
                print(f"  [OK] {peer_id}: {junction.name} → {shadow.relative_to(ws_path)}")
            except Exception as e:
                print(f"  [Fail] {peer_id}: {e}")

    print(f"\n  Done. '{ws_path.name}' ready.")


if __name__ == "__main__":
    main()
