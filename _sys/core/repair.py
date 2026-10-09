import argparse
import dataclasses
import json
import os
import sys
import contextlib
import io
from pathlib import Path
from typing import Optional, Callable, Any

from core import cli_help, env_manifest, venv_manager, env_ops, env_lock
from core import python_manager, relocation, venv_repair
from core.venv_manager import default_runner
from core.registrar import find_stale_entries
from core.relocation import RegistryOps


# Engram's baseline venv packages by DISTRIBUTION name (pip installs pywinpty; its module is winpty).
_BASELINE_PIP_NAMES = frozenset({"filelock", "psutil", "pydantic", "pywinpty"})
# Seams python_manager.plan_python_update understands (other seams belong to other building blocks).
_PYTHON_SEAMS = frozenset({"downloader", "runner", "free_space", "holders", "rename", "sleep", "now", "venv_policy"})


def _cli_result(res: dict, *, mode: str) -> dict:
    """Map an env_ops result dict onto the CLI result contract (design section 10 exit codes).

    0 ok | 11 preflight / zero mutation | 12 verification failed and rolled back | 13 rollback failed
    | 14 a non-terminal journal blocks the request. An explicit --rollback that ends ROLLED_BACK is a success.
    """
    phase = res.get("phase")
    status = res.get("status")
    detail = res.get("detail", "")
    if phase == "ROLLBACK_FAILED":
        code = 13
    elif mode == "rollback" and phase == "ROLLED_BACK":
        return {"status": "success", "operation": "repair", "detail": "rolled back", "exit_code": 0,
                "op_id": res.get("op_id"), "phase": phase}
    elif status == "success":
        code = 0
    elif phase == "ROLLED_BACK":
        code = 12
    elif phase is None:
        code = 14 if "journal" in detail.lower() else 11
    else:
        code = 12
    return {"status": "success" if code == 0 else "failed", "operation": "repair", "detail": detail,
            "exit_code": code, "op_id": res.get("op_id"), "phase": phase, "failed_step": res.get("failed_step")}


def detect(
    sys_dir: Path | str, base_dir: Path | str, *, 
    runner: Any = default_runner, registry: Optional[RegistryOps] = None, 
    now: Optional[Callable[[], str]] = None
) -> dict:
    sys_dir = Path(sys_dir)
    base_dir = Path(base_dir)
    
    localappdata = None
    if "LOCALAPPDATA" in os.environ:
        localappdata = Path(os.environ["LOCALAPPDATA"])
    
    mread = env_manifest.read_manifest(sys_dir)
    manifest_data = mread.data if mread.status == "ok" else None
    
    drift = env_manifest.detect_root_drift(manifest_data, base_dir, sys_dir, localappdata=localappdata)
    drift_dict = dataclasses.asdict(drift)
    
    findings = venv_manager.run_checks(sys_dir, runner=runner, manifest=manifest_data)
    findings_dicts = [dataclasses.asdict(f) if hasattr(f, "level") else f for f in findings]
    
    stale_registry = find_stale_entries(sys_dir, relay_root=localappdata)
    journal = env_ops.journal_blocks(sys_dir)
    lock = env_lock.inspect(sys_dir) if hasattr(env_lock, "inspect") else None
    
    return {
        "manifest": mread.status,
        "drift": drift_dict,
        "findings": findings_dicts,
        "stale_registry": stale_registry,
        "journal": journal,
        "journal_phase": env_ops.current_phase(sys_dir),
        "lock": lock,
    }


