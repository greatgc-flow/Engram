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
if str(sys_dir) not in sys.path:
    sys.path.insert(0, str(sys_dir))


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Warning] Failed to load {path.name}: {e}")
    return {}


def _resolve_paths(base_dir: Path) -> dict:
    """Load environment.json and resolve all aliases to absolute Paths."""
    from core.env_loader import EnvironmentLoader
    config_path = base_dir / "_sys" / "config" / "environment.json"
    loader = EnvironmentLoader(str(config_path), str(base_dir))
    loader.apply_to_os()
    paths = loader.get_paths()
    resolved = {"localappdata": Path(os.environ.get("LOCALAPPDATA", ""))}
    for k, v in paths.items():
        resolved[k] = Path(v)
    # Also inject root and sys for legacy compat
    resolved["root"] = base_dir
    resolved["sys"] = base_dir / "_sys"
    return resolved


def _build_ctx(cmd: str, extra_args: list) -> dict:
    paths = _resolve_paths(base_dir)
    ctx = {
        "base_dir": base_dir,
        "sys_dir":  sys_dir,
        "paths":    paths,
        "args":     extra_args,
        "command":  cmd,
        "state":    {},
    }
    # Pre-load prior register state for commands that undo it
    if cmd in ("unregister", "cleanup"):
        for fname in ("register.state.json", "install.state.json"):
            sf = paths["state"] / fname
            if sf.exists():
                ctx["prior_state"] = _load_json(sf)
                break
    return ctx


_REGISTER_STATE_KEYS = {"subst_drive", "registry_entries", "junctions"}


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
    print(f"  [OK] State saved → _sys/data/state/{state_file.name}")
    # install pipeline also performs registration ops → keep register.state.json in sync
    if ctx["command"] != "register" and _REGISTER_STATE_KEYS & ctx.get("state", {}).keys():
        reg_file = state_dir / "register.state.json"
        reg_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _prune_state(ctx: dict) -> None:
    state_dir = ctx["paths"]["state"]
    for target in ("register.state.json",):
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
        detail = result.get("detail") or result.get("failed") or result
        print(f"  [Error] Operation '{op_id}' returned failure: {detail}")
        if failure not in ("continue", "warn"):
            raise RuntimeError(f"operation '{op_id}' failed: {detail}")
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
