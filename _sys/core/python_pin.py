"""Resolve and maintain an installation-owned project Python pin."""
import json
import os
from pathlib import Path
import re
import stat

from core import env_lock, env_ops, python_registry

FILENAME = ".engram-python.json"
_SCHEMA = "engram.python-pin.v1"
_FIELDS = {"schema", "installation_id", "series", "build_id", "sha256"}
_MAX_SIZE = 4096


def _location(cwd):
    cwd = cwd.resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("The Python project directory must exist.")
    for ancestor in (cwd, *cwd.parents):
        if os.path.lexists(ancestor / ".git"):
            return ancestor / FILENAME
    return cwd / FILENAME


def _read(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError("Project Python pin path must be an ordinary file.")
    with path.open("rb") as stream:
        raw = stream.read(_MAX_SIZE + 1)
    try:
        if len(raw) > _MAX_SIZE:
            raise ValueError("Project Python pin exceeds its size limit.")
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=python_registry._unique)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid project Python pin. Existing file was preserved.") from exc
    if (not isinstance(document, dict) or document.keys() != _FIELDS or document["schema"] != _SCHEMA
            or not all(isinstance(document[name], str) and 0 < len(document[name]) <= 128 for name in _FIELDS)
            or not re.fullmatch(r"3\.(0|[1-9][0-9]*)", document["series"])
            or not re.fullmatch(r"[a-f0-9]{64}", document["sha256"])):
        raise ValueError("Invalid project Python pin. Existing file was preserved.")
    return document


def _pinned_build(document, registry, series):
    if not registry or document["installation_id"] != registry["installation_id"]:
        raise ValueError("The project Python pin belongs to an unavailable Engram installation.")
    if series is not None and series != document["series"]:
        raise ValueError(f"Requested Python {series} conflicts with the project's {document['series']} pin.")
    build = registry["builds"].get(document["build_id"])
    if not build or build["series"] != document["series"] or build["sha256"] != document["sha256"]:
        raise ValueError("The exact build required by the project Python pin is unavailable.")
    return build


def selected_build(cwd, registry, series):
    """Honor an exact saved build, including a retained build, or defer to normal selection."""
    document = _read(_location(cwd))
    return _pinned_build(document, registry, series) if document is not None else None


def current_build_id(cwd, registry):
    document = _read(_location(cwd))
    if document is None:
        return None
    _pinned_build(document, registry, None)
    return document["build_id"]


def change(root, cwd, series=None):
    """Create a pin for an installed series or remove this installation's pin."""
    path = _location(cwd)
    install_id = python_registry.new_document(root)["installation_id"]
    python_registry._plain(root, "data/state/" + env_lock.LOCK_FILENAME)
    python_registry._plain(root, "data/state/" + env_ops.JOURNAL_FILENAME)
    with env_lock.guard(root, env_ops.new_op_id("python-pin")):
        if env_ops.active_journal(root):
            raise env_ops.JournalError("Complete the interrupted Engram operation before changing a project pin.")
        existing = _read(path)
        if existing is not None and existing["installation_id"] != install_id:
            raise ValueError("Project Python pin belongs to another Engram installation.")
        if series is None:
            if existing is not None:
                path.unlink()
            return {"pin": str(path), "changed": existing is not None}
        registry = python_registry.inventory(root)["registry"]
        row = registry["series"].get(series) if registry else None
        if row is None:
            raise ValueError("Requested Python series is not registered.")
        build_id = row["active_build"]
        build = registry["builds"][build_id]
        if not (root / build["executable_rel"]).is_file():
            raise ValueError("Selected Python executable is missing.")
        document = {"schema": _SCHEMA, "installation_id": install_id,
                    "series": series, "build_id": build_id, "sha256": build["sha256"]}
        if existing is not None and existing != document:
            raise ValueError("An existing project Python pin conflicts. Unpin it explicitly before changing it.")
        if existing is None and not env_lock._create_exclusive(path, json.dumps(document, indent=2) + "\n"):
            raise ValueError("The project Python pin appeared during this operation. Retry to inspect it.")
        return {"pin": str(path), "changed": existing is None, "series": series,
                "build_id": build_id, "version": build["version"]}