def build_plan(
    sys_dir: Path | str, base_dir: Path | str, detection: dict, *, 
    only: set[str] | None = None, remap_ai_state: bool = False, 
    offline: bool = False, allow_rebuild: bool = True, **seams
) -> dict:
    sys_dir = Path(sys_dir)
    base_dir = Path(base_dir)
    
    valid_only = {"python", "venv", "registry", "state", "ai-state", "manifest", "packages"}
    if only is not None:
        invalid = only - valid_only
        if invalid:
            raise ValueError(f"Unknown only values: {invalid}. Valid: {valid_only}")

    spec = []
    summary = []
    
    manifest_status = detection.get("manifest")
    drift = detection.get("drift", {})
    # Only genuine failures drive a venv repair; passing ok/info checks are not findings.
    findings = [f for f in detection.get("findings", [])
                if f.get("ok") is False or f.get("level") in ("warning", "error")]
    stale_registry = detection.get("stale_registry", [])

    moved = drift.get("status") in ("moved", "copied")
    if manifest_status in ("absent", "corrupt") and not moved:
        # When the root moved, the relocation plan writes the manifest itself (write-manifest step).
        if only is None or "manifest" in only:
            spec.append({"name": "adopt-manifest", "group": "B", "kind": "manifest", "params": {}})
            summary.append("Adopt existing tree into new manifest")
    
    if drift.get("status") in ("moved", "copied"):
        if only is None or "registry" in only or "state" in only or "ai-state" in only:
            spec.append({
                "name": "relocate",
                "group": "A",
                "kind": "relocation",
                "params": {
                    "remap_ai_state": remap_ai_state,
                    "offline": offline,
                    "drift": drift
                }
            })
            summary.append(f"Relocate environment (detected {drift.get('status')})")

    # If stale_registry alone with consistent drift => no venv steps
    if findings and drift.get("status") not in ("moved", "copied"):
        if only is None or "venv" in only:
            spec.append({
                "name": "repair-venv",
                "group": "A",
                "kind": "venv",
                "params": {
                    "allow_rebuild": allow_rebuild,
                    "findings": findings
                }
            })
            summary.append("Repair venv (fix findings)")
    elif drift.get("status") in ("moved", "copied"):
        if only is None or "venv" in only:
            spec.append({
                "name": "repair-venv",
                "group": "A",
                "kind": "venv",
                "params": {
                    "allow_rebuild": allow_rebuild,
                    "findings": findings or [{"name": "console_scripts", "level": "warning",
                                          "detail": "stale-launchers: after relocation"}]
                }
            })
            summary.append("Repair venv (post-relocation)")

    steps = steps_from_spec(sys_dir, base_dir, spec, **seams)
    
    return {
        "steps": steps,
        "spec": spec,
        "summary": summary if summary else ["nothing to repair"],
        "kind": "repair"
    }


def steps_from_spec(sys_dir: Path | str, base_dir: Path | str, spec: list[dict], **seams) -> list[env_ops.Step]:
    sys_dir = Path(sys_dir)
    base_dir = Path(base_dir)
    out = []
    
    for item in spec:
        kind = item["kind"]
        params = item.get("params", {})
        
        if kind == "manifest":
            def do_adopt(ctx):
                props = env_manifest.propose_adoption(sys_dir, base_dir)
                env_manifest.write_manifest(sys_dir, props)
                # an adopted, unmoved install: record where it lives so a LATER move is detectable
                env_manifest._atomic_write_text(sys_dir / "data" / env_manifest.LAST_BASE_DIR_FILENAME, str(base_dir))

            def adopted(ctx):
                return env_manifest.read_manifest(sys_dir).status == "ok"
            out.append(env_ops.Step("adopt-manifest", do_adopt, done=adopted, group="B"))
            
        elif kind == "relocation":
            drift_dict = params.get("drift", {})
            remap = params.get("remap_ai_state", False)
            drift_obj = env_manifest.RootDrift(
                status=drift_dict.get("status", "unknown"),
                previous_root=drift_dict.get("previous_root"),
                source=drift_dict.get("source")
            )
            localappdata = Path(os.environ.get("LOCALAPPDATA", sys_dir / "temp"))
            m = env_manifest.read_manifest(sys_dir).data
            r_steps = relocation.plan_relocation(
                sys_dir, base_dir, manifest=m, drift=drift_obj, 
                localappdata=localappdata, remap_ai_state=remap, 
                now=seams.get("now")
            )
            out.extend(r_steps)
            
        elif kind == "venv":
            allow_rebuild = params.get("allow_rebuild", True)
            findings = params.get("findings", [])
            runner = seams.get("runner", default_runner)
            m = env_manifest.read_manifest(sys_dir).data
            v_steps = venv_repair.plan_venv_repair(
                sys_dir, findings, manifest=m, runner=runner, allow_rebuild=allow_rebuild
            )
            out.extend(v_steps)
            
        elif kind == "python":
            target = params.get("target_version")
            url = params.get("url")
            p_steps = python_manager.plan_python_update(
                sys_dir, target, url=url, sha256=params.get("sha256"),
                allow_downgrade=params.get("allow_downgrade", False),
                allow_major=params.get("allow_major", False),
                offline=params.get("offline", False), force=params.get("force", False),
                installed=params.get("installed"), had_venv=params.get("had_venv"),
                **{k: v for k, v in seams.items() if k in _PYTHON_SEAMS})
            out.extend(p_steps)
            
        elif kind == "packages":
            runner = seams.get("runner", default_runner)
            all_packages = bool(params.get("all_packages"))

            def do_snapshot(ctx):
                snap = venv_manager.build_snapshot(sys_dir, now=env_ops.utc_now())
                venv_manager.write_snapshot(sys_dir, snap)
                ctx.data["packages_before"] = [p["name"] for p in snap["packages"]]

            def do_upgrade_packages(ctx):
                venv_python = sys_dir / "env" / "venv" / "Scripts" / "python.exe"
                names = sorted(_BASELINE_PIP_NAMES)
                if all_packages:
                    latest = venv_manager.latest_snapshot(sys_dir) or {"packages": []}
                    names += sorted(
                        p["name"] for p in latest["packages"]
                        if p.get("requested") and not p.get("editable") and p["name"].lower() not in _BASELINE_PIP_NAMES
                    )
                rc, out_text = runner([str(venv_python), "-m", "pip", "install", "--upgrade", *names], 600.0)
                if rc != 0:
                    raise RuntimeError(f"pip upgrade failed: {out_text.strip()[-300:]}")
                ctx.data["packages_upgraded"] = names

            out.append(env_ops.Step("snapshot-packages", do_snapshot, group="A"))
            out.append(env_ops.Step("upgrade-packages", do_upgrade_packages, group="A"))

    return out


