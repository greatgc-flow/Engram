"""Offline inventory of the existing Engram Python installation and managed series."""
import json
from pathlib import Path
import re

from core import cli_help, python_registry


def run(ctx):
    parser = cli_help.CliParser("python")
    parser.add_argument("action", nargs="?", choices=("list", "where"))
    parser.add_argument("series", nargs="?")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(ctx.get("args", []))
    if not args.action or (args.series and (args.action != "where" or not re.fullmatch(r"3\.(0|[1-9][0-9]*)", args.series))):
        parser.error("expected list or where [3.MINOR]")
    root = Path(ctx["sys_dir"]).absolute()
    try:
        view = python_registry.inventory(root)
        registry = view["registry"] or {}
        builds = registry.get("builds", {})
        series = {minor: {"build_id": row["active_build"], "version": builds[row["active_build"]]["version"],
                          "executable_rel": builds[row["active_build"]]["executable_rel"]}
                  for minor, row in registry.get("series", {}).items()}
        if args.action == "list":
            data = {"revision": view["revision"], "legacy": view["legacy"], "series": series}
            lines = [f"Legacy default: {view['legacy']['status']} ({view['legacy']['executable_rel']})"]
            lines.extend(f"{minor}  {row['version']}  {row['executable_rel']}" for minor, row in series.items())
        else:
            selected = series.get(args.series) if args.series else view["legacy"]
            if selected is None:
                raise ValueError("Requested Python series is not registered.")
            executable = root / selected["executable_rel"]
            if not executable.is_file():
                raise ValueError("Selected Python executable is missing.")
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
