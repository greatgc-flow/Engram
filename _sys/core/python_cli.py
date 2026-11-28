"""Inspect local Python installations or run a selected interpreter."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from core import cli_help, env_lock, env_ops, provisioner, python_pin, python_registry

_SERIES = re.compile(r"3\.(0|[1-9][0-9]*)")
_RUNTIME_OVERRIDES = ("PYTHON", "PIP_", "UV_", "NPM_CONFIG_", "CONDA_", "_CONDA", "_CE_")


def _inventory(view):
    registry = view["registry"] or {}
    builds = registry.get("builds", {})
    series = {}
    for minor, row in registry.get("series", {}).items():
        build_id = row["active_build"]
        build = builds[build_id]
        series[minor] = {"build_id": build_id, "version": build["version"],
                         "executable_rel": build["executable_rel"]}
    return {"revision": view["revision"], "legacy": view["legacy"], "series": series}


def _caller_directory():
    return Path(os.environ.get("ENGRAM_CALLER_CWD") or Path.cwd())


def _executable(root, view, series, cwd):
    registry = view["registry"]
    selected = python_pin.selected_build(cwd, registry, series)
    if selected is None and series is None:
        selected = view["legacy"]
    elif selected is None and registry and series in registry["series"]:
        build_id = registry["series"][series]["active_build"]
        selected = registry["builds"][build_id]
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
    return _launch_child(root, selector[0] if selector else None, payload)


def _launch_child(root, series, payload=None):
    try:
        if env_ops.active_journal(root) is not None:
            print("An environment operation needs recovery. Run engram repair --resume or --rollback.",
                  file=sys.stderr)
            return 14
        if env_lock.inspect(root)["state"] == "held":
            print("An environment operation is in progress. Retry when it finishes.", file=sys.stderr)
            return 14
        cwd = _caller_directory()
        executable = _executable(root, python_registry.inventory(root), series, cwd)
        env = _child_environment(root, executable)
        if payload is not None:
            command = [str(executable), *payload]
        else:
            if sys.platform != "win32":
                raise ValueError("Python child shells require Windows.")
            if cwd.drive.startswith("\\\\"):
                raise ValueError("CMD needs a local working directory or a mapped drive.")
            windows = Path(os.environ.get("SystemRoot", ""))
            if not windows.is_absolute():
                raise ValueError("Windows SystemRoot is unavailable.")
            system = windows / "System32"
            cmd = system / "cmd.exe"
            # Exclude host Python and pip from shell lookup. Disable CMD AutoRun
            # and implicit search in the project directory.
            env["PATH"] = os.pathsep.join(map(str, (executable.parent, system, windows)))
            env["COMSPEC"] = str(cmd)
            env.pop("NODEFAULTCURRENTDIRECTORYINEXEPATH", None)
            env["NoDefaultCurrentDirectoryInExePath"] = "1"
            command = [str(cmd), "/d", "/q"]
        return subprocess.run(command, cwd=cwd, env=env).returncode
    except (ValueError, OSError, env_ops.JournalError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def run(ctx):
    parser = cli_help.CliParser("python")
    parser.add_argument("action", nargs="?", choices=("list", "where", "run", "use", "install", "pin", "unpin"))
    parser.add_argument("series", nargs="*")
    parser.add_argument("--all-supported", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache-dir")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--json", action="store_true")
    argv = ctx.get("args", [])
    root = Path(ctx["sys_dir"]).absolute()
    if argv[:1] == ["run"]:
        code = _run_child(root, argv, parser)
        return {"status": "failed" if code else "success", "exit_code": code, "quiet": True}

    args = parser.parse_args(argv)
    if any(not _SERIES.fullmatch(minor) for minor in args.series):
        parser.error("Python series must use 3.MINOR format.")
    if args.action == "install":
        if bool(args.series) == args.all_supported or len(set(args.series)) != len(args.series):
            parser.error("Choose distinct Python series or --all-supported.")
        from core import python_install
        cache = Path(args.cache_dir) if args.cache_dir else root / "data/setup-files/python-archives"
        if not cache.is_absolute():
            cache = Path(os.environ.get("ENGRAM_CALLER_CWD") or Path.cwd()) / cache
        try:
            result = python_install.run(root, args.series, all_supported=args.all_supported, offline=args.offline,
                                       cache=cache, preview=args.dry_run, yes=args.yes)
        except (ValueError, OSError, subprocess.SubprocessError, env_ops.JournalError) as exc:
            result = {"status": "failed", "exit_code": 1, "detail": str(exc)}
        if args.json:
            print(json.dumps(result))
        else:
            for row in result.get("plan", []):
                print(f"{row['series']} {row.get('version', '')} {row['status']}")
            if result.get("detail"):
                print(result["detail"], file=sys.stderr)
        return {**result, "quiet": True}
    if args.all_supported or args.offline or args.cache_dir is not None or args.dry_run or args.yes:
        parser.error("Installation flags require the install action.")
    max_series = {"list": 0, "where": 1, "use": 1, "pin": 1, "unpin": 0}
    if args.action not in max_series or len(args.series) > max_series[args.action]:
        parser.error("expected list, where [3.MINOR], run, use, install, pin SERIES, or unpin")
    if args.action == "pin" and not args.series:
        parser.error("pin requires an installed Python series")
    if args.action == "use":
        if args.json:
            parser.error("use starts an interactive shell and takes no --json")
        code = _launch_child(root, args.series[0] if args.series else None)
        return {"status": "failed" if code else "success", "exit_code": code, "quiet": True}
    try:
        if args.action == "list":
            data = _inventory(python_registry.inventory(root))
            lines = [f"Legacy default: {data['legacy']['status']} ({data['legacy']['executable_rel']})"]
            lines.extend(f"{minor}  {row['version']}  {row['executable_rel']}" for minor, row in data["series"].items())
        elif args.action in ("pin", "unpin"):
            data = python_pin.change(root, _caller_directory(), args.series[0] if args.series else None)
            verb = "Updated" if data["changed"] else "No change to"
            lines = [f"{verb} project Python pin at {data['pin']}"]
        else:
            executable = _executable(root, python_registry.inventory(root),
                                     args.series[0] if args.series else None, _caller_directory())
            data = {"executable": str(executable)}
            lines = [str(executable)]
        code = 0
    except (env_lock.EnvLockBusy, env_ops.JournalError) as exc:
        data = {"detail": str(exc)}
        lines = [str(exc)]
        code = 14
    except (ValueError, OSError) as exc:
        data = {"detail": str(exc)}
        lines = [str(exc)]
        code = 1
    result = {"status": "failed" if code else "success", "exit_code": code, **data}
    print(json.dumps(result) if args.json else "\n".join(lines))
    return {**result, "quiet": True}