def _python_pin(sys_dir: Path) -> dict:
    """The Python pin declared in runtimes.json (version/url/sha256); empty strings when absent."""
    try:
        data = json.loads((Path(sys_dir) / "runtimes.json").read_text(encoding="utf-8"))
        py = data["runtimes"]["python"]
    except (OSError, ValueError, KeyError):
        py = {}
    return {"version": py.get("version", ""), "url": py.get("url", ""), "sha256": py.get("sha256")}


def _installed_python(sys_dir: Path, seams: dict) -> Optional[str]:
    manifest = env_manifest.read_manifest(sys_dir)
    version = ((manifest.data or {}).get("python") or {}).get("version") if manifest.status == "ok" else None
    if version:
        return version
    exe = Path(sys_dir) / "env" / "python" / "python.exe"
    if not exe.is_file():
        return None
    import re
    rc, out = seams.get("runner", default_runner)([str(exe), "--version"], 20.0)
    m = re.search(r"(\d+\.\d+\.\d+)", out or "")
    return m.group(1) if rc == 0 and m else None


def _spec_needs_runner(spec: list[dict]) -> bool:
    """A python swap renames env/python, which the engine process itself is running on (design 6.1)."""
    return any(item.get("kind") == "python" for item in spec)


def _in_runner() -> bool:
    return os.environ.get("ENGRAM_IN_RUNNER") == "1"


def _handoff_result(sys_dir: Path, op_label: str) -> dict:
    exe = python_manager.prepare_runner(sys_dir, env_ops.new_op_id(op_label), confirmed=True)
    print(f"[i] Handing off to a runner interpreter so the Python tree can be replaced: {exe}")
    return {"status": "success", "operation": "repair", "detail": "handoff to runner", "handoff": True,
            "exit_code": 75}


def _plan_json(plan: dict) -> dict:
    """JSON-serialisable view of a plan (Step objects hold callables)."""
    return {"kind": plan.get("kind"), "summary": plan.get("summary", []), "spec": plan.get("spec", []),
            "steps": [{"name": s.name, "group": s.group} for s in plan.get("steps", [])]}


def _print_plan(plan: dict):
    if not plan["steps"]:
        lines = [line for line in plan.get("summary", []) if line != "nothing to repair"]
        for line in lines:
            print(line)
        if not lines:
            print("nothing to repair")
        return
    for s in plan["summary"]:
        print(s)
    for i, step in enumerate(plan["steps"], 1):
        print(f"Step {i}: [{step.group}] {step.name}")


