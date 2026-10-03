import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Callable, Any

from core import backups, env_manifest, env_ops, venv_manager, venv_repair, provisioner

Runner = Callable[[list[str], float], tuple[int, str]]
Downloader = Callable[[str, Path], None]

def classify_change(installed: str | None, target: str) -> str:
    if not installed:
        return "fresh"
    if installed == target:
        return "same"
    def _parse(v): return [int(x) for x in v.split(".")]
    iv, tv = _parse(installed), _parse(target)
    if tv < iv:
        return "downgrade"
    if tv[0] > iv[0]:
        return "major"
    if tv[1] > iv[1]:
        return "minor"
    return "patch"

def cache_paths(sys_dir: Path | str, version: str) -> tuple[Path, Path]:
    d = Path(sys_dir) / "data" / "setup-files"
    base = d / f"python-{version}-embed-amd64.zip"
    return base, Path(str(base) + ".sha256")

def allocate_paths(sys_dir: Path | str, op_id: str, now: Callable[[], str]) -> dict[str, Path]:
    sys_dir = Path(sys_dir)
    broot = sys_dir / "data" / "backups" / "env"
    ts = now().replace("-", "").replace(":", "")
    return {
        "python_backup": broot / "python" / f"{ts}-python-update",
        "venv_backup": broot / "venv" / f"{ts}-broken-venv",
        "freeze_backup": broot / "venv-freeze" / f"{ts}-venv-snapshot",
        "venv_failed_backup": broot / "venv" / f"{ts}-failed-rebuild",
        "venv_interp_backup": broot / "venv-interp" / f"{ts}-venv-refresh",
    }

def default_holders(paths: list[Path], runner: Runner = venv_manager.default_runner) -> list[dict]:
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"
    ]
    try:
        rc, out = runner(cmd, 10.0)
        if rc != 0 or not out.strip():
            return []
        import json
        import ntpath
        data = json.loads(out)
        if not isinstance(data, list):
            data = [data]
            
        held = []
        search_paths = [ntpath.normcase(str(p.resolve())) for p in paths]
        for proc in data:
            exe = proc.get("ExecutablePath")
            if not exe:
                continue
            exe_lower = ntpath.normcase(exe)
            for sp in search_paths:
                sp_prefix = sp if sp.endswith("\\") else sp + "\\"
                if exe_lower.startswith(sp_prefix) or exe_lower == sp:
                    held.append({"pid": proc.get("ProcessId"), "exe": exe})
                    break
        return held
    except Exception:
        return []

def new_pin_text(runtimes_text: str, version: str, url: str, sha256: str | None) -> str:
    in_python = False
    out = []
    for line in runtimes_text.splitlines(keepends=True):
        if re.search(r'"python"\s*:\s*\{', line):
            in_python = True
        elif in_python and (re.search(r'^\s*\},?\s*$', line) or re.search(r'"(nodejs|git|vscode|pwsh)"\s*:\s*\{', line)):
            in_python = False
        
        if in_python:
            if re.search(r'"version"\s*:', line):
                line = re.sub(r'("version"\s*:\s*)"[^"]*"', rf'\1"{version}"', line)
            elif re.search(r'"url"\s*:', line):
                line = re.sub(r'("url"\s*:\s*)"[^"]*"', rf'\1"{url}"', line)
            elif re.search(r'"sha256"\s*:', line):
                if sha256:
                    line = re.sub(r'("sha256"\s*:\s*)"[^"]*"', rf'\1"{sha256}"', line)
                else:
                    line = re.sub(r'\s*"sha256"\s*:\s*"[^"]*",?\r?\n?', '', line)
                    if not line.strip(): continue
        out.append(line)
    return "".join(out)

