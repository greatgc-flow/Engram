"""Read-only registered Python health and reference observations."""
from core import env_ops, python_env_restore, python_pin, python_registry


def report(root, cwd, series):
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
    registrations = {row["build_id"] for row in environments.values()}
    bindings = {row["build_id"] for row in registry.get("bindings", {}).values() if "build_id" in row}
    findings = []
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
            "coverage": {"external_projects": "UNKNOWN", "backups": "UNKNOWN", "live_processes": "UNKNOWN"}}
