import hashlib
import json
import ntpath
import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Callable

from core import backups, env_manifest, env_ops, provisioner, venv_manager, venv_repair

Runner = Callable[[list[str], float], tuple[int, str]]
Downloader = Callable[[str, Path], None]


def classify_change(installed: str | None, target: str) -> str:
    if not installed:
        return "fresh"
    if installed == target:
        return "same"
    iv = [int(x) for x in installed.split(".")]
    tv = [int(x) for x in target.split(".")]
    if tv < iv:
        return "downgrade"
    if tv[0] > iv[0]:
        return "major"
    if tv[1] > iv[1]:
        return "minor"
    return "patch"


def cache_paths(sys_dir: Path | str, version: str) -> tuple[Path, Path]:
    directory = Path(sys_dir) / "data" / "setup-files"
    archive = directory / f"python-{version}-embed-amd64.zip"
    return archive, Path(str(archive) + ".sha256")


def allocate_paths(
    sys_dir: Path | str, op_id: str, now: Callable[[], str]
) -> dict[str, Path]:
    root = backups.backups_root(Path(sys_dir))
    stamp = now().replace("-", "").replace(":", "")
    token = hashlib.sha256(str(op_id).encode("utf-8")).hexdigest()[:16]
    prefix = f"{stamp}-{token}"
    return {
        "python_backup": root / "python" / f"{prefix}-python-update",
        "venv_backup": root / "venv" / f"{prefix}-broken-venv",
        "freeze_backup": root / "venv-freeze" / f"{prefix}-venv-snapshot",
        "venv_failed_backup": root / "venv" / f"{prefix}-failed-rebuild",
        "venv_interp_backup": root / "venv-interp" / f"{prefix}-venv-refresh",
    }


def default_holders(
    paths: list[Path], runner: Runner = venv_manager.default_runner
) -> list[dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress",
    ]
    try:
        rc, output = runner(command, 10.0)
        if rc != 0 or not output.strip():
            return []
        processes = json.loads(output)
        if not isinstance(processes, list):
            processes = [processes]
        roots = [ntpath.normcase(str(path.resolve())) for path in paths]
        held = []
        for process in processes:
            executable = process.get("ExecutablePath")
            if not executable:
                continue
            normalized = ntpath.normcase(executable)
            for root in roots:
                prefix = root if root.endswith("\\") else root + "\\"
                if normalized == root or normalized.startswith(prefix):
                    held.append({
                        "pid": process.get("ProcessId"),
                        "exe": executable,
                    })
                    break
        return held
    except Exception:
        return []


def new_pin_text(
    runtimes_text: str, version: str, url: str, sha256: str | None
) -> str:
    in_python = False
    output = []
    for line in runtimes_text.splitlines(keepends=True):
        if re.search(r'"python"\s*:\s*\{', line):
            in_python = True
        elif in_python and (
            re.search(r"^\s*\},?\s*$", line)
            or re.search(r'"(nodejs|git|vscode|pwsh)"\s*:\s*\{', line)
        ):
            in_python = False

        if in_python:
            if re.search(r'"version"\s*:', line):
                line = re.sub(
                    r'("version"\s*:\s*)"[^"]*"',
                    lambda match: match.group(1) + json.dumps(version),
                    line,
                )
            elif re.search(r'"url"\s*:', line):
                line = re.sub(
                    r'("url"\s*:\s*)"[^"]*"',
                    lambda match: match.group(1) + json.dumps(url),
                    line,
                )
            elif re.search(r'"sha256"\s*:', line):
                if sha256:
                    line = re.sub(
                        r'("sha256"\s*:\s*)"[^"]*"',
                        lambda match: match.group(1) + json.dumps(sha256),
                        line,
                    )
                else:
                    line = re.sub(
                        r'\s*"sha256"\s*:\s*"[^"]*",?\r?\n?', "", line
                    )
                    if not line.strip():
                        # Removing a final property also removes its preceding comma.
                        if output:
                            output[-1] = re.sub(
                                r",([ \t]*\r?\n)$", r"\1", output[-1]
                            )
                        continue
        output.append(line)
    return "".join(output)


