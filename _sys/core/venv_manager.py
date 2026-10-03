"""venv_manager.py - read-only venv health probes and package snapshots (design P1).

Design: docs/design/engram-env-resilience-design-2026-10-02.md, sections 5.1 and 7.1-7.2.
P1 is strictly read-only with respect to the environment: the only file written is a
plain snapshot under data/state/venv-freeze/. First drafted by the ag peer, reviewed and
corrected by cc against a real install (spikes S-1..S-14).
"""
import hashlib
import json
import ntpath
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core import backups, env_lock
from core.env_manifest import _atomic_write_text

Runner = Callable[[list[str], float], tuple[int, str]]

# Importable MODULE names of the baseline packages (pywinpty is the distribution; its module is winpty).
BASELINE_MODULES = ("filelock", "psutil", "pydantic", "winpty")


def default_runner(argv: list[str], timeout_s: float) -> tuple[int, str]:
    try:
        res = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout_s)
        return res.returncode, res.stdout + res.stderr
    except OSError as exc:
        return -1, str(exc)
    except subprocess.TimeoutExpired:
        return -1, "TimeoutExpired"


@dataclass
class Finding:
    name: str
    level: str
    detail: str

    def to_check(self) -> dict:
        return {
            "name": self.name,
            "ok": self.level != "error",
            "level": self.level,
            "detail": self.detail or "ok",
        }


# An absolute Windows path: drive letter (either slash style) or a UNC share.
_ABS_PREFIX = rb'(?:[A-Za-z]:[\\/]|\\\\[^\\/\r\n"\x00]+[\\/])'
_LAUNCHER_SHEBANG = rb'#!"?(' + _ABS_PREFIX + rb'[^\r\n"\x00]+?\.exe)'
_LAUNCHER_FALLBACK = rb'(' + _ABS_PREFIX + rb'[^\r\n"\x00]+?pythonw?\.exe)'


def launcher_embedded_path(exe_path: Path) -> str | None:
    try:
        content = Path(exe_path).read_bytes()
        # pip-style launchers append `#!<absolute path to python.exe>`
        m = list(re.finditer(_LAUNCHER_SHEBANG, content))
        if m:
            return m[-1].group(1).decode("utf-8")
        
        # fallback: last drive-letter path ending in python.exe/pythonw.exe
        m2 = list(re.finditer(_LAUNCHER_FALLBACK, content))
        if m2:
            return m2[-1].group(1).decode("utf-8")
        return None
    except OSError:
        return None


def interpreter_file_set(venv_dir: Path) -> list[Path]:
    venv_dir = Path(venv_dir)
    scripts = venv_dir / "Scripts"
    candidates = [venv_dir / "pyvenv.cfg", scripts / "python.exe", scripts / "pythonw.exe"]
    if scripts.exists():
        for f in scripts.iterdir():
            if not f.is_file():
                continue
            name = f.name.lower()
            if (name.startswith("python3") and name.endswith(".dll")) or \
               (name.startswith("python") and name.endswith(".zip")) or \
               name.endswith(".pyd") or \
               name.endswith(".dll"):
                if f not in candidates:
                    candidates.append(f)
    
    res = [f.relative_to(venv_dir) for f in candidates if f.exists()]
    return sorted(res)


