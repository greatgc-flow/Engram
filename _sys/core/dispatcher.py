"""
dispatcher.py - Pipeline executor for Portable Dev Environment.
Reads dispatch.json and executes ordered operations per command.
"""
import os
import sys
import json
import datetime
import importlib
from pathlib import Path

sys_dir = Path(__file__).parent.parent.resolve()
base_dir = sys_dir.parent

sys.path.insert(0, str(sys_dir / "core"))
from root import bootstrap_root_package  # noqa: E402
bootstrap_root_package(sys_dir)

if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))

from core import provisioner, state_paths


def _load_json(path: Path) -> dict:
    return provisioner.load_json_with_fallback(path, warn_label=path.name)


def _resolve_paths(base_dir: Path, target_sys_dir: Path | None = None) -> dict:
    """Load environment.json and resolve all aliases to absolute Paths."""
    from core.env_loader import EnvironmentLoader
    effective_sys = target_sys_dir if target_sys_dir is not None else sys_dir
    config_path = effective_sys / "config" / "environment.json"
    loader = EnvironmentLoader(str(config_path), str(base_dir))
    loader.apply_to_os()
    paths = loader.get_paths()
    resolved = {"localappdata": Path(os.environ.get("LOCALAPPDATA", ""))}
    for k, v in paths.items():
        resolved[k] = Path(v)
    # Also inject root and sys for legacy compat
    resolved["root"] = base_dir
    resolved["sys"] = effective_sys
    # If sys_dir was renamed, ensure all sys-relative paths map to effective_sys
    if effective_sys.name != "_sys":
        sys_str = str(base_dir / "_sys")
        target_str = str(effective_sys)
        for k, v in list(resolved.items()):
            if k not in ("root", "localappdata") and isinstance(v, Path):
                v_str = str(v)
    # Inject portable path_entries from env.json into os.environ["PATH"] so subcommands
    # have access to bundled tools (gh, git, etc.) even when invoked outside launcher.py
    env_json_path = effective_sys / "env.json"
    if env_json_path.exists():
        try:
            env_cfg = _load_json(env_json_path)
            bases = {
                "sys": effective_sys,
                "env": effective_sys / "env",
                "tools": effective_sys / "tools",
                "engram": base_dir / ".engram",
            }
            entries = [
                bases.get(e.get("base", "sys"), effective_sys) / e.get("sub", "")
                for e in env_cfg.get("path_entries", [])
            ]
            valid_entries = [str(p) for p in entries if p.exists() and str(p) not in os.environ.get("PATH", "")]
            if valid_entries:
                os.environ["PATH"] = os.pathsep.join(valid_entries) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass

    return resolved


def _build_ctx(cmd: str, extra_args: list) -> dict:
    paths = _resolve_paths(base_dir, sys_dir)
    ctx = {
        "base_dir": base_dir,
        "sys_dir":  sys_dir,
        "paths":    paths,
        "args":     extra_args,
        "command":  cmd,
        "state":    {},
    }
    # Pre-load prior register state for commands that undo it
    if cmd in ("unregister", "menu-disable"):
        for fname in (state_paths.REGISTER_STATE_FILENAME, "install.state.json"):
            sf = paths["state"] / fname
            if sf.exists():
                ctx["prior_state"] = _load_json(sf)
                break
    return ctx


_REGISTER_STATE_KEYS = {"registry_entries"}


def _write_state(ctx: dict) -> None:
    state_dir = ctx["paths"]["state"]
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "base_dir":  str(ctx["base_dir"]),
        **ctx.get("state", {}),
    }
    state_file = state_dir / f"{ctx['command']}.state.json"
    state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    sys_name = ctx.get("sys_dir", sys_dir).name
    print(f"  [OK] State saved → {sys_name}/data/state/{state_file.name}")
    # install pipeline also performs registration ops → keep register.state.json in sync
    if ctx["command"] != "register" and _REGISTER_STATE_KEYS & ctx.get("state", {}).keys():
        reg_file = state_dir / state_paths.REGISTER_STATE_FILENAME
        reg_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _prune_state(ctx: dict) -> None:
    state_dir = ctx["paths"]["state"]
    for target in (state_paths.REGISTER_STATE_FILENAME,):
        f = state_dir / target
        if f.exists():
            f.unlink()
            print(f"  [OK] State pruned: {f.name}")


def _result_failed(result) -> bool:
    if result is False:
        return True
    if not isinstance(result, dict):
        return False
    return str(result.get("status", "")).lower() in {
        "error", "failed", "failure", "incomplete", "postcondition_failed",
    }


def _run_operation(op_id: str, op_cfg: dict, ctx: dict):
    module_name = op_cfg["module"]
    method_name = op_cfg.get("method", "main")
    failure     = op_cfg.get("failure_policy", "abort")

    try:
        mod    = importlib.import_module(module_name)
        method = getattr(mod, method_name)
        result = method(ctx)
    except SystemExit:
        raise
    except Exception as e:
        print(f"  [Error] Operation '{op_id}' ({module_name}.{method_name}): {e}")
        if failure in ("continue", "warn"):
            return {"status": "failed", "operation": op_id, "detail": str(e)}
        raise

    if _result_failed(result):
        detail = (result.get("detail") or result.get("failed") or result) if isinstance(result, dict) else result
        print(f"  [Error] Operation '{op_id}' returned failure: {detail}")
        if failure not in ("continue", "warn"):
            raise RuntimeError(f"operation '{op_id}' failed: {detail}")
        if not isinstance(result, dict):
            result = {"status": "failed", "operation": op_id, "detail": detail}
    return result


def run_pipeline(cmd: str, extra_args: list) -> None:
    dispatch_path = sys_dir / "dispatch.json"
    if not dispatch_path.exists():
        print(f"[Error] dispatch.json not found: {dispatch_path}")
        sys.exit(1)

    cfg        = _load_json(dispatch_path)
    pipelines  = cfg.get("pipelines", {})
    operations = cfg.get("operations", {})

    if cmd not in pipelines:
        print(f"[Error] Unknown command: '{cmd}'")
        print(f"  Available: {', '.join(pipelines.keys())}")
        sys.exit(1)

    ctx = _build_ctx(cmd, extra_args)
    failures = []

    for op_id in pipelines[cmd]:
        if op_id == "state.write":
            if not failures:
                _write_state(ctx)
            continue
        if op_id == "state.prune":
            if not failures:
                _prune_state(ctx)
            continue
        op_cfg = operations.get(op_id)
        if not op_cfg:
            failure = {"status": "failed", "operation": op_id, "detail": "operation is not configured"}
            failures.append(failure)
            print(f"  [Error] Unknown operation '{op_id}'")
            continue
        result = _run_operation(op_id, op_cfg, ctx)
        if _result_failed(result):
            failures.append(result)

    if failures:
        names = ", ".join(str(item.get("operation", "unknown")) for item in failures)
        raise RuntimeError(f"pipeline '{cmd}' incomplete; failed operations: {names}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dispatcher.py <command> [args...]")
        sys.exit(1)
    run_pipeline(sys.argv[1].lower(), sys.argv[2:])
