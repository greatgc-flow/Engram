"""Native selective installation proof for a disposable bootstrapped Windows checkout."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = ROOT / "_sys"

PROBE = """
import json, sys, ssl, sqlite3
print(json.dumps({"version": sys.version.split()[0], "exe": sys.executable,
                  "prefix": sys.prefix, "base_prefix": sys.base_prefix}))
"""


def command(*argv, code=0, parse=True):
    result = subprocess.run(["cmd.exe", "/d", "/c", "engram.cmd", "python", *argv],
                            cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
    if result.returncode != code:
        raise RuntimeError(f"{argv[:3]} returned {result.returncode}: {result.stdout} {result.stderr}")
    return json.loads(result.stdout) if parse else result.stdout


def main(cache):
    if os.name != "nt" or not (SYSTEM / "env/python/python.exe").is_file():
        raise RuntimeError("Expected a disposable, bootstrapped Windows checkout.")
    default = command("where", "--json")["executable"]
    old = command("list", "--json")
    assert old["series"] == {}
    with tempfile.TemporaryDirectory(prefix="engram-install-") as empty:
        result = command("install", "3.14", "--offline", "--cache-dir", empty, "--yes", "--json", code=1)
        assert result["plan"][0]["status"] == "MISSING_CACHE"
    args = ("--offline", "--cache-dir", str(cache), "--yes", "--json")
    preview = command("install", "--all-supported", "--dry-run", *args)
    assert {r["series"]: r["status"] for r in preview["plan"]} == {"3.13": "READY", "3.14": "READY"}
    assert command("list", "--json") == old
    first = command("install", "3.14", *args)
    assert first["revision"] == old["revision"] + 1
    current = command("list", "--json")
    assert set(current["series"]) == {"3.14"}
    added = command("install", "3.14", "3.13", *args)
    assert added["revision"] == first["revision"] + 1
    assert command("install", "--all-supported", *args)["revision"] == added["revision"]
    assert command("where", "--json")["executable"] == default
    actual = {}
    for series in ("3.13", "3.14"):
        # The probe lives outside the installation and its source contains no test-only launcher code.
        with tempfile.TemporaryDirectory(prefix="engram-probe-") as temp:
            script = Path(temp) / "probe.py"
            script.write_text(PROBE, encoding="ascii")
            result = command("run", series, "--", str(script))
        selected = Path(command("where", series, "--json")["executable"])
        assert selected.samefile(result["exe"]) and selected.parent.samefile(result["prefix"])
        assert selected.parent.samefile(result["base_prefix"])
        assert result["version"].startswith(series + ".")
        actual[series] = result["version"]
    with tempfile.TemporaryDirectory(prefix="engram-isolated-") as temp:
        environments = {series: Path(temp) / ("isolated " + series) for series in actual}
        with ThreadPoolExecutor(max_workers=2) as executor:
            jobs = [executor.submit(command, "run", series, "--", "-I", "-B", "-m", "venv",
                                    "--copies", str(path), parse=False)
                    for series, path in environments.items()]
            for job in jobs:
                job.result()
        for series, path in environments.items():
            selected = Path(command("where", series, "--json")["executable"])
            probe = ("import json,sys,pip; print(json.dumps([sys.version.split()[0],sys.prefix,"
                     "sys.base_prefix,pip.__file__]))")
            output = subprocess.check_output([path / "Scripts/python.exe", "-I", "-B", "-c", probe],
                                             cwd=path, timeout=30)
            version, prefix, base, pip = json.loads(output)
            assert version == actual[series]
            assert Path(prefix).samefile(path) and Path(base).samefile(selected.parent)
            assert Path(pip).resolve().is_relative_to(path.resolve())
    print(json.dumps({"selective_install": "PASS", "installed": actual, "revision": added["revision"],
                      "parallel_project_venvs": True,
                      "offline": True, "legacy_default_preserved": True}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
