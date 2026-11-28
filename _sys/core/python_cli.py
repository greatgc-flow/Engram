"""Inspect local Python installations or run a selected interpreter."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from core import cli_help, env_lock, env_ops, provisioner, python_registry

_SERIES = re.compile(r"3\.(0|[1-9][0-9]*)")
_RUNTIME_OVERRIDES = ("PYTHON", "PIP_", "UV_", "NPM_CONFIG_", "CONDA_", "_CONDA", "_CE_")


def _inventory(root):
    view = python_registry.inventory(root)
    registry = view["registry"] or {}
    builds = registry.get("builds", {})
    series = {}
    for minor, row in registry.get("series", {}).items():
        build_id = row["active_build"]
        build = builds[build_id]
        series[minor] = {"build_id": build_id, "version": build["version"],
                         "executable_rel": build["executable_rel"]}
    return {"revision": view["revision"], "legacy": view["legacy"], "series": series}


def _executable(root, view, series):
    selected = view["series"].get(series) if series else view["legacy"]
    if selected is None:
        raise ValueError("Requested Python series is not registered.")
    executable = root / selected["executable_rel"]
    if not executable.is_file():
        raise ValueError("Selected Python executable is missing.")
    return executable


def _child_environment(root, executable):
    env = os.environ.copy()
    excluded = [root / path for path in ("env/python", "env/venv", "env/python-versions",
                                         "env/python-envs", "AI/apps", "AI/runtime")]
    excluded.extend(Path(env[name]) for name in ("VIRTUAL_ENV", "CONDA_PREFIX")
                    if env.get(name) and Path(env[name]).is_absolute())
    excluded = [Path(os.path.normcase(path)) for path in excluded]
    remaining = []
    for entry in env.get("PATH", "").split(os.pathsep):
        path = Path(os.path.normcase(os.path.normpath(entry.strip('"'))))
        if path.is_absolute() and not any(path.is_relative_to(prefix) for prefix in excluded):
            remaining.append(entry)
    for key in tuple(env):
        name = key.upper()
        if name.startswith(_RUNTIME_OVERRIDES) or name in ("VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT", "ENGRAM_CALLER_CWD"):
            del env[key]
    env["PATH"] = os.pathsep.join([str(executable.parent), *remaining])
    env["PYTHONNOUSERSITE"] = "1"
    if executable == provisioner.venv_python_exe(root):
        env["VIRTUAL_ENV"] = str(executable.parents[1])
    return env


def _run_child(root, argv, parser):
    if "--" not in argv[1:]:
        parser.error("expected run [3.MINOR] -- PYTHON_ARGS")
    boundary = argv.index("--")
    selector, payload = argv[1:boundary], argv[boundary + 1:]
    if not payload or len(selector) > 1 or (selector and not _SERIES.fullmatch(selector[0])):
        parser.error("expected run [3.MINOR] -- PYTHON_ARGS")
    try:
        if env_ops.active_journal(root) is not None:
            print("An environment operation needs recovery. Run engram repair --resume or --rollback.",
                  file=sys.stderr)
            return 14
        if env_lock.inspect(root)["state"] == "held":
            print("An environment operation is in progress. Retry when it finishes.", file=sys.stderr)
            return 14
        executable = _executable(root, _inventory(root), selector[0] if selector else None)
        cwd = Path(os.environ.get("ENGRAM_CALLER_CWD") or Path.cwd())
        return subprocess.run([str(executable), *payload], cwd=cwd,
                              env=_child_environment(root, executable)).returncode
    except (ValueError, OSError, env_ops.JournalError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def run(ctx):
    parser = cli_help.CliParser("python")
    parser.add_argument("action", nargs="?", choices=("list", "where", "run"))
    parser.add_argument("series", nargs="?")
    parser.add_argument("--json", action="store_true")
    argv = ctx.get("args", [])
    root = Path(ctx["sys_dir"]).absolute()
    if argv[:1] == ["run"]:
        code = _run_child(root, argv, parser)
        return {"status": "failed" if code else "success", "exit_code": code, "quiet": True}

    args = parser.parse_args(argv)
    if not args.action or (args.series and (args.action != "where" or not _SERIES.fullmatch(args.series))):
        parser.error("expected list, where [3.MINOR], or run [3.MINOR] -- PYTHON_ARGS")
    try:
        view = _inventory(root)
        if args.action == "list":
            data = view
            lines = [f"Legacy default: {view['legacy']['status']} ({view['legacy']['executable_rel']})"]
            lines.extend(f"{minor}  {row['version']}  {row['executable_rel']}" for minor, row in view["series"].items())
        else:
            executable = _executable(root, view, args.series)
            data = {"executable": str(executable)}
            lines = [str(executable)]
        code = 0
    except (ValueError, OSError) as exc:
        data = {"detail": str(exc)}
        lines = [str(exc)]
        code = 1
    result = {"status": "failed" if code else "success", "exit_code": code, **data}
    print(json.dumps(result) if args.json else "\n".join(lines))
    return {**result, "quiet": True}
