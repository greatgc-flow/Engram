import os
import re
import time
import json
import ntpath
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from core.env_ops import Step, OpContext
from core.venv_manager import sanitize_url, interpreter_file_set, hash_files, default_runner

Runner = Callable[[list[str], float], tuple[int, str]]

def _atomic_write_bytes(path: Path, content: bytes, *, replace=os.replace, sleep=time.sleep) -> None:
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        for attempt in range(5):
            try:
                replace(tmp, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                sleep(0.1 * (2 ** attempt))
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

def rewrite_pyvenv_cfg(venv_dir: Path, managed_python_dir: Path, *, python_version: str | None = None) -> bool:
    cfg_path = venv_dir / "pyvenv.cfg"
    if not cfg_path.exists():
        return False
        
    content = cfg_path.read_bytes()
    lines = content.splitlines(keepends=True)
    
    managed_str = str(managed_python_dir)
    managed_exe = str(managed_python_dir / "python.exe")
    
    changed = False
    new_lines = []
    
    for line in lines:
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            new_lines.append(line)
            continue
            
        m = re.match(r"^([a-zA-Z0-9_-]+)\s*=\s*(.*?)(\r?\n)$", text)
        if m:
            key, val, eol = m.groups()
            new_val = None
            
            if key == "home":
                new_val = managed_str
            elif key in ("executable", "base-executable"):
                new_val = managed_exe
            elif key in ("base-prefix", "base-exec-prefix"):
                new_val = managed_str
            elif python_version and key == "version":
                new_val = python_version
            elif python_version and key == "version_info":
                parts = python_version.split(".")
                if len(parts) >= 3:
                    new_val = f"{parts[0]}.{parts[1]}.{parts[2]}.final.0"
                else:
                    new_val = python_version
                    
            if new_val is not None and val != new_val:
                new_lines.append(f"{key} = {new_val}{eol}".encode("utf-8"))
                changed = True
                continue
                
        new_lines.append(line)
        
    if not changed:
        return False
        
    _atomic_write_bytes(cfg_path, b"".join(new_lines))
    return True

_REGENERATE_SCRIPT = """
import sys
import json
from pathlib import Path

try:
    from pip._vendor.distlib.scripts import ScriptMaker
except ImportError:
    print(json.dumps({"error": "distlib.scripts not found"}))
    sys.exit(0)

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "missing arguments"}))
        sys.exit(1)
        
    venv_dir = Path(sys.argv[1])
    target_python = sys.argv[2]
    
    scripts_dir = venv_dir / "Scripts"
    site_packages = venv_dir / "Lib" / "site-packages"
    
    maker = ScriptMaker(None, str(scripts_dir))
    maker.executable = target_python
    maker.clobber = True
    maker.variants = {""}
    
    regenerated = 0
    failed = []
    
    if not site_packages.exists():
        print(json.dumps({"regenerated": 0, "failed": []}))
        return

    for d in site_packages.iterdir():
        if d.is_dir() and d.name.endswith(".dist-info"):
            ep_file = d / "entry_points.txt"
            if not ep_file.exists():
                continue
                
            current_section = None
            for line in ep_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    continue
                
                if current_section in ("console_scripts", "gui_scripts"):
                    gui = (current_section == "gui_scripts")
                    name = line.split("=")[0].strip()
                    if name.lower().startswith("python"):
                        continue
                    try:
                        res = maker.make(line, options={"gui": gui})
                        if res:
                            regenerated += 1
                        else:
                            failed.append(name)
                    except Exception:
                        failed.append(name)

    print(json.dumps({"regenerated": regenerated, "failed": failed}))

if __name__ == "__main__":
    main()
"""

def regenerate_console_scripts(venv_dir: Path, *, python_exe: Path | None = None, runner: Runner = default_runner) -> dict:
    if python_exe is None:
        python_exe = venv_dir / "Scripts" / "python.exe"
        
    rc, out = runner([str(python_exe), "-c", _REGENERATE_SCRIPT, str(venv_dir), str(python_exe)], 60.0)
    if rc != 0:
        return {"regenerated": 0, "failed": [f"error: {out}"]}
        
    try:
        data = json.loads(out.strip())
    except Exception:
        return {"regenerated": 0, "failed": [f"parse error: {out}"]}
    if isinstance(data, dict) and "error" in data:
        # e.g. the venv has no pip (distlib): never report that as a silent success
        return {"regenerated": 0, "failed": [f"error: {data['error']}"]}
    return data

def rebase_path(path: str, old_root: str, new_root: str) -> str | None:
    path_norm = ntpath.normpath(path)
    old_norm = ntpath.normpath(old_root)
    
    path_lower = ntpath.normcase(path_norm)
    old_lower = ntpath.normcase(old_norm)
    
    if path_lower == old_lower:
        return ntpath.normpath(new_root)
        
    old_prefix = old_lower if old_lower.endswith("\\") else old_lower + "\\"
    
    if path_lower.startswith(old_prefix):
        try:
            rel = ntpath.relpath(path_norm, old_norm)
        except ValueError:
            return None
        return ntpath.normpath(ntpath.join(new_root, rel))
        
    return None

def restore_packages_step_data(snapshot: dict, *, wheelhouse: Path | None = None) -> dict:
    t1, t2, t3, skipped_editable, constraints = [], [], [], [], []
    rebase = snapshot.get("rebase")
    BASELINE_PACKAGES = {"filelock", "psutil", "pydantic", "pywinpty", "winpty"}
    
    for pkg in snapshot.get("packages", []):
        name = pkg.get("name", "")
        if not name:
            continue
            
        version = pkg.get("version", "")
        spec = f"{name}=={version}" if version else name
        
        if name.lower() in BASELINE_PACKAGES:
            t1.append(spec)
            continue
            
        if pkg.get("editable"):
            url = pkg.get("editable_url", "")
            if url:
                url = sanitize_url(url)
            if url.startswith("file://"):
                try:
                    path_str = urllib.request.url2pathname(url[7:] if not url.startswith("file:////") else url[8:])
                except Exception:
                    path_str = url[7:]
                
                if rebase and "from" in rebase and "to" in rebase:
                    rebased = rebase_path(path_str, rebase["from"], rebase["to"])
                    if rebased:
                        path_str = rebased
                        
                if os.path.exists(path_str):
                    t3.append(path_str)
                else:
                    skipped_editable.append(name)
            else:
                skipped_editable.append(name)
            continue
            
        if pkg.get("requested"):
            t2.append(spec)
            
        if version:
            constraints.append(f"{name}=={version}")
            
    return {
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "skipped_editable": skipped_editable,
        "constraints_text": "\n".join(constraints) + "\n" if constraints else ""
    }

def _commit_op_backups(ctx) -> None:
    """The rebuild/refresh verified: commit this operation's pending backups so they age out normally
    instead of staying ``pending`` (which retention never touches)."""
    from core import backups
    for ref in backups.scan(ctx.sys_dir).valid:
        if ref.meta.get("op_id") == ctx.op_id and ref.meta.get("state") == "pending":
            backups.commit(ref)


def plan_venv_repair(sys_dir: Path, findings: list, *, manifest: dict | None = None, runner: Runner = default_runner, allow_rebuild: bool = True) -> list:
    findings_by_name = {f["name"]: f for f in findings}
    
    rebuild = False
    if allow_rebuild:
        if findings_by_name.get("venv_interpreter", {}).get("level") == "error":
            rebuild = True
        elif findings_by_name.get("venv_spawn", {}).get("level") == "error":
            rebuild = True
        elif findings_by_name.get("venv_interpreter_skew", {}).get("detail") == "minor-skew":
            rebuild = True
            
    steps = []
    
    if rebuild:
        def do_quarantine(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            if not venv_dir.exists(): return
            dest = ctx.paths.get("venv_backup")
            if not dest:
                raise RuntimeError("missing venv_backup path allocation")
            from core import backups
            backups.create(ctx.sys_dir, "venv", venv_dir, reason="quarantine broken venv", op_id=ctx.op_id, label="broken-venv", dest=Path(dest))
            
        def undo_quarantine(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            from core import backups
            
            if venv_dir.exists():
                failed_dest = ctx.paths.get("venv_failed_backup")
                if not failed_dest:
                    raise RuntimeError("missing venv_failed_backup path allocation")
                backups.create(ctx.sys_dir, "venv", venv_dir, reason="rollback of failed rebuild", op_id=ctx.op_id, label="failed-rebuild", dest=Path(failed_dest))
                
            # Restore from the write-ahead path allocated for this op (never search by label: markers do not
            # store labels, and a marker-only dir from an interrupted move must not hide the real payload).
            dest = ctx.paths.get("venv_backup")
            if not dest:
                raise RuntimeError("missing venv_backup path allocation")
            meta = backups._read_meta(Path(dest))
            if meta and (Path(dest) / backups.PAYLOAD).exists() and not venv_dir.exists():
                backups.restore(backups.BackupRef(meta["kind"], Path(dest), meta))
            
        def do_create(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            managed_python = ctx.sys_dir / "env" / "python" / "python.exe"
            rc, out = runner([str(managed_python), "-m", "virtualenv", str(venv_dir)], 60.0)
            if rc != 0:
                raise RuntimeError(f"venv creation failed: {out}")
                
        def undo_create(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            if venv_dir.exists():
                failed_dest = ctx.paths.get("venv_failed_backup")
                if not failed_dest:
                    raise RuntimeError("missing venv_failed_backup path allocation")
                from core import backups
                backups.create(ctx.sys_dir, "venv", venv_dir, reason="rollback of failed rebuild", op_id=ctx.op_id, label="failed-rebuild", dest=Path(failed_dest))
                
        def do_restore(ctx):
            snapshot = ctx.data.get("snapshot")
            if not snapshot:
                from core.venv_manager import latest_snapshot
                snapshot = latest_snapshot(ctx.sys_dir) or {"packages": []}
            plan = restore_packages_step_data(snapshot)
            venv_python = ctx.sys_dir / "env" / "venv" / "Scripts" / "python.exe"
            
            if plan["t1"]:
                rc, out = runner([str(venv_python), "-m", "pip", "install"] + plan["t1"], 120.0)
                if rc != 0: raise RuntimeError(f"T1 baseline install failed: {out}")
                
            if plan["t2"]:
                import tempfile
                fd, c_path = tempfile.mkstemp(suffix=".txt", text=True)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(plan["constraints_text"])
                    rc, out = runner([str(venv_python), "-m", "pip", "install", "-c", c_path] + plan["t2"], 300.0)
                    if rc != 0:
                        for pkg in plan["t2"]:
                            runner([str(venv_python), "-m", "pip", "install", pkg], 60.0)
                finally:
                    os.remove(c_path)
                    
            for path in plan["t3"]:
                runner([str(venv_python), "-m", "pip", "install", "-e", path, "--force-reinstall", "--no-deps", "--no-build-isolation"], 120.0)
                
        def do_regen(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            res = regenerate_console_scripts(venv_dir, runner=runner)
            ctx.data["regenerated_scripts"] = res
            if res.get("failed"):
                raise RuntimeError(f"console script regeneration failed: {res['failed']}")
            _commit_op_backups(ctx)
            
        steps.append(Step("quarantine-venv", do=do_quarantine, undo=undo_quarantine, group="A"))
        steps.append(Step("create-venv", do=do_create, undo=undo_create, group="A"))
        steps.append(Step("restore-packages", do=do_restore, group="A"))
        steps.append(Step("regenerate-console-scripts", do=do_regen, group="A"))
        return steps

    # Not rebuilding
    pyvenv_home = findings_by_name.get("pyvenv_home", {})
    if pyvenv_home.get("level") == "error" or pyvenv_home.get("detail") == "skew":
        def do_rewrite(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            managed_dir = ctx.sys_dir / "env" / "python"
            rewrite_pyvenv_cfg(venv_dir, managed_dir)
        steps.append(Step("rewrite-pyvenv-cfg", do=do_rewrite, group="A"))
        
    console = findings_by_name.get("console_scripts", {})
    console_stale = console.get("level") == "warning" and console.get("detail", "").startswith("stale-launchers")
    skew = findings_by_name.get("venv_interpreter_skew", {})
    if skew.get("detail") == "patch-skew":
        def do_backup_interp(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            scripts = venv_dir / "Scripts"
            # lock probe
            if scripts.exists():
                for f in scripts.iterdir():
                    name = f.name.lower()
                    if name.endswith(".lockprobe"):
                        orig_name = f.name[:-len(".lockprobe")]
                        orig_f = f.with_name(orig_name)
                        if not orig_f.exists():
                            os.rename(str(f), str(orig_f))
                            
                for f in list(scripts.iterdir()):
                    name = f.name.lower()
                    if name in ("python.exe", "pythonw.exe") or (name.startswith("python3") and name.endswith(".dll")):
                        tmp = f.with_name(f.name + ".lockprobe")
                        try:
                            os.rename(str(f), str(tmp))
                        finally:
                            if tmp.exists():
                                os.rename(str(tmp), str(f))
                        
            files = interpreter_file_set(venv_dir)
            ctx.data["old_interpreter_hashes"] = hash_files(venv_dir, files)
            
            import tempfile, shutil
            tmp_dir = Path(tempfile.mkdtemp(prefix="venv-interp-"))
            try:
                for f in files:
                    src = venv_dir / f
                    dst = tmp_dir / f
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.exists():
                        shutil.copy2(src, dst)
                        
                dest = ctx.paths.get("venv_interp_backup")
                if not dest:
                    raise RuntimeError("missing venv_interp_backup path allocation")
                from core import backups
                backups.create(ctx.sys_dir, "venv-interp", tmp_dir, reason="refresh interpreter", op_id=ctx.op_id, label="pre-refresh", dest=Path(dest))
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                
        def do_refresh(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            managed_python = ctx.sys_dir / "env" / "python" / "python.exe"
            
            rc, out = runner([str(managed_python), "-m", "virtualenv", "--no-seed", str(venv_dir)], 30.0)
            if rc != 0: raise RuntimeError(f"virtualenv refresh failed: {out}")
            
            old_hashes = ctx.data.get("old_interpreter_hashes", {})
            new_files = interpreter_file_set(venv_dir)
            new_hashes = hash_files(venv_dir, new_files)
            
            baseline = None
            if manifest and "venv" in manifest:
                baseline = manifest["venv"].get("interpreter_hashes")
            
            # Figure out exactly what virtualenv generated by doing a dry-run in a temp dir
            import tempfile, shutil
            tmp_venv = Path(tempfile.mkdtemp(prefix="venv-probe-"))
            try:
                rc_probe, out_probe = runner([str(managed_python), "-m", "virtualenv", "--no-seed", str(tmp_venv)], 30.0)
                if rc_probe != 0: raise RuntimeError(f"virtualenv probe failed: {out_probe}")
                new_set = {f.as_posix() for f in interpreter_file_set(tmp_venv)}
            finally:
                shutil.rmtree(tmp_venv, ignore_errors=True)
                
            kept_foreign = []
            for f_path in new_files:
                rel = f_path.as_posix()
                if rel not in new_set:
                    f = venv_dir / rel
                    if f.exists():
                        if baseline is None or rel not in baseline:
                            kept_foreign.append(rel)
                        else:
                            current_h = new_hashes.get(rel)
                            if rel in old_hashes and current_h == old_hashes[rel]:
                                f.unlink()
                            else:
                                kept_foreign.append(rel)
                                
            ctx.data["kept_foreign_files"] = kept_foreign
            
        def undo_refresh(ctx):
            from core import backups
            import shutil
            venv_dir = ctx.sys_dir / "env" / "venv"
            dest = ctx.paths.get("venv_interp_backup")
            if not dest:
                raise RuntimeError("cannot undo refresh-interpreter: missing venv_interp_backup path allocation")
            dest = Path(dest)
            payload = dest / backups.PAYLOAD
            if not payload.exists():
                raise RuntimeError(f"cannot undo refresh-interpreter: interpreter backup not found at {dest}")
            def _raise(err):
                raise err
            expected = 0
            restored = 0
            for root, _, files in os.walk(payload, onerror=_raise):
                for f in files:
                    expected += 1
                    src = Path(root) / f
                    rel = src.relative_to(payload)
                    dst = venv_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    restored += 1
            if restored != expected:
                raise RuntimeError(f"undo refresh-interpreter restored {restored} of {expected} files")

        def do_record_hashes(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            ctx.data["new_interpreter_hashes"] = hash_files(venv_dir, interpreter_file_set(venv_dir))
            if not console_stale:
                _commit_op_backups(ctx)
            
        steps.append(Step("backup-interpreter-files", do=do_backup_interp, group="A"))
        steps.append(Step("refresh-interpreter", do=do_refresh, undo=undo_refresh, group="A"))
        steps.append(Step("record-interpreter-hashes", do=do_record_hashes, group="A"))
        
    console = findings_by_name.get("console_scripts", {})
    if console.get("level") == "warning" and console.get("detail", "").startswith("stale-launchers"):
        def do_regen_stale(ctx):
            venv_dir = ctx.sys_dir / "env" / "venv"
            res = regenerate_console_scripts(venv_dir, runner=runner)
            ctx.data["regenerated_scripts"] = res
            if res.get("failed"):
                raise RuntimeError(f"console script regeneration failed: {res['failed']}")
            _commit_op_backups(ctx)
        steps.append(Step("regenerate-console-scripts", do=do_regen_stale, group="A"))
        
    return steps
