"""Windows Sandbox isolation with guest-owned evidence and verified teardown.

The current WSB capability observation is one instance per user. Detection
publishes that observation; reservation code consumes capabilities.concurrency.
Raw list and stop support are mandatory even for the LogonCommand fallback:
without them this provider cannot honor verified teardown. Help *exit codes*
probe command presence; localized help and exec text are never interpreted.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable, Sequence
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from _sys.core.isolation import (
    Availability, Capabilities, Evidence, EvidenceValidationError, ExecResult,
    Handle, Profile, collect_guest_evidence, probe_availability,
)


@dataclass
class _Job:
    handle: Handle
    profile: Profile
    inputs: tuple[Path, ...]
    workspace: Path | None
    lease: object
    cli: bool
    instance: str | None = None
    destroyed: bool = False
    executions: set[str] = field(default_factory=set)
    launch_before: set[str] | None = None


class SandboxLifecycleError(RuntimeError):
    """Cleanup could not be verified; handle permits an explicit destroy retry."""

    def __init__(self, message: str, handle: Handle) -> None:
        super().__init__(message + "; run `engram isolation check`")
        self.handle = handle


class WindowsSandboxProvider:
    """Protocol implementation; all external processes use the injected runner.

    create reserves a fresh job/mount. In CLI mode it also starts the VM; in
    fallback mode exec starts the .wsb with the wrapped command as LogonCommand.
    Fallback handles support one execution. Input directories are mapped at
    guest_root/input-N; evidence at guest_root/evidence; dev at guest_root/workspace.
    A per-user file lease covers the entire lifecycle, including failed cleanup.
    """

    def __init__(
        self, *, runner: Callable = subprocess.run, workspace: Path | None = None,
        lock_root: Path | None = None, guest_root: str | None = None,
        probe_timeout: float = 5, lifecycle_timeout: float = 30,
        lock_timeout: float = 1, poll_interval: float = 0.1,
        observed_concurrency: int = 1,
    ) -> None:
        self.runner = runner
        self.workspace = workspace
        user = os.environ.get("USERPROFILE", str(Path.home()))
        key = hashlib.sha256(user.casefold().encode("utf-8")).hexdigest()[:24]
        self.lock_root = Path(lock_root or Path(tempfile.gettempdir()) / "engram-wsb") / key
        drive = os.environ.get("SystemDrive", Path.home().drive)
        self.guest_root = guest_root or drive + r"\EngramSandbox"
        self.probe_timeout = probe_timeout
        self.lifecycle_timeout = lifecycle_timeout
        self.lock_timeout = lock_timeout
        self.poll_interval = poll_interval
        self.observed_concurrency = observed_concurrency
        self._probing = False
        self._availability: Availability | None = None
        self._cli = False
        self._jobs: dict[str, _Job] = {}

    def _run(self, argv: list[str], timeout: float):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("process timeout must be finite and positive")
        try:
            return self.runner(argv, timeout=timeout, shell=False, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            if self._probing:
                raise
            hint = "; run `engram isolation check`"
            if isinstance(exc, OSError) and exc.strerror is not None:
                exc.strerror += hint
            elif isinstance(exc, (subprocess.TimeoutExpired, subprocess.CalledProcessError)):
                exc.cmd = str(exc.cmd) + hint
            else:
                exc.args = (str(exc) + hint, *exc.args[1:])
            raise

    def _checked(self, argv: list[str], timeout: float):
        result = self._run(argv, timeout)
        if result.returncode != 0:
            hint = "" if self._probing else "; run `engram isolation check`"
            raise RuntimeError(f"{argv[0]} {argv[1]} failed with process exit {result.returncode}{hint}")
        return result

    def _instances(self, timeout: float) -> set[str]:
        result = self._checked(["wsb.exe", "list", "--raw"], timeout)
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or not isinstance(data.get("WindowsSandboxEnvironments"), list):
            raise ValueError("invalid raw Sandbox environment list")
        ids = set()
        for item in data["WindowsSandboxEnvironments"]:
            if not isinstance(item, dict) or not isinstance(item.get("Id"), str):
                raise ValueError("invalid Sandbox environment ID")
            identifier = str(UUID(item["Id"]))
            if identifier in ids:
                raise ValueError("duplicate Sandbox environment ID")
            ids.add(identifier)
        return ids

    def detect(self) -> Availability:
        def probe():
            try:
                self._instances(self.probe_timeout)
            except Exception as exc:
                code = "WSB_CLI_MISSING" if isinstance(exc, FileNotFoundError) else "PROBE_ERROR"
                # Supplemental read-only probe returns our own numeric exit codes.
                # OS SKU and feature State are structured values, not translated text.
                try:
                    diagnostic = self._run([
                        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        "$ErrorActionPreference='Stop'; try { "
                        "$sku=(Get-CimInstance Win32_OperatingSystem).OperatingSystemSKU; "
                        "if ($sku -in 98,99,100,101) { exit 20 }; "
                        "$feature=Get-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM; "
                        "if ($feature.State -eq [Microsoft.Dism.Commands.FeatureState]::Disabled) { exit 21 }; "
                        "exit 0 } catch { exit 22 }",
                    ], self.probe_timeout)
                    code = {20: "WSB_UNSUPPORTED_EDITION", 21: "WSB_FEATURE_DISABLED"}.get(diagnostic.returncode, code)
                except Exception:
                    pass
                return Availability("UNAVAILABLE", f"Probe failed: {type(exc).__name__}: {exc}",
                                    Capabilities("windows-sandbox", False, 0), code)
            self._checked(["wsb.exe", "stop", "--help"], self.probe_timeout)
            self._cli = all([
                self._run(["wsb.exe", "start", "--help"], self.probe_timeout).returncode == 0,
                self._run(["wsb.exe", "exec", "--help"], self.probe_timeout).returncode == 0,
            ])
            if not self._cli:
                self._checked(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                               "Get-Command WindowsSandbox.exe -ErrorAction Stop | Out-Null"],
                              self.probe_timeout)
            mode = "CLI" if self._cli else ".wsb LogonCommand fallback"
            return Availability("AVAILABLE", f"Raw lifecycle probes succeeded; {mode}; guest evidence capture",
                                Capabilities("windows-sandbox", True, self.observed_concurrency), "OK")
        self._probing = True
        try:
            self._availability = probe_availability(probe, backend="windows-sandbox")
        finally:
            self._probing = False
        return self._availability

    def _reserve(self, concurrency: int):
        self.lock_root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout
        while True:
            for slot in range(concurrency):
                lease = (self.lock_root / f"slot-{slot}.lock").open("a+b")
                try:
                    if os.name == "nt":
                        import msvcrt
                        lease.seek(0, 2)
                        if lease.tell() == 0:
                            lease.write(b"0")
                            lease.flush()
                        lease.seek(0)
                        msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return lease
                except OSError:
                    lease.close()
            if time.monotonic() >= deadline:
                raise TimeoutError("Sandbox capacity is reserved by another job for this user")
            time.sleep(self.poll_interval)

    @staticmethod
    def _mapped_path(path: Path) -> Path:
        text = str(path)
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or c in '<>"|?*' for c in text):
            raise ValueError("unsafe mapped path characters")
        if ":" in text[2:] or text.startswith(("\\\\", "//")):
            raise ValueError("network, device or alternate-stream mappings are unsupported")
        if any(part.endswith((" ", ".")) for part in Path(path).parts):
            raise ValueError("ambiguous mapped path component")
        return Path(path).resolve()

    def _guest(self, suffix: str) -> str:
        root = PureWindowsPath(self.guest_root)
        if not root.is_absolute() or root.drive.startswith("\\\\") or any(
            ord(c) < 32 or c in '<>"|?*' for c in str(root)
        ) or any(part == ".." or ":" in part or part.endswith((" ", ".")) for part in root.parts[1:]):
            raise ValueError("guest_root must be an absolute Windows path")
        return str(root / suffix)

    def _config(self, job: _Job, command: str | None = None) -> str:
        root = ET.Element("Configuration")
        for name, enabled in (("Networking", job.profile.network),
                              ("ClipboardRedirection", job.profile.clipboard), ("VGpu", job.profile.vgpu)):
            ET.SubElement(root, name).text = "Enable" if enabled else "Disable"
        mounts = ET.SubElement(root, "MappedFolders")
        entries = [(path, self._guest(f"input-{i}"), True) for i, path in enumerate(job.inputs)]
        entries.append((job.handle.evidence_root, self._guest("evidence"), False))
        if job.workspace is not None:
            entries.append((job.workspace, self._guest("workspace"), job.profile.workspace_access == "read-only"))
        for host, guest, readonly in entries:
            mount = ET.SubElement(mounts, "MappedFolder")
            for name, text in (("HostFolder", str(host)), ("SandboxFolder", guest),
                               ("ReadOnly", str(readonly).lower())):
                ET.SubElement(mount, name).text = text
        if command:
            ET.SubElement(ET.SubElement(root, "LogonCommand"), "Command").text = command
        return ET.tostring(root, encoding="unicode")

    def create(self, profile: Profile, inputs: Sequence[Path], evidence_root: Path) -> Handle:
        if not isinstance(profile, Profile):
            raise ValueError("create requires a validated Profile")
        # Revalidate even if a caller bypassed the frozen record's normal constructor.
        Profile(**{key: value for key, value in vars(profile).items() if key != "warnings"})
        paths = tuple(self._mapped_path(Path(p)) for p in inputs)
        evidence = self._mapped_path(Path(evidence_root))
        workspace = None
        if profile.workspace_access != "none":
            if self.workspace is None:
                raise ValueError("dev workspace access requires an explicit workspace directory")
            workspace = self._mapped_path(Path(self.workspace))
        mounts = [*paths, evidence, *([workspace] if workspace else [])]
        for index, path in enumerate(mounts):
            if any(path.is_relative_to(other) or other.is_relative_to(path) for other in mounts[:index]):
                raise ValueError("input/workspace/evidence mounts overlap")
        if any(not p.is_dir() for p in (*paths, *([workspace] if workspace else []))):
            raise ValueError("mapped inputs and workspace must be existing directories")
        availability = self._availability or self.detect()
        if availability.status != "AVAILABLE":
            raise RuntimeError(availability.reason + "; run `engram isolation check`")
        lease = self._reserve(availability.capabilities.concurrency)
        handle = Handle(uuid4().hex, evidence / uuid4().hex)
        job = _Job(handle, profile, paths, workspace, lease, self._cli)
        self._jobs[handle.id] = job
        before = None
        try:
            before = self._instances(self.lifecycle_timeout)
            if len(before) >= availability.capabilities.concurrency:
                raise RuntimeError("Sandbox user capacity is occupied outside this provider")
            handle.evidence_root.mkdir(parents=True, exist_ok=False)
            config = self._config(job)
            if job.cli:
                job.launch_before = before
                result = self._checked(["wsb.exe", "start", "--raw", "--config", config], self.lifecycle_timeout)
                job.instance = str(UUID(json.loads(result.stdout)["Id"]))
                if job.instance in before:
                    job.instance = None
                    raise RuntimeError("start returned an existing Sandbox ID")
                job.launch_before = None
            return handle
        except Exception:
            self._recover_start(job, before)
            self.destroy(handle)
            raise

    def _recover_start(self, job: _Job, before: set[str] | None) -> None:
        if job.instance is None and before is not None:
            added = self._instances(self.lifecycle_timeout) - before
            if len(added) > 1:
                raise SandboxLifecycleError("Ambiguous Sandbox launch; reservation retained", job.handle)
            if added:
                job.instance = added.pop()
                job.launch_before = None

    def _job(self, handle: Handle) -> _Job:
        job = self._jobs.get(handle.id)
        if job is None or job.handle != handle:
            raise ValueError("unknown Sandbox handle")
        return job

    @staticmethod
    def _literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _command(self, job: _Job, execution_id: str, argv: Sequence[str]) -> str:
        literal = self._literal
        directory = self._guest("evidence/" + execution_id)
        arguments = " -ArgumentList " + literal(subprocess.list2cmdline(list(argv[1:]))) if len(argv) > 1 else ""
        script = f"""$ErrorActionPreference = 'Stop'