def plan_python_update(
    sys_dir: Path | str,
    target_version: str,
    *,
    url: str,
    sha256: str | None = None,
    allow_downgrade=False,
    allow_major=False,
    offline=False,
    force=False,
    downloader: Downloader = lambda u, d: provisioner._secure_download(u, d),
    runner: Runner = venv_manager.default_runner,
    free_space: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free,
    holders: Callable[[list[Path]], list[dict]] = default_holders,
    rename: Callable[[str, str], None] = os.replace,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], str] = env_ops.utc_now,
    venv_policy: str = "auto",
    installed: str | None = None,
    had_venv: bool | None = None,
) -> list[env_ops.Step]:
    sys_dir = Path(sys_dir)
    env_dir = sys_dir / "env"
    py_dir = env_dir / "python"
    new_dir = env_dir / "python.new"
    venv_dir = env_dir / "venv"

    # A rebuilt plan must describe the original environment.
    active = env_ops.active_journal(sys_dir)
    saved = (active or {}).get("data", {}).get("python_update", {})
    if saved.get("target_version") != target_version:
        saved = {}

    if installed is None:
        if "installed" in saved:
            installed = saved["installed"]
        elif (py_dir / "python.exe").exists():
            rc, output = runner([str(py_dir / "python.exe"), "--version"], 10.0)
            match = re.search(r"(\d+\.\d+\.\d+)", output)
            if rc == 0 and match:
                installed = match.group(1)

    if had_venv is None:
        had_venv = saved.get("had_venv", venv_dir.exists())

    change = classify_change(installed, target_version)
    if change == "downgrade" and not allow_downgrade and not force:
        raise ValueError("downgrade blocked without flag")
    if change == "major" and not allow_major and not force:
        raise ValueError("major upgrade blocked without flag")
    if change == "same" and not force:
        return []

    rebuild = venv_policy != "keep" and (
        change in ("minor", "major") or venv_policy == "rebuild"
    )
    refresh = not rebuild and venv_policy != "keep" and change == "patch"
    venv_backup_key = "venv_backup" if rebuild else "venv_interp_backup"
    venv_backup_kind = "venv" if rebuild else "venv-interp"

    def robust_rename(source, destination):
        for attempt in range(5):
            try:
                rename(str(source), str(destination))
                return
            except OSError:
                if attempt == 4:
                    raise
                sleep(0.1 * (2 ** attempt))

    def workspace(ctx):
        token = hashlib.sha256(str(ctx.op_id).encode("utf-8")).hexdigest()
        return sys_dir / "data" / "temp" / "env-op" / token / "python-update"

    def destination(ctx, key):
        # Normal engine execution supplies journaled allocations. The fallback
        # also supports callers invoking an individual public Step directly.
        if key not in ctx.paths:
            allocated = allocate_paths(sys_dir, ctx.op_id, now)
            for name, path in allocated.items():
                ctx.paths.setdefault(name, path)
        return Path(ctx.paths[key])

    def write_text(path, text):
        env_manifest._atomic_write_text(
            path, text, replace=robust_rename, sleep=sleep
        )

    def absence_receipt(ctx, key):
        return workspace(ctx) / f"{key}.absent"

    def backup_ref(ctx, key, kind):
        dest = destination(ctx, key)
        meta = backups._read_meta(dest)
        if meta is None:
            if (dest / backups.MARKER).exists() or (dest / backups.PAYLOAD).exists():
                raise RuntimeError(f"unreadable backup ownership: {dest}")
            return None
        if meta.get("op_id") != ctx.op_id or meta.get("kind") != kind:
            raise RuntimeError(f"backup belongs to another operation: {dest}")
        return backups.BackupRef(kind, dest, meta)

    def preserve_dir(ctx, source, kind, label, *, dest=None):
        source = Path(source)
        if not source.exists():
            return None
        if not source.is_dir():
            raise RuntimeError(f"expected a directory to preserve: {source}")

        if dest is not None:
            base = Path(dest)
            dest = base
            suffix = 1
            while dest.exists():
                meta = backups._read_meta(dest)
                reusable = (
                    not (dest / backups.PAYLOAD).exists()
                    and (
                        (
                            meta is not None
                            and meta.get("op_id") == ctx.op_id
                            and meta.get("kind") == kind
                            and meta.get("state") == "pending"
                            and meta.get("source_path") == str(source)
                        )
                        or not any(dest.iterdir())
                    )
                )
                if reusable:
                    break
                suffix += 1
                dest = base.with_name(f"{base.name}-{suffix}")

        return backups.create(
            sys_dir,
            kind,
            source,
            reason=label.replace("-", " "),
            op_id=ctx.op_id,
            label=label,
            dest=dest,
            now=now(),
            rename=robust_rename,
            sleep=sleep,
        )

    def preserve_file(ctx, source):
        source = Path(source)
        if not source.exists():
            return
        box = workspace(ctx) / "preserved-file"
        if box.exists():
            preserve_dir(ctx, box, "state", "interrupted-file-preservation")
        box.mkdir(parents=True)
        robust_rename(source, box / source.name)
        preserve_dir(ctx, box, "state", "superseded-cache-file")

    def save_directory(ctx, source, key, kind, label):
        ref = backup_ref(ctx, key, kind)
        if ref is not None:
            if (ref.path / backups.PAYLOAD).is_dir():
                return
            if ref.meta.get("state") == "restored":
                raise RuntimeError(f"backup was already restored: {ref.path}")
        if absence_receipt(ctx, key).exists():
            return
        if not source.exists():
            write_text(absence_receipt(ctx, key), "absent\n")
            return
        backups.create(
            sys_dir,
            kind,
            source,
            reason=label.replace("-", " "),
            op_id=ctx.op_id,
            label=label,
            dest=destination(ctx, key),
            now=now(),
            rename=robust_rename,
            sleep=sleep,
        )

    def restore_directory(ctx, source, key, kind, *, failed_key=None):
        ref = backup_ref(ctx, key, kind)
        payload = ref.path / backups.PAYLOAD if ref is not None else None

        if payload is not None and payload.is_dir():
            if Path(ref.meta.get("source_path", "")) != source:
                raise RuntimeError(f"unexpected restore target in {ref.path}")
            if source.exists():
                preserve_dir(
                    ctx,
                    source,
                    "venv" if failed_key else kind,
                    "failed-rebuild" if failed_key else "failed-swap",
                    dest=destination(ctx, failed_key) if failed_key else None,
                )
            backups.restore(ref, rename=robust_rename, sleep=sleep)
            return

        # No payload means either the forward move never happened, or an undo
        # already restored it. Neither case authorizes touching the live tree.
        # Only an explicit pre-mutation absence receipt permits removing a new
        # tree when there was no original to restore.
        if absence_receipt(ctx, key).exists() and source.exists():
            preserve_dir(
                ctx,
                source,
                "venv" if failed_key else kind,
                "failed-rebuild" if failed_key else "failed-swap",
                dest=destination(ctx, failed_key) if failed_key else None,
            )

    def check_version(executable, label):
        rc, output = runner([str(executable), "--version"], 10.0)
        if rc != 0:
            raise RuntimeError(f"{label} --version failed: {output}")
        match = re.search(r"(\d+\.\d+\.\d+)", output)
        if not match or match.group(1) != target_version:
            raise RuntimeError(
                f"{label} version mismatch: target={target_version}, got={output}"
            )

    def do_preflight(ctx):
        python_size = sum(
            path.stat().st_size for path in py_dir.rglob("*") if path.is_file()
        )
        venv_size = sum(
            path.stat().st_size for path in venv_dir.rglob("*") if path.is_file()
        )
        required = 2 * (python_size + venv_size) + (256 << 20)
        if free_space(sys_dir) < required:
            raise RuntimeError(f"Low disk space: need {required}")
        busy = holders([py_dir, venv_dir])
        if busy:
            raise RuntimeError(f"Holders active: {busy}")
        ctx.data["classification"] = change
        ctx.data["python_update"] = {
            "target_version": target_version,
            "installed": installed,
            "had_venv": bool(had_venv),
        }

    def do_download(ctx):
        archive, checksum = cache_paths(sys_dir, target_version)
        valid_cache = False
        if archive.is_file() and checksum.is_file():
            cached_hash = checksum.read_text().strip()
            valid_cache = (
                (not sha256 or cached_hash == sha256)
                and provisioner._hash_file(archive, "sha256") == cached_hash
            )
        if valid_cache:
            return
        if offline:
            raise RuntimeError("Offline mode but cache missing or invalid")

        archive.parent.mkdir(parents=True, exist_ok=True)
        partial = archive.with_suffix(".part")
        preserve_file(ctx, partial)
        try:
            downloader(url, partial)
            actual_hash = provisioner._hash_file(partial, "sha256")
            if sha256 and actual_hash != sha256:
                raise RuntimeError("Checksum mismatch")
        except Exception:
            preserve_file(ctx, partial)
            raise

        preserve_file(ctx, archive)
        preserve_file(ctx, checksum)
        robust_rename(partial, archive)
        write_text(checksum, actual_hash)

    def do_stage(ctx):
        work = workspace(ctx)
        owned = work / "stage-owned"
        ready = work / "stage-ready"
        staging = work / "stage"
        staged_python = staging / "python"

        if new_dir.exists():
            if owned.is_file() and ready.is_file():
                if ready.read_text().strip() == target_version:
                    return
            raise RuntimeError(f"unowned staging directory already exists: {new_dir}")

        # Bootstrap in an isolated parent. Even runners that infer their package
        # prefix as executable.parent.parent cannot write into the live env.
        if staging.exists():
            preserve_dir(ctx, staging, "state", "interrupted-python-stage")
        write_text(owned, f"{target_version}\n")
        staged_python.mkdir(parents=True)

        archive, _ = cache_paths(sys_dir, target_version)
        with zipfile.ZipFile(archive, "r") as package:
            members = package.infolist()
            for member in members:
                name = member.filename.replace("\\", "/")
                if (
                    name.startswith("/")
                    or ":" in name
                    or ".." in name.split("/")
                ):
                    raise RuntimeError("zip-slip attempt")
            for member in members:
                package.extract(member, staged_python)

        for pth in staged_python.glob("python*._pth"):
            text = pth.read_text()
            pth.write_text(text.replace("#import site", "import site"))

        executable = staged_python / "python.exe"
        pip_script = sys_dir / "data" / "setup-files" / "get-pip.py"
        if pip_script.exists():
            rc, output = runner(
                [str(executable), str(pip_script), "--no-warn-script-location"],
                60.0,
            )
            if rc != 0:
                raise RuntimeError(f"get-pip failed: {output}")
            command = [str(executable), "-m", "pip", "install"]
            if offline:
                command.append("--no-index")
            rc, output = runner(command + ["virtualenv"], 60.0)
            if rc != 0:
                raise RuntimeError(f"virtualenv install failed: {output}")

        check_version(executable, "Staged python")
        write_text(ready, f"{target_version}\n")
        env_dir.mkdir(parents=True, exist_ok=True)
        robust_rename(staged_python, new_dir)
        preserve_dir(ctx, staging, "state", "python-stage-residuals")

    def undo_stage(ctx):
        if not (workspace(ctx) / "stage-owned").is_file():
            return
        preserve_dir(ctx, new_dir, "python", "staged-failed")
        preserve_dir(
            ctx, workspace(ctx) / "stage", "state", "interrupted-python-stage"
        )

    def read_snapshot(ctx):
        ref = backup_ref(ctx, "freeze_backup", "venv-freeze")
        if ref is None:
            raise RuntimeError("missing package snapshot for this operation")
        path = ref.path / backups.PAYLOAD / venv_manager.SNAPSHOT_FILENAME
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict):
            raise RuntimeError(f"invalid package snapshot: {path}")
        return snapshot

    def do_snapshot(ctx):
        ref = backup_ref(ctx, "freeze_backup", "venv-freeze")
        if ref is not None and (ref.path / backups.PAYLOAD).exists():
            ctx.data["snapshot"] = read_snapshot(ctx)
            return

        scratch = workspace(ctx) / "freeze"
        if scratch.exists():
            preserve_dir(ctx, scratch, "state", "interrupted-package-snapshot")
        scratch.mkdir(parents=True)
        snapshot = venv_manager.build_snapshot(
            sys_dir, now=now(), python_version=installed
        )
        plan = venv_repair.restore_packages_step_data(snapshot)
        write_text(
            scratch / venv_manager.SNAPSHOT_FILENAME,
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        )
        write_text(scratch / "constraints.txt", plan["constraints_text"])
        backups.create(
            sys_dir,
            "venv-freeze",
            scratch,
            reason="python update package snapshot",
            op_id=ctx.op_id,
            label="venv-snapshot",
            dest=destination(ctx, "freeze_backup"),
            now=now(),
            rename=robust_rename,
            sleep=sleep,
        )
        ctx.data["snapshot"] = snapshot

    def undo_snapshot(ctx):
        preserve_dir(
            ctx,
            workspace(ctx) / "freeze",
            "state",
            "interrupted-package-snapshot",
        )

    def do_backup_venv(ctx):
        # Preserve the complete original even for a patch refresh. Virtualenv
        # may create files that an interpreter-only overlay cannot undo.
        save_directory(
            ctx,
            venv_dir,
            venv_backup_key,
            venv_backup_kind,
            "broken-venv" if rebuild else "pre-refresh",
        )
        if refresh:
            ref = backup_ref(ctx, venv_backup_key, venv_backup_kind)
            if ref is not None and (ref.path / backups.PAYLOAD).is_dir():
                payload = ref.path / backups.PAYLOAD
                ctx.data["old_interpreter_hashes"] = venv_manager.hash_files(
                    payload, venv_manager.interpreter_file_set(payload)
                )

    def undo_venv(ctx):
        restore_directory(
            ctx,
            venv_dir,
            venv_backup_key,
            venv_backup_kind,
            failed_key="venv_failed_backup",
        )

    def do_quarantine_python(ctx):
        save_directory(ctx, py_dir, "python_backup", "python", "old-python")

    def undo_quarantine_python(ctx):
        restore_directory(ctx, py_dir, "python_backup", "python")

    def do_swap(ctx):
        if not new_dir.exists():
            ref = backup_ref(ctx, "python_backup", "python")
            backed_up = ref is not None and (ref.path / backups.PAYLOAD).is_dir()
            originally_absent = absence_receipt(ctx, "python_backup").is_file()
            if py_dir.exists() and (backed_up or originally_absent):
                check_version(py_dir / "python.exe", "Swapped python")
                return
            raise RuntimeError("staged Python is missing")
        robust_rename(new_dir, py_dir)

    def undo_swap(ctx):
        if new_dir.exists() or not py_dir.exists():
            return
        ref = backup_ref(ctx, "python_backup", "python")
        backed_up = ref is not None and (ref.path / backups.PAYLOAD).is_dir()
        originally_absent = absence_receipt(ctx, "python_backup").is_file()
        if backed_up or originally_absent:
            robust_rename(py_dir, new_dir)

    def do_create_or_refresh(ctx):
        ref = backup_ref(ctx, venv_backup_key, venv_backup_kind)
        payload = ref.path / backups.PAYLOAD if ref is not None else None
        has_original = payload is not None and payload.is_dir()
        originally_absent = absence_receipt(ctx, venv_backup_key).is_file()

        if not has_original and not originally_absent:
            raise RuntimeError("venv backup has not completed")
        if refresh and originally_absent:
            return

        # A started-but-unrecorded creation may have left a partial tree.
        # Preserve it and retry from the immutable original.
        if venv_dir.exists():
            preserve_dir(
                ctx,
                venv_dir,
                "venv",
                "interrupted-venv-build",
                dest=destination(ctx, "venv_failed_backup"),
            )
        if refresh:
            shutil.copytree(payload, venv_dir)

        command = [str(py_dir / "python.exe"), "-m", "virtualenv"]
        if refresh:
            command.append("--no-seed")
        command.append(str(venv_dir))
        rc, output = runner(command, 60.0)
        if rc != 0:
            raise RuntimeError(f"venv creation failed: {output}")

    def do_restore_packages(ctx):
        snapshot = read_snapshot(ctx)
        plan = venv_repair.restore_packages_step_data(snapshot)
        executable = venv_dir / "Scripts" / "python.exe"
        if not executable.is_file():
            raise RuntimeError("package restore failed: venv interpreter missing")

        def install(arguments, timeout):
            command = [str(executable), "-m", "pip", "install"]
            if offline:
                command.append("--no-index")
            return runner(command + arguments, timeout)

        baseline = list(plan["t1"])
        baseline_names = {
            re.split(r"[<>=!~\[]", spec, maxsplit=1)[0].lower()
            for spec in baseline
        }
        for name in ("filelock", "psutil", "pydantic", "pywinpty"):
            if name not in baseline_names:
                baseline.append(name)
        if baseline:
            rc, output = install(baseline, 120.0)
            if rc != 0:
                raise RuntimeError(f"T1 baseline install failed: {output}")

        if plan["t2"]:
            constraints = (
                destination(ctx, "freeze_backup")
                / backups.PAYLOAD
                / "constraints.txt"
            )
            # One option token also prevents simplistic injected runners from
            # mistaking the constraints filename for an install requirement.
            rc, output = install(
                [f"--constraint={constraints}"] + plan["t2"], 300.0
            )
            if rc != 0:
                failures = []
                for package in plan["t2"]:
                    package_rc, package_output = install([package], 60.0)
                    if package_rc != 0:
                        failures.append(f"{package}: {package_output}")
                if failures:
                    raise RuntimeError(
                        "requested package restore failed: " + "; ".join(failures)
                    )

        for path in plan["t3"]:
            rc, output = install(
                [
                    "-e",
                    path,
                    "--force-reinstall",
                    "--no-deps",
                    "--no-build-isolation",
                ],
                120.0,
            )
            if rc != 0:
                raise RuntimeError(f"editable package restore failed: {output}")
        ctx.data["skipped_editable"] = plan["skipped_editable"]

    def do_regenerate(ctx):
        result = venv_repair.regenerate_console_scripts(venv_dir, runner=runner)
        ctx.data["regenerated_scripts"] = result
        if result.get("error") or result.get("failed"):
            raise RuntimeError(f"console script regeneration failed: {result}")

    def do_record_hashes(ctx):
        ctx.data["new_interpreter_hashes"] = venv_manager.hash_files(
            venv_dir, venv_manager.interpreter_file_set(venv_dir)
        )

    def do_verify(ctx):
        check_version(py_dir / "python.exe", "Verify python")
        original = ctx.data.get("python_update", {})
        expected_venv = rebuild or original.get("had_venv", had_venv)
        if expected_venv and not venv_dir.is_dir():
            raise RuntimeError("Verify failed: venv missing")
        if not venv_dir.exists():
            return

        if rebuild or refresh:
            executable = venv_dir / "Scripts" / "python.exe"
            if not executable.is_file():
                raise RuntimeError("Verify failed: venv interpreter missing")
            check_version(executable, "Verify venv")

        for finding in venv_manager.probe_venv(sys_dir, runner=runner):
            if finding.level == "error":
                raise RuntimeError(f"Venv verify failed: {finding.name}")
            if (
                rebuild
                and finding.name == "venv_imports"
                and finding.level != "ok"
            ):
                raise RuntimeError(
                    f"Venv verify failed: {finding.name}: {finding.detail}"
                )

    def do_write_pin(ctx):
        path = sys_dir / "runtimes.json"
        if path.exists():
            with open(path, "r", encoding="utf-8", newline="") as handle:
                text = handle.read()
            write_text(path, new_pin_text(text, target_version, url, sha256))

    def do_write_manifest(ctx):
        manifest = env_manifest.read_manifest(sys_dir).data or {}
        manifest["python"] = {"version": target_version}
        env_manifest.write_manifest(
            sys_dir, manifest, replace=robust_rename, sleep=sleep
        )

    def do_commit_snapshots(ctx):
        for ref in backups.scan(sys_dir).valid:
            if (
                ref.meta.get("op_id") == ctx.op_id
                and ref.meta.get("state") == "pending"
            ):
                backups.commit(ref, now=now())

    steps = [
        env_ops.Step("preflight", do_preflight, group="A"),
        env_ops.Step("download-verify", do_download, group="A"),
        env_ops.Step("stage", do_stage, undo=undo_stage, group="A"),
        env_ops.Step(
            "snapshot-packages", do_snapshot, undo=undo_snapshot, group="A"
        ),
    ]
    if rebuild or refresh:
        steps.append(env_ops.Step(
            "quarantine-venv" if rebuild else "backup-interpreter-files",
            do_backup_venv,
            undo=undo_venv,
            group="A",
        ))
    steps.extend([
        env_ops.Step(
            "quarantine-python",
            do_quarantine_python,
            undo=undo_quarantine_python,
            group="A",
        ),
        env_ops.Step("swap", do_swap, undo=undo_swap, group="A"),
    ])
    if rebuild:
        steps.extend([
            env_ops.Step(
                "create-venv", do_create_or_refresh, undo=undo_venv, group="A"
            ),
            env_ops.Step("restore-packages", do_restore_packages, group="A"),
            env_ops.Step("regenerate-console-scripts", do_regenerate, group="A"),
        ])
    elif refresh:
        steps.extend([
            env_ops.Step(
                "refresh-interpreter",
                do_create_or_refresh,
                undo=undo_venv,
                group="A",
            ),
            env_ops.Step("record-interpreter-hashes", do_record_hashes, group="A"),
        ])
    steps.extend([
        env_ops.Step("verify", do_verify, group="A"),
        env_ops.Step("write-pin", do_write_pin, group="B"),
        env_ops.Step("write-manifest", do_write_manifest, group="B"),
        env_ops.Step("record-snapshot-commit", do_commit_snapshots, group="B"),
    ])
    return steps


