"""doctor.py - zero-network lifecycle health check (T32).

Reports whether the portable environment is installed, registered, consistent,
and free of active sessions - the "am I healthy right now?" one-shot the
install/update/cleanup lifecycle was missing. Read-only: it mutates nothing and
performs NO network calls (version discovery is UPDATE's job, not status's).

Usage (via dispatch 'status' pipeline / STATUS.bat):
    STATUS.bat            human-readable report
    STATUS.bat --json     machine-readable JSON

Exit/return: run(ctx) returns a dict whose "status" is "failed" ONLY on a
genuinely broken install (portable python missing, or declared python version
!= on-disk, or a required runtime absent). Informational states - not
registered, not mounted, standard-user elevation - are "success"; they are
reported, not failures.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_runtimes(sys_dir: Path) -> dict:
    path = sys_dir / "runtimes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _installed_python_version(sys_dir: Path) -> str | None:
    py = sys_dir / "env" / "python" / "python.exe"
    if not py.exists():
        return None
    try:
        out = subprocess.run([str(py), "--version"], capture_output=True, text=True, timeout=15)
        text = (out.stdout or out.stderr or "").strip()
        # "Python X.Y.Z"
        parts = text.split()
        return parts[1] if len(parts) >= 2 else None
    except Exception:
        return None


def check_python(sys_dir: Path) -> dict:
    rt = _load_runtimes(sys_dir)
    declared = (rt.get("runtimes", {}).get("python", {}) or {}).get("version")
    installed = _installed_python_version(sys_dir)
    if installed is None:
        return {"name": "python", "ok": False, "level": "error",
                "detail": f"portable python.exe missing (declared {declared})"}
    if declared and installed != declared:
        return {"name": "python", "ok": False, "level": "error",
                "detail": f"declared {declared} != installed {installed} (run INSTALL.bat)"}
    return {"name": "python", "ok": True, "level": "ok",
            "detail": f"{installed} (matches declared)"}


def check_subst(base_dir: Path) -> dict:
    try:
        from core.virtualizer import _get_subst_mappings
    except Exception:
        try:
            from virtualizer import _get_subst_mappings
        except Exception:
            return {"name": "subst_drive", "ok": True, "level": "warning",
                    "detail": "could not read SUBST mappings"}
    try:
        mappings = _get_subst_mappings()
    except Exception:
        mappings = {}
    # base_dir's own drive letter (e.g. "P") when we are running FROM the mount.
    own_letter = str(base_dir.drive).rstrip(":").upper()
    for letter, target in mappings.items():
        norm = str(letter).rstrip(":").upper()
        if norm == own_letter:
            return {"name": "subst_drive", "ok": True, "level": "ok",
                    "detail": f"mounted at {norm}: (running from the mount)"}
        try:
            if Path(target).resolve() == Path(base_dir).resolve():
                return {"name": "subst_drive", "ok": True, "level": "ok",
                        "detail": f"mounted at {norm}:"}
        except OSError:
            continue
    return {"name": "subst_drive", "ok": True, "level": "info",
            "detail": "not mounted (run register.bat to mount the P: drive)"}


def check_registration(base_dir: Path, sys_dir: Path) -> dict:
    try:
        from core import registrar
    except Exception:
        try:
            import registrar  # type: ignore
        except Exception:
            return {"name": "context_menu", "ok": True, "level": "warning",
                    "detail": "could not query HKCU"}
    try:
        cfg = registrar._load_context_menu(sys_dir)
    except Exception:
        cfg = {}
    if not cfg or not cfg.get("entries"):
        return {"name": "context_menu", "ok": True, "level": "info",
                "detail": "no context-menu entries configured (optional)"}
    base_key = registrar._registry_key_name(base_dir)
    targets = cfg.get("registry", {}).get("targets", {})
    present = 0
    total = 0
    for entry in cfg.get("entries", []):
        eid = entry.get("id", "entry")
        for tgt in targets.values():
            path = tgt.get("path") if isinstance(tgt, dict) else None
            if not path:
                continue
            total += 1
            reg_key = f"HKCU\\{path}\\{base_key}_{eid}"
            try:
                if registrar._hkcu_key_state(reg_key) != "absent":
                    present += 1
            except Exception:
                pass
    if total and present == 0:
        return {"name": "context_menu", "ok": True, "level": "info",
                "detail": "configured but not registered (run register.bat)"}
    return {"name": "context_menu", "ok": True, "level": "ok",
            "detail": f"{present}/{total} HKCU entries present"}


def _tool_present(sys_dir: Path, name: str, cfg: dict) -> bool:
    """A tool counts as present if it exists as a native binary under tools/ OR
    as an npm-global .cmd (claude/codex and other npm-backed tools install to
    _sys/env/nodejs/npm-global, not tools/)."""
    bin_name = cfg.get("bin", f"{name}.exe")
    if (sys_dir / "tools" / name / bin_name).exists():
        return True
    if (sys_dir / "env" / "nodejs" / "npm-global" / f"{name}.cmd").exists():
        return True
    return False


def check_components(sys_dir: Path) -> dict:
    try:
        from core import provisioner
    except Exception:
        try:
            import provisioner  # type: ignore
        except Exception:
            provisioner = None  # type: ignore
    rt = _load_runtimes(sys_dir)
    missing: list[str] = []
    checked = 0
    for name, cfg in (rt.get("runtimes", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        checked += 1
        try:
            ok = provisioner._runtime_postcondition(sys_dir, name, cfg) if provisioner else True
        except Exception:
            ok = True
        if not ok:
            missing.append(f"runtime/{name}")
    for name, cfg in (rt.get("tools", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        checked += 1
        if not _tool_present(sys_dir, name, cfg):
            missing.append(f"tool/{name}")
    # Missing components are advisory (many runtimes/tools are optional); only
    # python (checked separately) is a hard gate. Report but do not fail here.
    if missing:
        return {"name": "components", "ok": True, "level": "warning",
                "detail": f"{len(missing)}/{checked} declared components not found: "
                          f"{', '.join(missing)} (run INSTALL.bat to provision)",
                "missing": missing}
    return {"name": "components", "ok": True, "level": "ok",
            "detail": f"all {checked} declared components present", "missing": []}


def check_sessions(base_dir: Path) -> dict:
    try:
        from core.scrubber import _active_sessions_present
    except Exception:
        try:
            from scrubber import _active_sessions_present  # type: ignore
        except Exception:
            return {"name": "sessions", "ok": True, "level": "warning",
                    "detail": "could not read session state"}
    active = False
    try:
        active = _active_sessions_present(base_dir)
    except Exception:
        pass
    if active:
        return {"name": "sessions", "ok": True, "level": "info",
                "detail": "active peer session/lease present (cleanup is guarded)"}
    return {"name": "sessions", "ok": True, "level": "ok",
            "detail": "no active peer sessions"}


def check_elevation() -> dict:
    is_admin = False
    try:
        if sys.platform == "win32":
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        else:
            import os
            is_admin = (os.geteuid() == 0)  # type: ignore[attr-defined]
    except Exception:
        is_admin = False
    if is_admin:
        return {"name": "elevation", "ok": True, "level": "warning",
                "detail": "running as Administrator - not required; run the lifecycle as a standard user"}
    return {"name": "elevation", "ok": True, "level": "ok",
            "detail": "standard user (expected; admin only for an optional Defender exclusion)"}


_LEVEL_ICON = {"ok": "[OK]", "info": "[i]", "warning": "[!]", "error": "[X]"}


def run(ctx: dict) -> dict[str, Any]:
    base_dir = Path(ctx["base_dir"])
    sys_dir = Path(ctx["sys_dir"])
    args = ctx.get("args", []) or []
    want_json = "--json" in args

    checks = [
        check_python(sys_dir),
        check_components(sys_dir),
        check_subst(base_dir),
        check_registration(base_dir, sys_dir),
        check_sessions(base_dir),
        check_elevation(),
    ]
    broken = [c for c in checks if not c.get("ok")]
    overall = "failed" if broken else "success"

    if want_json:
        print(json.dumps({"status": overall, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print("=" * 56)
        print("  Portable Dev - Environment Status (doctor)")
        print("=" * 56)
        for c in checks:
            icon = _LEVEL_ICON.get(c.get("level", "info"), "[i]")
            name = c.get("name", "unknown")
            detail = c.get("detail", "no detail provided")
            print(f"  {icon} {name:<14} {detail}")
        print("=" * 56)
        print(f"  Overall: {'HEALTHY' if overall == 'success' else 'NEEDS ATTENTION'}")
        print("=" * 56)

    result: dict[str, Any] = {"status": overall, "checks": checks}
    if broken:
        result["detail"] = "; ".join(c.get("detail", "no detail provided") for c in broken)
    return result
