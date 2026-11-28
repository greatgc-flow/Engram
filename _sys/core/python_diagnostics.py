"""Read-only registered Python health and reference observations."""
import os
import zipfile

from core import env_ops, python_env_restore, python_pin, python_registry, python_runtime_backup


def _live_builds(root, builds, environments):
    try:
        import psutil
    except ImportError:
        return set(), "UNKNOWN"

    images = {}
    for key, build in builds.items():
        executable = root / build["executable_rel"]
        for image in (executable, executable.with_name("pythonw.exe")):
            images.setdefault(os.path.normcase(os.path.normpath(image)), set()).add(key)
    for row in environments.values():
        if row["build_id"] in builds:
            for name in ("python.exe", "pythonw.exe"):
                image = root / row["root_rel"] / "Scripts" / name
                images.setdefault(os.path.normcase(os.path.normpath(image)), set()).add(row["build_id"])
    if not images:
        return set(), "UNKNOWN"

    found = set()
    try:
        for process in psutil.process_iter(["name"]):
            try:
                if (process.info["name"] or "").casefold() not in ("python.exe", "pythonw.exe"):
                    continue
                actual = process.exe()
                keys = images.get(os.path.normcase(os.path.normpath(actual))) if actual else None
                if keys and process.is_running():
                    found.update(keys)
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
    except (psutil.Error, OSError):
        return found, "PARTIAL" if found else "UNKNOWN"
    return found, "PARTIAL"


def _backup_builds(root, sources, builds, findings):
    references = set()
    observed = False
    for number, source in enumerate(sources, start=1):
        try:
            snapshot = python_runtime_backup.build_references(root, source)
        except (ValueError, OSError, zipfile.BadZipFile):
            findings.append({"code": "BACKUP_REFERENCE_UNAVAILABLE", "detail": f"Backup input {number}"})
            continue
        observed = True
        saved = {(build["sha256"], build["version"], build["provider"], build["abi"])
                 for build in snapshot.values()}
        for key, build in builds.items():
            identity = (build["sha256"], build["version"], build["provider"], build["abi"])
            if key in snapshot or identity in saved:
                references.add(key)
    return references, "PARTIAL" if observed else "UNKNOWN"


def report(root, cwd, series, *, scan_processes=False, backups=()):
    view = python_registry.inventory(root)
    registry = view["registry"] or {}
    selected = registry.get("series", {})
    if series is not None and series not in selected:
        raise ValueError("Requested Python series is not registered.")

    all_builds = registry.get("builds", {})
    builds = {key: build for key, build in all_builds.items()
              if series is None or build["series"] == series}
    active = {row["active_build"] for row in selected.values()}
    environments = registry.get("environments", {})
    live, live_coverage = _live_builds(root, builds, environments) if scan_processes else (set(), "UNKNOWN")
    registrations = {row["build_id"] for row in environments.values()}
    bindings = {row["build_id"] for row in registry.get("bindings", {}).values() if "build_id" in row}
    findings = []
    backup_refs, backup_coverage = _backup_builds(root, backups, builds, findings)
    try:
        pin = python_pin.current_build_id(cwd, view["registry"])
    except (OSError, ValueError) as exc:
        findings.append({"code": "PROJECT_PIN_INVALID", "detail": str(exc)})
        pin = None
    python_registry._plain(root, "data/state/" + env_ops.JOURNAL_FILENAME)
    pending = env_ops.active_journal(root) is not None
    if pending:
        findings.append({"code": "RECOVERY_REQUIRED", "detail": "Complete the active Engram operation."})
    if series is None and view["legacy"]["status"] != "PRESENT":
        findings.append({"code": "LEGACY_RUNTIME_INCOMPLETE", "detail": view["legacy"]["status"]})

    rows = []
    for key, build in builds.items():
        installed = (root / build["executable_rel"]).is_file()
        if not installed:
            findings.append({"code": "BUILD_MISSING", "detail": key})
        references = []
        for present, label in ((key in active, "ACTIVE_SERIES"),
                               (key in registrations, "REGISTERED_ENVIRONMENT"),
                               (key in bindings, "CONSUMER_BINDING"),
                               (key == pin, "PROJECT_PIN"),
                               (key in live, "LIVE_PROCESS"),
                               (key in backup_refs, "BACKUP_REFERENCE"),
                               (pending, "PENDING_OPERATION")):
            if present:
                references.append(label)
        rows.append({"build_id": key, "series": build["series"], "version": build["version"],
                     "state": build["state"], "installed": installed, "references": references,
                     "retirement": "PROTECTED" if references else "UNVERIFIED"})
    for key, environment in environments.items():
        if environment["build_id"] not in builds:
            continue
        destination = root / environment["root_rel"]
        if not destination.is_dir():
            findings.append({"code": "ENVIRONMENT_MISSING", "detail": key})
            continue
        base = root / builds[environment["build_id"]]["executable_rel"]
        try:
            usable = python_env_restore._existing(root, destination, base)
        except (ValueError, OSError):
            usable = False
        if not usable:
            findings.append({"code": "ENVIRONMENT_REBUILD_REQUIRED", "detail": key})
    return {"revision": view["revision"], "legacy": view["legacy"], "builds": rows, "findings": findings,
            "coverage": {"external_projects": "UNKNOWN", "backups": backup_coverage, "live_processes": live_coverage}}