def hash_files(venv_dir: Path, files: list[Path]) -> dict[str, str]:
    venv_dir = Path(venv_dir)
    res = {}
    for f in files:
        full_path = venv_dir / f
        if not full_path.exists():
            continue
        h = hashlib.sha256()
        try:
            with open(full_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            res[f.as_posix()] = h.hexdigest()
        except OSError:
            pass
    return res


def _norm(p: str | Path) -> str:
    return ntpath.normcase(ntpath.normpath(str(p)))


def _pip_check(python_exe: Path, runner: Runner) -> Finding:
    """``pip check`` (design 5.1 step 8): informational - dependency problems never fail doctor."""
    rc, out = runner([str(python_exe), "-m", "pip", "check"], 60.0)
    if rc == 0:
        return Finding("pip_check", "ok", "no broken requirements")
    if "No module named pip" in out:
        return Finding("pip_check", "info", "pip is not installed in the venv")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return Finding("pip_check", "warning", "; ".join(lines[:3]) or "pip check reported problems")


def probe_venv(
    sys_dir: Path,
    *,
    runner: Runner = default_runner,
    manifest: Optional[dict] = None,
    path_exists: Callable[[str], bool] = os.path.exists,
    is_file: Callable[[str], bool] = os.path.isfile
) -> list[Finding]:
    sys_dir = Path(sys_dir)
    venv_dir = sys_dir / "env" / "venv"
    python_exe = venv_dir / "Scripts" / "python.exe"
    
    findings = []
    
    interpreter_runs = False
    venv_ver = None
    venv_prefix = None
    
    if not path_exists(str(venv_dir)):
        findings.append(Finding("venv_interpreter", "info", "venv not present"))
    elif not is_file(str(python_exe)):
        findings.append(Finding("venv_interpreter", "error", "venv interpreter does not run"))
    else:
        cmd = [
            str(python_exe),
            "-c",
            "import sys,json;print(json.dumps([list(sys.version_info[:3]),sys.prefix]))"
        ]
        rc, out = runner(cmd, 10.0)
        try:
            if rc != 0:
                raise ValueError("rc != 0")
            parsed = json.loads(out)
            venv_ver = f"{parsed[0][0]}.{parsed[0][1]}.{parsed[0][2]}"
            venv_prefix = parsed[1]
            findings.append(Finding("venv_interpreter", "ok", ""))
            interpreter_runs = True
        except Exception:
            findings.append(Finding("venv_interpreter", "error", "venv interpreter does not run"))
            
    if interpreter_runs:
        if venv_prefix and _norm(venv_prefix) != _norm(venv_dir):
            findings.append(Finding("venv_prefix", "warning", f"prefix mismatch: {venv_prefix} != {venv_dir}"))
        else:
            findings.append(Finding("venv_prefix", "ok", ""))
            
        cmd_spawn = [
            str(python_exe),
            "-c",
            "from concurrent.futures import ProcessPoolExecutor; ProcessPoolExecutor(1).submit(id, 1).result()"
        ]
        rc, out = runner(cmd_spawn, 15.0)
        if rc != 0:
            findings.append(Finding("venv_spawn", "error", "pyvenv.cfg home may not resolve (spike S-12)"))
        else:
            findings.append(Finding("venv_spawn", "ok", ""))
            
        cmd_imports = [
            str(python_exe),
            "-c",
            "import json,importlib.util; "
            f"print(json.dumps([m for m in {list(BASELINE_MODULES)!r} if importlib.util.find_spec(m) is None]))",
        ]
        rc, out = runner(cmd_imports, 10.0)
        try:
            missing = json.loads(out)
            if missing:
                findings.append(Finding("venv_imports", "warning", f"missing baseline packages: {', '.join(missing)}"))
            else:
                findings.append(Finding("venv_imports", "ok", ""))
        except Exception:
            findings.append(Finding("venv_imports", "warning", "failed to probe imports"))
        findings.append(_pip_check(python_exe, runner))
    else:
        for name in ["venv_prefix", "venv_spawn", "venv_imports", "pip_check"]:
            findings.append(Finding(name, "info", "skipped: interpreter does not run"))

    if not path_exists(str(venv_dir)):
        for name in ("pyvenv_home", "venv_interpreter_skew", "interpreter_integrity", "console_scripts"):
            findings.append(Finding(name, "info", "skipped: venv not present"))
        return findings

    cfg_path = venv_dir / "pyvenv.cfg"
    home = None
    if is_file(str(cfg_path)):
        try:
            content = Path(cfg_path).read_text(encoding="utf-8", errors="replace")
            m = re.search(r"(?m)^home\s*=\s*(.+)$", content)
            if m:
                home = m.group(1).strip()
            if not venv_ver:
                m_ver = re.search(r"(?m)^version\s*=\s*(\d+\.\d+\.\d+)", content)
                if m_ver:
                    venv_ver = m_ver.group(1)
        except OSError:
            pass
            
    managed_python_dir = sys_dir / "env" / "python"
    
    if not home or not path_exists(home) or not is_file(str(Path(home) / "python.exe")):
        findings.append(Finding("pyvenv_home", "error", "pyvenv.cfg home does not resolve (repair trigger, S-12)"))
    else:
        if _norm(home) != _norm(managed_python_dir):
            findings.append(Finding("pyvenv_home", "info", "skew"))
        else:
            findings.append(Finding("pyvenv_home", "ok", ""))

    managed_ver = None
    managed_python_exe = managed_python_dir / "python.exe"
    if not is_file(str(managed_python_exe)):
        findings.append(Finding("venv_interpreter_skew", "info", "managed python missing"))
    else:
        rc, out = runner([str(managed_python_exe), "--version"], 10.0)
        if rc == 0:
            m = re.search(r"(\d+\.\d+\.\d+)", out)
            if m:
                managed_ver = m.group(1)
                
        if not managed_ver:
            findings.append(Finding("venv_interpreter_skew", "info", "managed python missing"))
        elif not venv_ver:
            findings.append(Finding("venv_interpreter_skew", "info", "venv version unknown"))
        else:
            v1 = managed_ver.split(".")
            v2 = venv_ver.split(".")
            if v1[:2] != v2[:2]:
                findings.append(Finding("venv_interpreter_skew", "warning", "minor-skew"))
            elif v1 != v2:
                findings.append(Finding("venv_interpreter_skew", "warning", "patch-skew"))
            else:
                findings.append(Finding("venv_interpreter_skew", "ok", ""))

    if manifest and "venv" in manifest and "interpreter_hashes" in manifest["venv"]:
        expected = manifest["venv"]["interpreter_hashes"]
        actual = hash_files(venv_dir, interpreter_file_set(venv_dir))
        mismatches = []
        for p, h in expected.items():
            if actual.get(p) != h:
                mismatches.append(p)
        for p in actual:
            if p not in expected:
                mismatches.append(p)
        if mismatches:
            findings.append(Finding("interpreter_integrity", "warning", f"mismatches: {', '.join(sorted(mismatches))}"))
        else:
            findings.append(Finding("interpreter_integrity", "ok", ""))
    else:
        findings.append(Finding("interpreter_integrity", "info", "no baseline recorded"))

    scripts_dir = venv_dir / "Scripts"
    stale = []
    native_exes = 0
    if path_exists(str(scripts_dir)):
        for f in Path(scripts_dir).iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() == ".exe" and not f.name.lower().startswith("python"):
                emb = launcher_embedded_path(f)
                if emb is None:
                    native_exes += 1
                elif _norm(emb) != _norm(python_exe) and _norm(emb) != _norm(venv_dir / "Scripts" / "pythonw.exe"):
                    stale.append(f.name)
    if stale:
        findings.append(Finding("console_scripts", "warning", f"stale-launchers: {', '.join(sorted(stale))}"))
    else:
        detail = ""
        if native_exes > 0:
            detail = f"{native_exes} native executable{'s' if native_exes > 1 else ''} ignored"
        findings.append(Finding("console_scripts", "ok", detail))
        
    return findings


def sanitize_url(url: str) -> str:
    if not isinstance(url, str):
        return str(url)
    try:
        url = re.sub(r"(?i)(://)[^/@]+@", r"\1", url)
        if "?" in url:
            base, query = url.split("?", 1)
            # \b does not match after an underscore (access_token, api_key), so test parameter
            # NAMES by substring instead of the whole query by word boundary.
            names = [part.split("=", 1)[0] for part in re.split(r"[&;]", query)]
            if any(re.search(r"(?i)(token|key|password|passwd|secret|signature|credential|auth)", n) for n in names):
                url = base
    except Exception:
        pass
    return url


def scan_installed_packages(site_packages: Path) -> list[dict]:
    site_packages = Path(site_packages)
    packages = []
    if not site_packages.exists():
        return packages
        
    for d in site_packages.iterdir():
        if d.is_dir() and d.name.endswith(".dist-info"):
            metadata_file = d / "METADATA"
            if not metadata_file.exists():
                continue
                
            pkg = {"name": "", "version": "", "requested": False, "editable": False}
            
            try:
                content = metadata_file.read_text(encoding="utf-8", errors="replace")
                m_name = re.search(r"(?im)^Name:\s*(.+)$", content)
                m_ver = re.search(r"(?im)^Version:\s*(.+)$", content)
                if m_name: pkg["name"] = m_name.group(1).strip()
                if m_ver: pkg["version"] = m_ver.group(1).strip()
            except OSError:
                pass
                
            if (d / "REQUESTED").exists():
                pkg["requested"] = True
                
            direct_url_file = d / "direct_url.json"
            if direct_url_file.exists():
                try:
                    direct_url = json.loads(direct_url_file.read_text(encoding="utf-8"))
                    if direct_url.get("dir_info", {}).get("editable"):
                        pkg["editable"] = True
                        if "url" in direct_url:
                            pkg["editable_url"] = sanitize_url(direct_url["url"])
                except Exception:
                    pass
                    
            installer_file = d / "INSTALLER"
            if installer_file.exists():
                try:
                    pkg["installer"] = installer_file.read_text(encoding="utf-8", errors="replace").strip()
                except OSError:
                    pass
                    
            if pkg["name"]:
                packages.append(pkg)
                
    packages.sort(key=lambda x: x["name"].lower())
    return packages


def build_snapshot(sys_dir: Path, *, now: str, python_version: Optional[str] = None) -> dict:
    sys_dir = Path(sys_dir)
    site_packages = sys_dir / "env" / "venv" / "Lib" / "site-packages"
    skipped = []
    
    packages = []
    if site_packages.exists():
        for d in site_packages.iterdir():
            if d.is_dir() and d.name.endswith(".dist-info") and not (d / "METADATA").exists():
                skipped.append(d.name)
        packages = scan_installed_packages(site_packages)
        
    venv_dir = sys_dir / "env" / "venv"
    hashes = hash_files(venv_dir, interpreter_file_set(venv_dir))
    
    return {
        "schema_version": 1,
        "created_at": now,
        "source": "metadata-scan",
        "python_version": python_version,
        "packages": packages,
        "skipped": sorted(skipped),
        "interpreter_hashes": hashes
    }


SNAPSHOT_KIND = "venv-freeze"
SNAPSHOT_FILENAME = "snapshot.json"
_LEGACY_SNAPSHOT_DIR = ("data", "state", "venv-freeze")  # P1 plain files; still read as a fallback


def write_snapshot(sys_dir: Path, snapshot: dict, *, replace=os.replace, sleep=time.sleep) -> Path:
    """Record a package snapshot as a committed ``venv-freeze`` registry entry (design 8.1)."""
    ref = backups.create_text(
        Path(sys_dir), SNAPSHOT_KIND, SNAPSHOT_FILENAME,
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        reason="venv package snapshot", op_id="venv-snapshot", label="venv-packages",
        now=snapshot["created_at"], replace=replace, sleep=sleep,
    )
    return ref.path / backups.PAYLOAD / SNAPSHOT_FILENAME


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def latest_snapshot(sys_dir: Path) -> dict | None:
    """Newest readable snapshot: registry first, then P1-era plain files."""
    registered = sorted(
        (r for r in backups.scan(Path(sys_dir)).valid if r.kind == SNAPSHOT_KIND and r.meta.get("state") == "committed"),
        key=lambda r: r.meta["created_at"], reverse=True,
    )
    for ref in registered:
        data = _read_json(ref.path / backups.PAYLOAD / SNAPSHOT_FILENAME)
        if data is not None:
            return data
    legacy_dir = Path(sys_dir).joinpath(*_LEGACY_SNAPSHOT_DIR)
    if legacy_dir.is_dir():
        for candidate in sorted(legacy_dir.glob("*.json"), reverse=True):
            data = _read_json(candidate)
            if data is not None:
                return data
    return None


def run_checks(sys_dir: Path, *, runner: Runner = default_runner, manifest: Optional[dict] = None) -> list[dict]:
    findings = probe_venv(sys_dir, runner=runner, manifest=manifest)
    return [f.to_check() for f in findings]


def _utc_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_fingerprint(snapshot: dict) -> str:
    """What makes two snapshots 'the same': installed packages + interpreter hashes."""
    core = {"packages": snapshot.get("packages"), "interpreter_hashes": snapshot.get("interpreter_hashes")}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()


def snapshot_op(ctx: dict, *, now: Optional[str] = None) -> dict:
    """Pipeline operation ``venv.snapshot``: record the venv's package set after install/update.

    Idempotent (an unchanged venv writes nothing) and never fails the pipeline: a missing
    venv or a busy environment lock is reported as a skip. The write is serialized with
    every other environment mutator through ``env_lock``.
    """
    sys_dir = Path(ctx["sys_dir"])
    op = {"status": "success", "operation": "venv.snapshot"}
    if any(a in ("--dry-run", "--check") for a in (ctx.get("args") or [])):
        print("  [--] venv snapshot: skipped (dry-run/check)")
        return {**op, "skipped": True, "detail": "dry-run"}
    venv_dir = sys_dir / "env" / "venv"
    if not (venv_dir / "Scripts" / "python.exe").is_file():
        print("  [--] venv snapshot: no venv present")
        return {**op, "skipped": True, "detail": "no venv present"}
    stamp = now or _utc_now()
    try:
        with env_lock.guard(sys_dir, f"venv-snapshot-{stamp}"):
            snapshot = build_snapshot(sys_dir, now=stamp)
            previous = latest_snapshot(sys_dir)
            if previous is not None and _snapshot_fingerprint(previous) == _snapshot_fingerprint(snapshot):
                print("  [--] venv snapshot: unchanged since the last one")
                return {**op, "skipped": True, "detail": "unchanged"}
            path = write_snapshot(sys_dir, snapshot)
    except env_lock.EnvLockBusy as exc:
        print(f"  [!] venv snapshot skipped: environment lock busy ({exc})")
        return {**op, "skipped": True, "detail": f"environment lock busy: {exc}"}
    print(f"  [OK] venv snapshot recorded: {path.name} ({len(snapshot['packages'])} packages)")
    return {**op, "snapshot": str(path)}