def plan_python_update(
    sys_dir: Path | str, target_version: str, *, url: str, sha256: str | None = None,
    allow_downgrade=False, allow_major=False, offline=False, force=False,
    downloader: Downloader = lambda u, d: provisioner._secure_download(u, d),
    runner: Runner = venv_manager.default_runner,
    free_space: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free,
    holders: Callable[[list[Path]], list[dict]] = default_holders,
    rename: Callable[[str, str], None] = os.replace,
    sleep: Callable[[float], None] = __import__("time").sleep,
    now: Callable[[], str] = env_ops.utc_now,
    venv_policy: str = "auto",
    installed: str | None = None,
    had_venv: bool | None = None
) -> list[env_ops.Step]:
    sys_dir = Path(sys_dir)
    env_dir = sys_dir / "env"
    py_dir = env_dir / "python"
    venv_dir = env_dir / "venv"

    if installed is None:
        if (py_dir / "python.exe").exists():
            rc, out = runner([str(py_dir / "python.exe"), "--version"], 10.0)
            if rc == 0:
                m = re.search(r"(\d+\.\d+\.\d+)", out)
                if m: installed = m.group(1)

    if had_venv is None:
        had_venv = venv_dir.exists()

    change = classify_change(installed, target_version)
    if change == "downgrade" and not allow_downgrade and not force:
        raise ValueError("downgrade blocked without flag")
    if change == "major" and not allow_major and not force:
        raise ValueError("major upgrade blocked without flag")
    if change == "same" and not force:
        return []

    steps = []

    def robust_rename(src: str, dst: str):
        for i in range(5):
            try:
                rename(str(src), str(dst))
                return
            except OSError:
                if i == 4: raise
                sleep(0.1 * (2 ** i))

    def do_preflight(ctx):
        p_sz = sum(f.stat().st_size for f in py_dir.rglob('*') if f.is_file()) if py_dir.exists() else 0
        v_sz = sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file()) if venv_dir.exists() else 0
        req = 2 * (p_sz + v_sz) + (256 << 20)
        if free_space(sys_dir) < req:
            raise RuntimeError(f"Low disk space: need {req}")
        busy = holders([py_dir, venv_dir])
        if busy:
            raise RuntimeError(f"Holders active: {busy}")
        ctx.data["classification"] = change

    def do_download(ctx):
        zip_path, sha_path = cache_paths(sys_dir, target_version)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        valid_cache = False
        if zip_path.exists() and sha_path.exists():
            c_sha = sha_path.read_text().strip()
            if (not sha256 or c_sha == sha256) and provisioner._hash_file(zip_path, "sha256") == c_sha:
                valid_cache = True
                
        if offline and not valid_cache:
            raise RuntimeError("Offline mode but cache missing or invalid")
            
        if not valid_cache:
            part = zip_path.with_suffix(".part")
            try:
                downloader(url, part)
                a_sha = provisioner._hash_file(part, "sha256")
                if sha256 and a_sha != sha256:
                    raise RuntimeError("Checksum mismatch")
                robust_rename(str(part), str(zip_path))
                sha_path.write_text(a_sha)
            except Exception:
                part.unlink(missing_ok=True)
                raise

    def do_stage(ctx):
        new_dir = env_dir / "python.new"
        if new_dir.exists(): shutil.rmtree(new_dir)
        new_dir.mkdir(parents=True)
        zip_path, _ = cache_paths(sys_dir, target_version)
        
        tmp = sys_dir / "data" / "temp" / "python_stage"
        if tmp.exists(): shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                if member.filename.startswith("/") or member.filename.startswith("\\") or ".." in member.filename:
                    raise RuntimeError("zip-slip attempt")
                zf.extract(member, tmp)
        
        for f in tmp.iterdir():
            robust_rename(str(f), str(new_dir / f.name))
        shutil.rmtree(tmp)
        
        for pth in new_dir.glob("python*._pth"):
            txt = pth.read_text()
            txt = txt.replace("#import site", "import site")
            pth.write_text(txt)
            
        pip_script = sys_dir / "data" / "setup-files" / "get-pip.py"
        if pip_script.exists():
            rc1, out1 = runner([str(new_dir / "python.exe"), str(pip_script), "--no-warn-script-location"], 60.0)
            if rc1 != 0: raise RuntimeError(f"get-pip failed: {out1}")
            rc2, out2 = runner([str(new_dir / "python.exe"), "-m", "pip", "install", "virtualenv"], 60.0)
            if rc2 != 0: raise RuntimeError(f"virtualenv install failed: {out2}")
            
        rc, out = runner([str(new_dir / "python.exe"), "--version"], 10.0)
        if rc != 0: raise RuntimeError(f"Staged python --version failed: {out}")
        if str(target_version) not in out:
            raise RuntimeError("Staged python version mismatch")
            
    def undo_stage(ctx):
        new_dir = env_dir / "python.new"
        if new_dir.exists():
            backups.create(sys_dir, "python", new_dir, reason="quarantine staged", op_id=ctx.op_id, label="staged-failed", rename=robust_rename, sleep=sleep)

    def do_snapshot(ctx):
        if venv_dir.exists():
            snap = venv_manager.build_snapshot(sys_dir, now=now(), python_version=installed)
            venv_manager.write_snapshot(sys_dir, snap, replace=robust_rename, sleep=sleep)
            ctx.data["snapshot"] = snap

    def do_quar_py(ctx):
        if py_dir.exists():
            backups.create(sys_dir, "python", py_dir, reason="update", op_id=ctx.op_id, label="old-python", rename=robust_rename, sleep=sleep)
            
    def undo_quar_py(ctx):
        for ref in backups.scan(sys_dir).valid:
            if ref.meta.get("op_id") == ctx.op_id and ref.kind == "python" and "old-python" in ref.path.name:
                if (ref.path / backups.PAYLOAD).exists() and not py_dir.exists():
                    backups.restore(ref, rename=robust_rename, sleep=sleep)
                break

    def do_swap(ctx):
        new_dir = env_dir / "python.new"
        robust_rename(str(new_dir), str(py_dir))
                
    def undo_swap(ctx):
        new_dir = env_dir / "python.new"
        if py_dir.exists() and not new_dir.exists():
            robust_rename(str(py_dir), str(new_dir))

    was_rebuilt = change in ("minor", "major") or venv_policy == "rebuild"
    
    def do_verify(ctx):
        rc, out = runner([str(py_dir / "python.exe"), "--version"], 10.0)
        if rc != 0: raise RuntimeError("Verify failed")
        if str(target_version) not in out:
            raise RuntimeError(f"Verify python version mismatch: target={target_version}, got={out}")
            
        if had_venv or was_rebuilt:
            if not venv_dir.exists():
                raise RuntimeError("Verify failed: venv missing")
                
        if venv_dir.exists():
            f = venv_manager.probe_venv(sys_dir, runner=runner)
            for x in f:
                if x.level == "error":
                    raise RuntimeError(f"Venv verify failed: {x.name}")
                if was_rebuilt and x.name == "venv_imports" and x.level == "warning":
                    raise RuntimeError(f"Venv verify failed: {x.name} (warning after rebuild)")

    steps.extend([
        env_ops.Step("preflight", do_preflight, group="A"),
        env_ops.Step("download-verify", do_download, group="A"),
        env_ops.Step("stage", do_stage, undo=undo_stage, group="A"),
        env_ops.Step("snapshot-packages", do_snapshot, group="A"),
    ])

    venv_pre_swap = []
    venv_post_swap = []
    synthetic_findings = []
    if not (venv_policy == "keep" or (venv_policy == "auto" and change == "same")):
        if was_rebuilt:
            synthetic_findings.append({"name": "venv_interpreter", "level": "error"})
        elif change == "patch":
            synthetic_findings.append({"name": "venv_interpreter_skew", "level": "warning", "detail": "patch-skew"})
            
    if synthetic_findings:
        all_venv_steps = venv_repair.plan_venv_repair(sys_dir, synthetic_findings, runner=runner)
        for s in all_venv_steps:
            if s.name in ("quarantine-venv", "backup-interpreter-files"):
                venv_pre_swap.append(s)
            else:
                venv_post_swap.append(s)

    steps.extend(venv_pre_swap)
    steps.extend([
        env_ops.Step("quarantine-python", do_quar_py, undo=undo_quar_py, group="A"),
        env_ops.Step("swap", do_swap, undo=undo_swap, group="A"),
    ])
    steps.extend(venv_post_swap)
    steps.extend([
        env_ops.Step("verify", do_verify, group="A"),
    ])

    def do_write_pin(ctx):
        rt_path = sys_dir / "runtimes.json"
        if rt_path.exists():
            txt = rt_path.read_text(encoding="utf-8")
            txt = new_pin_text(txt, target_version, url, sha256)
            env_manifest._atomic_write_text(rt_path, txt, replace=robust_rename, sleep=sleep)
            
    def do_write_manifest(ctx):
        m = env_manifest.read_manifest(sys_dir).data or {}
        m["python"] = {"version": target_version}
        env_manifest.write_manifest(sys_dir, m, replace=robust_rename, sleep=sleep)
        
    def do_commit_snaps(ctx):
        for ref in backups.scan(sys_dir).valid:
            if ref.meta.get("op_id") == ctx.op_id and ref.meta.get("state") == "pending":
                backups.commit(ref, now=now())

    steps.extend([
        env_ops.Step("write-pin", do_write_pin, group="B"),
        env_ops.Step("write-manifest", do_write_manifest, group="B"),
        env_ops.Step("record-snapshot-commit", do_commit_snaps, group="B"),
    ])
    return steps


