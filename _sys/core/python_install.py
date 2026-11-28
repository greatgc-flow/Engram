"""Plan, stage and publish explicitly requested extra Python runtimes."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from uuid import uuid4

from core import env_lock, env_ops, provisioner, python_provider, python_registry, version_resolver
from core.python_artifact import Artifact, ProviderError, open_verified

_OFFLINE_PINS = Path(__file__).resolve().parents[1] / "defaults/python-offline-artifacts.json"
_PROBE = r"""
import ctypes, sqlite3, ssl, sys, sysconfig
from pathlib import Path
import pip
exe, base, version, abi = sys.argv[1:]
assert Path(sys.executable).samefile(exe)
assert Path(sys.base_prefix).samefile(base)
assert Path(sys.prefix).samefile(Path(exe).parents[1])
assert tuple(sys.version_info[:3]) == tuple(map(int, version.split(".")))
assert sys.implementation.name == "cpython"
assert sys.implementation.cache_tag == "cpython-" + abi[2:]
assert not sysconfig.get_config_var("Py_GIL_DISABLED")
assert sysconfig.get_platform() == "win-amd64" and ctypes.sizeof(ctypes.c_void_p) == 8
assert Path(pip.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert ssl.OPENSSL_VERSION
with sqlite3.connect(":memory:") as conn:
    assert conn.execute("SELECT 1").fetchone() == (1,)
"""


@dataclass(frozen=True)
class InstallPlan:
    registry: dict
    rows: list[dict]
    staged: list[tuple[str, Artifact, Path]]
    offline: bool
    patch: bool = False


def offline_artifacts():
    """Use the reviewed pins shipped with this version of Engram."""
    doc = json.loads(_OFFLINE_PINS.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).date()
    return [Artifact(doc["release"], row["version"], row["asset_id"], row["sha256"], row["size"])
            for row in doc["artifacts"] if today <= date.fromisoformat(row["support_through"])]


def _candidates(offline):
    if offline:
        return offline_artifacts()
    source = version_resolver.resolve_latest("python", "endoflife_python", "", "python")
    if source["status"] != "ok":
        raise ProviderError("CPython source lifecycle could not be verified.")
    release = python_provider.fetch_release()
    measured = python_provider.assess(source["source_catalog"], release, {}, ())
    eligible = {row["source_version"] for row in measured["series"].values()
                if row["binary_status"] == "AVAILABLE" and row["support_phase"] in ("BUGFIX", "SECURITY_ONLY")}
    return [artifact for artifact in release.artifacts if artifact.version in eligible]


def plan(root, selected, all_supported, offline, cache):
    view = python_registry.inventory(root)
    registry = view["registry"] or python_registry.new_document(root)
    needs_candidate = all_supported or any(minor not in registry["series"] for minor in selected)
    candidates = {item.version.rsplit(".", 1)[0]: item for item in _candidates(offline)} if needs_candidate else {}
    targets = sorted(candidates, key=lambda value: tuple(map(int, value.split(".")))) if all_supported else selected
    if not targets:
        raise ProviderError("No eligible Python series were found.")
    rows, staged = [], []
    for minor in targets:
        present = registry["series"].get(minor)
        artifact = candidates.get(minor)
        if present is not None:
            build = registry["builds"][present["active_build"]]
            status = "INSTALLED" if (root / build["executable_rel"]).is_file() else "INSTALLED_MISSING"
            rows.append({"series": minor, "version": build["version"], "status": status})
        elif artifact is None:
            rows.append({"series": minor, "status": "UNAVAILABLE"})
        else:
            source = cache / python_provider.asset_name(artifact)
            status = "MISSING_CACHE" if offline and not source.is_file() else "READY"
            rows.append({"series": minor, "status": status, "version": artifact.version,
                         "sha256": artifact.sha256, "asset": source.name})
            if status == "READY":
                staged.append((minor, artifact, source))
    return InstallPlan(registry, rows, staged, offline)


def plan_update(root, selected, offline, cache):
    view = python_registry.inventory(root)
    registry = view["registry"] or python_registry.new_document(root)
    installed = registry["series"]
    targets = selected or sorted(installed, key=lambda minor: int(minor.split(".")[1]))
    if any(minor not in installed for minor in targets):
        raise ProviderError("Python update requires installed extra series. Use install to add one.")
    candidates = {item.version.rsplit(".", 1)[0]: item for item in _candidates(offline)} if targets else {}
    rows, staged = [], []
    for minor in targets:
        build = registry["builds"][installed[minor]["active_build"]]
        row = {"series": minor, "installed": build["version"], "version": build["version"]}
        candidate = candidates.get(minor)
        if not (root / build["executable_rel"]).is_file():
            row["status"] = "INSTALLED_MISSING"
        elif candidate is None:
            row["status"] = "UNAVAILABLE"
        elif int(candidate.version.rsplit(".", 1)[1]) <= int(build["version"].rsplit(".", 1)[1]):
            row["status"] = "NO_NEWER_BUILD"
        elif any(build[key] != candidate.identity()[key]
                 for key in ("implementation", "provider", "abi", "arch", "flavor")):
            row["status"] = "IDENTITY_CONFLICT"
        else:
            source = cache / python_provider.asset_name(candidate)
            status = "MISSING_CACHE" if offline and not source.is_file() else "READY"
            row.update({"status": status, "version": candidate.version,
                        "sha256": candidate.sha256, "asset": source.name})
            if status == "READY":
                staged.append((minor, candidate, source))
        rows.append(row)
    return InstallPlan(registry, rows, staged, offline, patch=True)


def _eligible(plan):
    return all(row["status"] in ("READY", "INSTALLED", "NO_NEWER_BUILD") for row in plan.rows)


class _HttpsRedirect(provisioner._SameHostRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ProviderError("Python download redirect must use HTTPS.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(path, artifact):
    request = urllib.request.Request(python_provider.download_url(artifact),
                                     headers={"User-Agent": "Engram-Python-Install"})
    try:
        with urllib.request.build_opener(_HttpsRedirect()).open(request, timeout=30) as response, path.open("xb") as out:
            remaining = artifact.size
            while remaining:
                chunk = response.read(min(1 << 20, remaining))
                if not chunk:
                    raise ProviderError("Python download ended early.")
                out.write(chunk)
                remaining -= len(chunk)
            if response.read(1):
                raise ProviderError("Python download exceeded the published size.")
    except (OSError, http.client.HTTPException) as exc:
        raise ProviderError(f"Python download failed ({type(exc).__name__}).") from exc


def _probe(base, scratch, artifact):
    system = Path(os.environ["SystemRoot"])
    env = {"SYSTEMROOT": str(system), "PATH": str(system / "System32"),
           "TEMP": str(scratch), "TMP": str(scratch), "PIP_CONFIG_FILE": os.devnull}
    venv = scratch / "venv"
    exe = venv / "Scripts/python.exe"

    def checked(program, *argv):
        completed = subprocess.run([str(program), "-I", "-B", *map(str, argv)], cwd=scratch,
                                   env=env, capture_output=True, timeout=180)
        if completed.returncode:
            raise ProviderError(f"Python {artifact.version} failed its local runtime check ({argv[0]}).")

    checked(base / "python.exe", "-m", "venv", "--copies", venv)
    checked(exe, "-c", _PROBE, exe, base, artifact.version, artifact.identity()["abi"])
    checked(exe, "-m", "pip", "--isolated", "--disable-pip-version-check", "check")


def _stage(root, destination, artifact, source, offline):
    series = python_registry._plain(root, destination.parent.relative_to(root).as_posix())
    series.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stage-", dir=series) as directory:
        scratch = Path(directory)
        if not source.is_file() and not offline:
            source = scratch / "download.tar.gz"
            _download(source, artifact)
        with open_verified(source, artifact, artifact.identity()) as (stream, _):
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                archive.extractall(scratch, filter="data")
        if destination.exists():
            raise ProviderError("The selected build directory already exists.")
        (scratch / "python").rename(destination)
        try:
            _probe(destination, scratch, artifact)
        except Exception:
            shutil.rmtree(destination)
            raise


def _result(code, **details):
    return {"status": "failed" if code else "success", "exit_code": code, **details}


def apply(root, plan):
    if not _eligible(plan):
        return _result(1, plan=plan.rows)
    if not plan.staged:
        return _result(0, plan=plan.rows, revision=plan.registry["revision"])
    if env_ops.active_journal(root) or env_lock.inspect(root)["state"] == "held":
        return _result(14, plan=plan.rows, detail="Finish the current Engram lifecycle operation before changing Python.")

    current = python_registry.inventory(root)["registry"] or python_registry.new_document(root)
    if current["revision"] != plan.registry["revision"] or current["installation_id"] != plan.registry["installation_id"]:
        return _result(1, plan=plan.rows, detail="The Python registry changed. Review a fresh install plan.")
    registry = deepcopy(plan.registry)
    staged_paths = []
    try:
        for minor, artifact, source in plan.staged:
            build = f"pbs-{artifact.asset_id}-{uuid4().hex[:10]}"
            relative = f"env/python-versions/{minor}/{build}"
            destination = python_registry._plain(root, relative)
            _stage(root, destination, artifact, source, plan.offline)
            staged_paths.append(destination)
            if plan.patch:
                previous = registry["series"][minor]["active_build"]
                registry["builds"][previous]["state"] = "RETAINED"
            registry["series"][minor] = {"channel": "stable", "active_build": build, "policy": "compatible_patch"}
            registry["builds"][build] = {**artifact.identity(), "series": minor, "owner": "engram", "state": "ACTIVE",
                                         "executable_rel": relative + "/python.exe"}
    except Exception:
        for directory in reversed(staged_paths):
            shutil.rmtree(python_registry._plain(root, directory.relative_to(root).as_posix()))
        raise

    # After entering publication, recovery can need these exact staged paths.
    registry["revision"] += 1
    committed = python_registry.publish(root, plan.registry["revision"], registry)
    if committed["phase"] != "COMMITTED":
        return _result(committed["exit_code"], plan=plan.rows, detail=committed["detail"])
    status = "UPDATED" if plan.patch else "INSTALLED"
    rows = [{**row, "status": status} if row["status"] == "READY" else row for row in plan.rows]
    return _result(0, plan=rows, revision=registry["revision"])


def run(root, selected, *, all_supported, offline, cache, preview, yes, patch=False):
    proposal = plan_update(root, selected, offline, cache) if patch else plan(root, selected, all_supported, offline, cache)
    eligible = _eligible(proposal)
    if preview or not eligible:
        return _result(0 if eligible else 1, plan=proposal.rows, preview=True, offline=offline)
    if not proposal.staged:
        return _result(0, plan=proposal.rows, revision=proposal.registry["revision"])
    if sys.platform != "win32":
        return _result(1, plan=proposal.rows, detail="Managed Python changes require Windows x64.")
    if not yes:
        for row in proposal.rows:
            print(f"{row['series']} {row['status']} {row.get('version', '')} {row.get('sha256', '')}", file=sys.stderr)
        if not sys.stdin.isatty():
            return _result(10, plan=proposal.rows, detail="Use --yes for a non-interactive Python change.")
        print("Apply this Python plan? [y/N] ", end="", file=sys.stderr, flush=True)
        try:
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            return _result(10, plan=proposal.rows, detail="Python change cancelled.")
    return apply(root, proposal)