$directory = {literal(directory)}
$stdout = Join-Path $directory 'stdout.log'
$stderr = Join-Path $directory 'stderr.log'
$code = 1
try {{
    $process = Start-Process -FilePath {literal(argv[0])}{arguments} -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $code = $process.ExitCode
}} catch {{
    [IO.File]::WriteAllText($stderr, $_.ToString())
}} finally {{
    if (!(Test-Path $stdout)) {{ [IO.File]::WriteAllText($stdout, '') }}
    if (!(Test-Path $stderr)) {{ [IO.File]::WriteAllText($stderr, '') }}
}}
$outcome = if ($code -eq 0) {{ 'passed' }} else {{ 'failed' }}
$result = @{{schema_version=1; handle_id={literal(job.handle.id)}; execution_id={literal(execution_id)}; complete=$true; outcome=$outcome; exit_code=[int]$code; log_refs=@('stdout.log','stderr.log')}} | ConvertTo-Json -Compress
$pending = Join-Path $directory 'result.json.tmp'
$bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($result)
$stream = [IO.File]::Open($pending, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {{ $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }} finally {{ $stream.Dispose() }}
Move-Item -LiteralPath $pending -Destination (Join-Path $directory 'result.json') -ErrorAction Stop
exit $code
"""
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        return "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + encoded

    def exec(self, handle: Handle, argv: Sequence[str], timeout: float) -> ExecResult:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("execution timeout must be finite and positive")
        if not argv or isinstance(argv, (str, bytes)) or any(not isinstance(a, str) or "\x00" in a for a in argv) or not argv[0]:
            raise ValueError("argv must contain a guest executable and valid string arguments")
        job = self._job(handle)
        if job.destroyed or (not job.cli and job.executions):
            raise ValueError("destroyed or already executed fallback handle")
        execution_id = uuid4().hex
        directory = handle.evidence_root / execution_id
        directory.mkdir(exist_ok=False)
        job.executions.add(execution_id)
        deadline = time.monotonic() + timeout
        command = self._command(job, execution_id, argv)
        try:
            if job.cli:
                # Exec's localized text and process exit code do not replace guest evidence.
                self._run(["wsb.exe", "exec", "--id", job.instance, "-c", command, "-r", "System"], timeout)
            else:
                before = self._instances(min(timeout, self.lifecycle_timeout))
                config = handle.evidence_root / "sandbox.wsb"
                config.write_text(self._config(job, command), encoding="utf-8", newline="\n")
                launch = "Start-Process -FilePath WindowsSandbox.exe -ArgumentList " + self._literal('"' + str(config) + '"') + " -WindowStyle Hidden -ErrorAction Stop"
                job.launch_before = before
                try:
                    self._checked(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", launch], max(0.001, deadline - time.monotonic()))
                finally:
                    self._recover_start(job, before)
                if job.instance is None:
                    while job.instance is None and time.monotonic() < deadline:
                        time.sleep(self.poll_interval)
                        self._recover_start(job, before)
                    if job.instance is None:
                        raise subprocess.TimeoutExpired("Sandbox launch", timeout)
            while not (directory / "result.json").exists():
                if time.monotonic() >= deadline:
                    if not job.cli:
                        raise subprocess.TimeoutExpired("LogonCommand", timeout)
                    raise EvidenceValidationError("Guest did not publish canonical result.json")
                time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
            evidence = self.collect_evidence(handle, execution_id)
            status = {"timed-out": "TIMED_OUT", "cancelled": "CANCELLED"}.get(evidence.outcome, "COMPLETED")
            return ExecResult(evidence.exit_code, execution_id, status)
        except subprocess.TimeoutExpired:
            self.destroy(handle)
            return ExecResult(None, execution_id, "TIMED_OUT")
        except Exception:
            self.destroy(handle)
            raise

    def collect_evidence(self, handle: Handle, execution_id: str) -> Evidence:
        job = self._job(handle)
        if execution_id not in job.executions:
            raise EvidenceValidationError("execution ID does not belong to this handle")
        return collect_guest_evidence(handle, execution_id)

    def destroy(self, handle: Handle) -> None:
        job = self._job(handle)
        if job.destroyed:
            return
        if job.launch_before is not None:
            self._recover_start(job, job.launch_before)
            if job.instance is None:
                raise SandboxLifecycleError("Launch completion is unknown; reservation retained", handle)
        if job.instance is not None:
            self._checked(["wsb.exe", "stop", "--id", job.instance], self.lifecycle_timeout)
            deadline = time.monotonic() + self.lifecycle_timeout
            while job.instance in self._instances(max(0.001, deadline - time.monotonic())):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Sandbox remains listed after stop; reservation retained; run `engram isolation check`")
                time.sleep(self.poll_interval)
        job.lease.close()
        job.destroyed = True
