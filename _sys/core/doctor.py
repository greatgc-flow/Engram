"""doctor.py - zero-network lifecycle health check (T32).

Reports whether the portable environment is installed, registered, consistent,
and free of active sessions - the "am I healthy right now?" one-shot the
install/update/cleanup lifecycle was missing. Read-only: it mutates nothing and
performs NO network calls (version discovery is UPDATE's job, not status's).

Usage (via dispatch 'doctor' pipeline / engram.cmd):
    engram doctor            human-readable report
    engram doctor --json     machine-readable JSON

Exit/return: run(ctx) returns a dict whose "status" is "failed" ONLY on a
genuinely broken install (portable python missing, or declared python version
!= on-disk, or a required runtime absent). Informational states - not
registered, not mounted, standard-user elevation - are "success"; they are
reported, not failures.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from core import cli_help, env_lock, env_manifest, env_ops, provisioner, state_paths, venv_manager

try:  # registrar needs winreg (Windows); keep doctor importable elsewhere
    from core import registrar
except Exception:  # pragma: no cover
    registrar = None  # type: ignore[assignment]


def _load_runtimes(sys_dir: Path) -> dict:
    return provisioner.load_json_with_fallback(provisioner.resolve_declared_config(sys_dir, "runtimes.json"))


def _installed_python_version(sys_dir: Path) -> str | None:
    py = provisioner.portable_python_exe(sys_dir)
    if not py.exists():
        return None
    try:
        out = subprocess.run([str(py), "--version"], capture_output=True, encoding="utf-8", errors="replace", timeout=15)
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
                "detail": f"declared {declared} != installed {installed} (run 'engram' or 'engram update')"}
    return {"name": "python", "ok": True, "level": "ok",
            "detail": f"{installed} (matches declared)"}


def check_legacy_host_integration(base_dir: Path, sys_dir: Path) -> dict:
    """Check for legacy SUBST or directory junction records in this install only."""
    state_file = state_paths.register_state(sys_dir)
    legacy_cfg = sys_dir / "config.json"
    
    subst_drive = None # legacy-detect
    junctions = [] # legacy-detect
    subst_letter = None # legacy-detect

    data = provisioner.load_json_with_fallback(state_file)
    subst_drive = data.get("subst_drive") # legacy-detect
    junctions = data.get("junctions", []) # legacy-detect

    cfg_data = provisioner.load_json_with_fallback(legacy_cfg)
    subst_letter = cfg_data.get("SUBST_DRIVE_LETTER") # legacy-detect

    has_legacy = bool(subst_drive or junctions or subst_letter)
    if has_legacy:
        drive_name = subst_drive or subst_letter or "X"
        instructions = [
            f"Run: subst {drive_name}: /D (first run 'subst' and confirm '{drive_name}:\\: => {base_dir}')", # legacy-detect
        ]
        if junctions:
            for j in junctions:
                host = j.get("host") if isinstance(j, dict) else str(j)
                instructions.append(f'Run: rmdir "{host}"')
        instructions.append(f"Delete 'subst_drive' and 'junctions' entries from {state_file}") # legacy-detect
        detail = "legacy host integration recorded. Instructions:\n    " + "\n    ".join(instructions)
        return {
            "name": "legacy_host_integration",
            "ok": True,
            "level": "warning",
            "detail": detail,
        }

    return {
        "name": "legacy_host_integration",
        "ok": True,
        "level": "ok",
        "detail": "clean (no legacy SUBST or junctions recorded)",
    }


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
                "detail": "configured but not registered (run 'engram menu enable')"}
    if total and present == total:
        return {"name": "context_menu", "ok": True, "level": "ok",
                "detail": f"{present}/{total} HKCU entries present (active — run 'engram menu disable' to remove)"}
    return {"name": "context_menu", "ok": True, "level": "warning",
            "detail": f"{present}/{total} HKCU entries present (partial — run 'engram menu enable' to repair or 'engram menu disable' to remove)"}


def _tool_present(sys_dir: Path, name: str, cfg: dict) -> bool:
    """A tool counts as present if it exists as a native binary under tools/,
    or as an npm-global .cmd (claude/codex and other npm-backed tools install
    to _sys/env/nodejs/npm-global, not tools/)."""
    bin_name = cfg.get("bin", f"{name}.exe")
    if (sys_dir / "tools" / name / bin_name).exists():
        return True
    if (provisioner.npm_global_dir(sys_dir) / f"{name}.cmd").exists():
        return True
    return False


def _load_tool_catalog(sys_dir: Path) -> dict:
    return provisioner.load_json_with_fallback(provisioner.resolve_declared_config(sys_dir, provisioner.TOOL_CATALOG_FILENAME))


def check_components(sys_dir: Path) -> dict:
    rt = _load_runtimes(sys_dir)
    missing: list[str] = []
    checked = 0
    for name, cfg in (rt.get("runtimes", {}) or {}).items():
        if not isinstance(cfg, dict):
            continue
        checked += 1
        try:
            ok = provisioner._runtime_postcondition(sys_dir, name, cfg)
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

    observed_versions: dict[str, str] = {}
    catalog = _load_tool_catalog(sys_dir)
    for tool in catalog.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tool_id = tool.get("tool_id")
        if not tool_id or tool_id in rt.get("tools", {}):
            continue
        checked += 1
        bin_name = tool.get("install", {}).get("bin", f"{tool_id}.exe")
        npm_global = provisioner.npm_global_dir(sys_dir)
        manifest_path = sys_dir / "tools" / tool_id / ".install_manifest.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                obs = m.get("observed_version")
                if obs:
                    observed_versions[tool_id] = obs
            except Exception:
                pass
        present = (
            (sys_dir / "tools" / tool_id / bin_name).exists()
            or (npm_global / f"{tool_id}.cmd").exists()
        )
        if not present:
            missing.append(f"tool/{tool_id}")

    obs_notes = []
    for tid, obs_ver in observed_versions.items():
        tool_entry = next((t for t in catalog.get("tools", []) if isinstance(t, dict) and t.get("tool_id") == tid), None)
        decl_ver = tool_entry.get("version") if tool_entry else None
        if decl_ver and obs_ver != decl_ver:
            obs_notes.append(f"{tid}: active {obs_ver}")

    # Missing components are advisory (many runtimes/tools are optional); only
    # python (checked separately) is a hard gate. Report but do not fail here.
    note_str = f" ({', '.join(obs_notes)})" if obs_notes else ""
    if missing:
        return {"name": "components", "ok": True, "level": "warning",
                "detail": f"{len(missing)}/{checked} declared components not found: "
                          f"{', '.join(missing)}{note_str} (run 'engram update' to provision)",
                "missing": missing,
                "observed_versions": observed_versions}
    return {"name": "components", "ok": True, "level": "ok",
            "detail": f"all {checked} declared components present{note_str}",
            "missing": [],
            "observed_versions": observed_versions}



_PATH_SPECIAL_CHAR_CHECKS: tuple[tuple[str, str], ...] = (
    ("&", "contains '&' (breaks cmd.exe argument parsing and Node.js npm-global wrappers)"),
    ("%", "contains '%' (interferes with batch variable expansion)"),
    ("^", "contains '^' (cmd.exe escape character)"),
    (
        "!",
        "contains '!' (silently stripped under delayed expansion -- "
        "cd/pushd fails with NO error and the script keeps running in "
        "the wrong directory; see CONVENTION.md section 2.6)",
    ),
)


def check_root_path(base_dir: Path) -> dict:
    """Validate that base_dir does not contain problematic characters for Windows CLI/Node."""
    path_str = str(base_dir)
    issues = [desc for char, desc in _PATH_SPECIAL_CHAR_CHECKS if char in path_str]

    if issues:
        detail = (
            f"root path '{path_str}' has issues: {'; '.join(issues)}. "
            f"Action: move Engram to a clean path without special characters (e.g. C:\\Engram or D:\\PortableDev)"
        )
        return {
            "name": "root_path",
            "ok": True,
            "level": "warning",
            "detail": detail,
            "issues": issues,
        }
    return {
        "name": "root_path",
        "ok": True,
        "level": "ok",
        "detail": f"clean path ({path_str})",
    }


# ---- environment-resilience checks (read-only) ----------------------------------------
# Design: docs/design/engram-env-resilience-design-2026-10-02.md, section 5.
# None of these may mutate anything. Overall status is "failed" only for the hard gates:
# python_pin and a venv that does not run (any venv_* finding with level "error").
# Everything else (manifest, root drift, stale registry, lock) is warning/info only.

_DESIGN_DOC = "docs/design/engram-env-resilience-design-2026-10-02.md"


def check_venv(sys_dir: Path) -> list[dict]:
    """Read-only venv health/skew/integrity/launcher findings (see core.venv_manager)."""
    manifest = env_manifest.read_manifest(sys_dir)
    try:
        return venv_manager.run_checks(sys_dir, manifest=manifest.data if manifest.status == "ok" else None)
    except Exception as exc:  # a probe bug must never break doctor
        return [{"name": "venv_health", "ok": True, "level": "info", "detail": f"venv probes unavailable ({exc})"}]


def check_env_manifest(sys_dir: Path) -> dict:
    res = env_manifest.read_manifest(sys_dir)
    if res.status == "ok":
        return {"name": "env_manifest", "ok": True, "level": "ok",
                "detail": "environment manifest present and readable"}
    if res.status == "absent":
        return {"name": "env_manifest", "ok": True, "level": "info",
                "detail": "no environment manifest yet (adoptable; written by a fresh install "
                          "or a future 'engram repair')"}
    return {"name": "env_manifest", "ok": True, "level": "warning",
            "detail": f"environment manifest is {res.status} ({res.detail}); it will not be trusted"}


def check_root_moved(base_dir: Path, sys_dir: Path) -> dict:
    manifest = env_manifest.read_manifest(sys_dir)
    local = os.environ.get("LOCALAPPDATA")
    drift = env_manifest.detect_root_drift(
        manifest.data if manifest.status == "ok" else None,
        Path(base_dir), Path(sys_dir),
        localappdata=Path(local) if local else None,
    )
    if drift.status == "consistent":
        return {"name": "root_moved", "ok": True, "level": "ok",
                "detail": f"install root unchanged ({base_dir})"}
    if drift.status == "unknown":
        return {"name": "root_moved", "ok": True, "level": "info",
                "detail": "no record of a previous install root"}
    what = "moved" if drift.status == "moved" else "looks like a copy (the old root still exists)"
    return {
        "name": "root_moved", "ok": True, "level": "warning",
        "detail": (
            f"install {what}: previously {drift.previous_root} (evidence: {drift.source}). "
            f"Console scripts (e.g. pip.exe) and context-menu entries may be stale. "
            f"Run 'engram relocate' (dry run) to preview the fix, then 'engram relocate --apply'."
        ),
        "previous_root": drift.previous_root,
        "drift": drift.status,
    }


def check_registry_stale(sys_dir: Path) -> dict:
    if registrar is None:
        return {"name": "registry_stale", "ok": True, "level": "info",
                "detail": "registry module unavailable on this platform"}
    try:
        stale = registrar.find_stale_entries(sys_dir)
    except Exception as exc:
        return {"name": "registry_stale", "ok": True, "level": "info",
                "detail": f"could not scan the registry ({exc})"}
    if not stale:
        return {"name": "registry_stale", "ok": True, "level": "ok",
                "detail": "no stale context-menu entries"}
    return {"name": "registry_stale", "ok": True, "level": "warning",
            "detail": f"{len(stale)} stale context-menu entr{'y' if len(stale) == 1 else 'ies'}: "
                      f"{', '.join(stale)}. Run 'engram menu clean'."}


def check_env_journal(sys_dir: Path) -> dict:
    """A non-terminal env-op journal blocks every mutating verb (design section 9)."""
    try:
        active = env_ops.journal_blocks(sys_dir)
    except Exception as exc:  # an unreadable journal is itself a finding, never a crash
        return {"name": "env_journal", "ok": False, "level": "error",
                "detail": f"environment journal is unreadable ({exc}); do not delete it, run 'engram repair --rollback'"}
    if not active:
        return {"name": "env_journal", "ok": True, "level": "ok", "detail": "no interrupted environment operation"}
    return {"name": "env_journal", "ok": False, "level": "error",
            "detail": (f"environment operation {active.get('op_id')!r} was interrupted in phase {active.get('phase')}. "
                       f"Run 'engram repair --resume' to continue it or 'engram repair --rollback' to undo it.")}


def check_env_lock(sys_dir: Path) -> dict:
    info = env_lock.inspect(sys_dir)
    if info["state"] == "free":
        return {"name": "env_lock", "ok": True, "level": "ok", "detail": "no environment operation in progress"}
    owner = info.get("owner") or {}
    if info["state"] == "held":
        return {"name": "env_lock", "ok": True, "level": "info",
                "detail": f"environment operation in progress: {owner.get('op_id')} (pid {owner.get('pid')})"}
    return {"name": "env_lock", "ok": True, "level": "warning",
            "detail": f"stale environment lock left by op {owner.get('op_id')!r}; "
                      f"the next mutating operation will break it safely"}


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
    args = ctx.get("args", []) or []
    if cli_help.wants_help(args):
        cli_help.print_verb_help("doctor")
        return {"status": "success", "detail": "help displayed"}
    for a in args:
        if a != "--json":
            if a.startswith("-"):
                try:
                    cli_help.unknown_option("doctor", a)
                except SystemExit:
                    pass
            else:
                try:
                    cli_help.unexpected_argument("doctor", a)
                except SystemExit:
                    pass
            return {"status": "failed", "detail": "usage", "exit_code": 2, "quiet": True}

    base_dir = Path(ctx["base_dir"])
    sys_dir = Path(ctx["sys_dir"])
    want_json = "--json" in args

    checks = [
        check_root_path(base_dir),
        check_python(sys_dir),
        check_components(sys_dir),
        check_legacy_host_integration(base_dir, sys_dir),
        check_registration(base_dir, sys_dir),
        *check_venv(sys_dir),
        check_env_manifest(sys_dir),
        check_root_moved(base_dir, sys_dir),
        check_registry_stale(sys_dir),
        check_env_lock(sys_dir),
        check_env_journal(sys_dir),
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