def handoff_path(sys_dir: Path | str) -> Path:
    """Dispatch handoff: runner Python, then whether the user confirmed."""
    return Path(sys_dir) / "data" / "state" / "env-op" / "handoff.txt"


def prepare_runner(
    sys_dir: Path | str,
    op_id: str,
    *,
    confirmed: bool,
    copytree=shutil.copytree,
) -> Path:
    """Copy the current interpreter outside both swap targets."""
    sys_dir = Path(sys_dir)
    source = sys_dir / "env" / "python"
    if not (source / "python.exe").is_file():
        raise FileNotFoundError(f"no interpreter to copy for the runner: {source}")

    runner_dir = sys_dir / "data" / "temp" / "env-op" / op_id / "runner"
    if runner_dir.exists():
        backups.create(
            sys_dir,
            "state",
            runner_dir,
            reason="preserve previous runner",
            op_id=op_id,
            label="previous-runner",
        )
    runner_dir.parent.mkdir(parents=True, exist_ok=True)
    copytree(source, runner_dir)

    executable = runner_dir / "python.exe"
    handoff = handoff_path(sys_dir)
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_bytes(
        (
            str(executable)
            + "\r\n"
            + ("1" if confirmed else "0")
            + "\r\n"
        ).encode("mbcs")
    )
    return executable
