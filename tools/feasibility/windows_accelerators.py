"""Read-only Windows display adapter inventory for WP0. No inference or GPU allocation."""
import json
import os
from pathlib import Path
import subprocess


def inventory(rows):
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("Name"), str)
                                         or not row["Name"].strip() for row in rows):
        return {"coverage": "UNKNOWN", "adapters": [], "source": "Win32_VideoController"}
    return {"coverage": "MEASURED", "source": "Win32_VideoController",
            "adapters": [{"name": row["Name"], "driver": row.get("DriverVersion"),
                          "inference": "NOT_RUN", "available_bytes": None} for row in rows]}


def main():
    rows = None
    detail = "Windows CIM unavailable on this host"
    if os.name == "nt":
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        query = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                 "$a=@(Get-CimInstance Win32_VideoController -Property Name,DriverVersion | "
                 "Select-Object Name,DriverVersion); ConvertTo-Json -InputObject $a -Compress")
        try:
            completed = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", query],
                                       check=True, capture_output=True, timeout=20)
            rows = json.loads(completed.stdout.decode("utf-8-sig"))
            detail = "Unrecognized CIM response"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            detail = type(exc).__name__
    result = inventory(rows)
    if result["coverage"] == "UNKNOWN":
        result["detail"] = detail
    print(json.dumps(result))
    return int(result["coverage"] == "UNKNOWN")


if __name__ == "__main__":
    raise SystemExit(main())