def handoff_path(sys_dir: Path | str) -> Path:
    """The file a normal engine process leaves for dispatch.bat: line 1 runner python, line 2 `1` if the user confirmed."""
    return Path(sys_dir) / "data" / "state" / "env-op" / "handoff.txt"


def prepare_runner(sys_dir: Path | str, op_id: str, *, confirmed: bool, copytree=shutil.copytree) -> Path:
    """Copy the CURRENT interpreter to a runner dir outside both swap targets and write the handoff file.

    The calling process runs on env/python and so cannot rename it (design 6.1, B1). It must exit with code 75
    right after this call; dispatch.bat then re-runs the same command line on the returned interpreter with
    ENGRAM_IN_RUNNER=1. The copy is of the working interpreter, so the runner does not depend on the staged one.
    """
    sys_dir = Path(sys_dir)
    source = sys_dir / "env" / "python"
    if not (source / "python.exe").is_file():
        raise FileNotFoundError(f"no interpreter to copy for the runner: {source}")
    runner_dir = sys_dir / "data" / "temp" / "env-op" / op_id / "runner"
    if runner_dir.exists():
        shutil.rmtree(runner_dir)
    runner_dir.parent.mkdir(parents=True, exist_ok=True)
    copytree(source, runner_dir)
    exe = runner_dir / "python.exe"
    handoff = handoff_path(sys_dir)
    handoff.parent.mkdir(parents=True, exist_ok=True)
    # read back by `set /p` / `for /f` in dispatch.bat: ANSI code page, one value per line, no escaping needed
    handoff.write_bytes((str(exe) + "\r\n" + ("1" if confirmed else "0") + "\r\n").encode("mbcs"))
    return exe