def _repair_engine_main(ctx: dict, build_plan_fn: Callable, parser_setup: Callable[[argparse.ArgumentParser], None] = None) -> dict:
    """Emit exactly one final JSON result, including failures and recovery modes."""
    if "--json" not in ctx.get("args", []) or cli_help.wants_help(ctx.get("args", [])):
        return _repair_engine_run(ctx, build_plan_fn, parser_setup)
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            result = _repair_engine_run(ctx, build_plan_fn, parser_setup)
        except Exception as exc:
            result = {"status": "failed", "operation": ctx.get("command", "repair"),
                      "detail": str(exc), "exit_code": 11}
    if not result.get("handoff"):
        print(json.dumps(result, default=str))
    result["quiet"] = True
    return result


def _repair_engine_run(ctx: dict, build_plan_fn: Callable, parser_setup: Callable[[argparse.ArgumentParser], None] = None) -> dict:
    sys_dir = Path(ctx["sys_dir"])
    base_dir = Path(ctx["base_dir"])
    args_list = ctx.get("args", [])
    command = ctx.get("command", "engram repair")
    help_verb = command if command in ("repair", "relocate", "update") else "repair"

    p = cli_help.CliParser(help_verb)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", "-y", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--remap-ai-state", action="store_true")
    recovery = p.add_mutually_exclusive_group()
    recovery.add_argument("--resume", action="store_true")
    recovery.add_argument("--rollback", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--only")
    
    if parser_setup:
        parser_setup(p)
    
    try:
        args = p.parse_args(args_list)
        valid_only = {"python", "venv", "registry", "state", "ai-state", "manifest", "packages"}
        if args.only is not None and (not args.only or set(args.only.split(",")) - valid_only):
            p.error("--only requires comma-separated names: " + ",".join(sorted(valid_only)))
    except SystemExit as e:
        return {"status": "success" if e.code == 0 else "failed", "operation": "repair", "detail": "usage", "exit_code": 0 if e.code == 0 else 2}
    if args.dry_run:
        args.apply = False  # --dry-run always wins

    only_set = set(args.only.split(",")) if args.only else None
    seams = ctx.get("seams", {})
    input_fn = seams.get("input_fn", input)
    
    detection = detect(sys_dir, base_dir, now=seams.get("now"))
    
    if hasattr(args, "from_path") and args.from_path and not detection.get("drift", {}).get("previous_root"):
        status = "moved" if not Path(args.from_path).exists() else "copied"
        detection["drift"] = {"status": status, "previous_root": args.from_path, "source": "--from"}
    
    if detection["journal"] is not None:
        if not args.resume and not args.rollback:
            msg = f"Non-terminal journal blocks the request. Run --resume or --rollback for {detection['journal']['op_id']}."
            if not args.json:
                print(msg)
            return {"status": "failed", "operation": "repair", "detail": msg, "exit_code": 14}
            
    if args.resume:
        active = detection["journal"]
        if not active:
            return {"status": "failed", "operation": "repair", "detail": "No journal to resume", "exit_code": 11}
        spec = active.get("data", {}).get("spec", [])
        if _spec_needs_runner(spec) and not _in_runner():
            return _handoff_result(sys_dir, "resume")
        def steps_for(a): return steps_from_spec(sys_dir, base_dir, spec, **seams)
        return _cli_result(env_ops.resume(sys_dir, steps_for), mode="resume")
        
    if args.rollback:
        active = detection["journal"]
        if not active:
            return {"status": "failed", "operation": "repair", "detail": "No journal to rollback", "exit_code": 11}
        spec = active.get("data", {}).get("spec", [])
        if _spec_needs_runner(spec) and not _in_runner():
            return _handoff_result(sys_dir, "rollback")
        def steps_for(a): return steps_from_spec(sys_dir, base_dir, spec, **seams)
        try:
            res = env_ops.rollback(sys_dir, steps_for)
        except env_ops.JournalError as exc:
            return {"status": "failed", "operation": "repair", "detail": str(exc), "exit_code": 11}
        return _cli_result(res, mode="rollback")

    try:
        plan = build_plan_fn(sys_dir, base_dir, detection, only=only_set, remap_ai_state=args.remap_ai_state, offline=args.offline, cli_args=args, seams=seams)
    except ValueError as ve:
        return {"status": "failed", "operation": "repair", "detail": str(ve), "exit_code": 11}
        
    if not plan["steps"]:
        if not args.json:
            _print_plan(plan)
        return {"status": "success", "operation": "repair", "detail": "nothing to repair", "exit_code": 0,
                "plan": _plan_json(plan)}
        
    if not args.apply:
        if not args.json:
            _print_plan(plan)
            print("Run with --apply to execute.")
        return {"status": "success", "operation": "repair", "detail": "dry run", "exit_code": 0,
                "plan": _plan_json(plan)}
        
    if not args.yes and os.environ.get("ENGRAM_ASSUME_YES") != "1":
        if sys.stdin and sys.stdin.isatty():
            _print_plan(plan)
            if args.json:
                print("Proceed? [y/N] ", end="", file=sys.stderr, flush=True)
            ans = input_fn("" if args.json else "Proceed? [y/N] ")
            if not ans.lower().startswith('y'):
                return {"status": "failed", "operation": "repair", "detail": "user declined", "exit_code": 10}
        else:
            return {"status": "failed", "operation": "repair", "detail": "non-interactive without --yes", "exit_code": 11}

    if _spec_needs_runner(plan["spec"]) and not _in_runner():
        return _handoff_result(sys_dir, plan["kind"])
    op_id = env_ops.new_op_id(plan["kind"])
    paths = python_manager.allocate_paths(sys_dir, op_id, env_ops.utc_now)
    try:
        res = env_ops.execute(sys_dir, plan["kind"], plan["steps"], op_id=op_id, paths=paths,
                              initial_data={"spec": plan["spec"]})
    except env_ops.JournalError as exc:
        return {"status": "failed", "operation": "repair", "detail": str(exc), "exit_code": 14}
    return _cli_result(res, mode="apply")


def repair_main(ctx: dict) -> dict:
    return _repair_engine_main(ctx, build_plan)


def relocate_main(ctx: dict) -> dict:
    def setup(p):
        p.add_argument("--from", dest="from_path")
    return _repair_engine_main(ctx, build_plan, setup)


def update_env_main(ctx: dict, only: set[str]) -> dict:
    def setup(p):
        p.add_argument("--to", dest="to_version")
        p.add_argument("--all-packages", action="store_true")
        p.add_argument("--allow-major-runtime-upgrade", action="store_true")
        p.add_argument("--force", action="store_true")
        
    def update_plan(s, b, d, *, cli_args, seams, **kw):
        spec = []
        summary = []
        if "python" in only:
            pin = _python_pin(s)
            target = getattr(cli_args, "to_version", None) or pin["version"]
            url = pin["url"] if target == pin["version"] and pin["url"] else (
                f"https://www.python.org/ftp/python/{target}/python-{target}-embed-amd64.zip")
            sha = pin["sha256"] if target == pin["version"] else None
            installed = _installed_python(s, seams)
            had_venv = (Path(s) / "env" / "venv" / "Scripts" / "python.exe").is_file()
            change = python_manager.classify_change(installed, target)
            if change in ("downgrade", "major") and not getattr(cli_args, "allow_major_runtime_upgrade", False):
                raise ValueError(f"Blocked {change} update {installed} -> {target}: pass --allow-major-runtime-upgrade and --yes.")
            if change == "same" and not getattr(cli_args, "force", False):
                summary.append(f"Python already at {target}")
            else:
                spec.append({
                    "name": "update-python", "group": "A", "kind": "python",
                    "params": {"target_version": target, "url": url, "sha256": sha,
                               "allow_downgrade": change == "downgrade", "allow_major": change == "major",
                               "offline": getattr(cli_args, "offline", False),
                               "installed": installed, "had_venv": had_venv},
                })
                summary.append(f"Update python {installed or 'none'} -> {target} ({change})")

        if "venv" in only:
            spec.append({
                "name": "repair-venv", "group": "A", "kind": "venv", 
                "params": {"allow_rebuild": True, "findings": d.get("findings", [])}
            })
            summary.append("Refresh venv")
            
        if "packages" in only:
            spec.append({
                "name": "upgrade-packages", "group": "A", "kind": "packages",
                "params": {"all_packages": getattr(cli_args, "all_packages", False)}
            })
            summary.append("Upgrade packages")
            
        steps = steps_from_spec(s, b, spec, **seams)
        return {"steps": steps, "spec": spec, "summary": summary, "kind": "update"}
        
    return _repair_engine_main(ctx, update_plan, setup)
