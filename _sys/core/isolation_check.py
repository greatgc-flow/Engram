"""Read-only optional provider check, dispatched like doctor."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from core import cli_help
from _sys.core.isolation import probe_availability
from _sys.extensions.windows_sandbox import WindowsSandboxProvider
from _sys.extensions.wsl2 import WSL2Provider


def run(ctx: dict) -> dict:
    args = list(ctx.get("args", []))
    parser = cli_help.CliParser("isolation", allow_abbrev=False)
    parser.add_argument("action", choices=["check"], nargs="?")
    parser.add_argument("--json", action="store_true")
    try:
        options = parser.parse_args(args)
        if options.action is None:
            parser.error("the following arguments are required: action")
    except SystemExit as exc:
        return {"status": "success" if exc.code == 0 else "failed",
                "detail": "usage", "exit_code": exc.code, "quiet": True}

    try:
        guidance = json.loads((Path(ctx["sys_dir"]) / "config" / "isolation-guidance.json").read_text(encoding="utf-8"))
        if guidance["schema_version"] != 1:
            raise ValueError("unsupported isolation guidance schema_version")
        providers = [("windows-sandbox", WindowsSandboxProvider()), ("wsl2", WSL2Provider())]
        checks = []
        for backend, provider in providers:
            availability = probe_availability(provider.detect, backend=backend)
            record = asdict(availability)
            record["provider"] = backend
            record["guidance"] = guidance["codes"].get(availability.code, guidance["codes"]["UNKNOWN"])
            checks.append(record)
        report = {"status": "success", "providers": checks}
        if options.json:
            print(json.dumps(report, indent=2))
        else:
            for check in checks:
                advice = check["guidance"]
                print(f"{check['provider']}: {check['status']} ({check['code'] or 'UNKNOWN'})")
                print(f"  Reason: {check['reason']}")
                print(f"  {advice['title']}: {advice['why']}")
                print(f"  Setup may need administrator: {advice['admin_needed']}; reboot: {advice['reboot_needed']}")
                for step in advice["steps"]:
                    print(f"  - {step}")
                print(f"  Without it: {advice['without_it']}")
                print()
        return report
    except Exception as exc:
        report = {"status": "failed", "detail": f"Isolation check internal error: {exc}",
                  "exit_code": 1, "quiet": True}
        if options.json:
            print(json.dumps(report))
        else:
            print(f"[Error] {report['detail']}")
        return report
