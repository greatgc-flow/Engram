"""Ephemeral WSL2 Linux compatibility and reproducibility provider.

NEVER security-equivalent to Windows Sandbox: Windows filesystem, executable
and network interop remain possible. Profile network=False is NOT enforced.
Read-only input binds are workflow constraints, bypassable by guest root.
The first input is a caller-supplied rootfs tar (never downloaded); subsequent
inputs are directories exposed as read-only /engram/input-N bind mounts.
Linux work should use the distro's ext4 filesystem, not host mounts.

Import -> exec -> collect -> optional caller export (outside this port) ->
unregister. Each import uses a unique private name. A private rootfs copy adds
wsl.conf BEFORE first boot: automount and executable interop explicitly enabled,
Windows PATH injection disabled. Only evidence needs a writable host mount.
wslpath inside the distro resolves mounts; no drive/mount prefix is assumed.
Durable evidence stays on the host before unregister destroys the distro.

Measured with Alpine 3.20 on WSL 3.0.1: wsl.exe passes guest arguments through
a shell. Backslashes in Windows paths are consumed; forward slashes, spaces
and Korean letters work, but quotes, dollar signs, ampersands and parentheses
cause parsing errors or expansion. Host paths entering that shell are normalized
to forward slashes and allow only letters/digits (including non-ASCII), spaces
and _ . - / :. Unsupported characters are rejected before any WSL call;
escaping is not attempted. Direct --import paths do not enter the guest shell
and are not subject to this allowlist. Measured guest scripts passed via sh -c
argv are also mangled by shell reparsing. Setup and execution scripts instead
reach sh on stdin as UTF-8 bytes with LF newlines; shell syntax and quoted guest
arguments survive this transport, and the guest exit code propagates.

Imports explicitly request --version 2, independent of the host default version.
Detection requires both --version and --status to exit zero. No localized command
text is interpreted as success. An ambiguous import retains its reservation
and exposes a retry handle, but is never claimed or unregistered by inference.
"""
from __future__ import annotations

import io
import math
import os
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence
from uuid import uuid4

from _sys.core.isolation import (
    Availability, Capabilities, Evidence, EvidenceValidationError, ExecResult,
    Handle, Profile, collect_guest_evidence, probe_availability,
)


_LIMITATIONS = (
    "Linux compatibility/reproducibility only; not security-equivalent to Sandbox; "
    "Windows filesystem/executable/network interop remains possible; no network enforcement; "
    "parallel private distros supported, serialized default"
)
_WSL_CONF = b"[automount]\nenabled=true\n[interop]\nenabled=true\nappendWindowsPath=false\n"


@dataclass
class _Job:
    handle: Handle
    name: str
    lease: object
    created: bool = False
    uncertain: bool = False
    destroyed: bool = False
    unregister_returned: bool = False
    guest_evidence: str = ""
    executions: set[str] = field(default_factory=set)


class WSLLifecycleError(RuntimeError):
    """Cleanup failed or ownership is uncertain; reservation remains retained."""

    def __init__(self, message: str, handle: Handle) -> None:
        super().__init__(message + "; run `engram isolation check`")
        self.handle = handle


class WSL2Provider:
    """IsolationProvider implementation with injected subprocess runner.

    Capabilities.capture=True describes pipe capture, not a security boundary.
    Availability.reason always carries the interop/network limitations. File
    leases serialize lifecycle jobs by default; explicit concurrency > 1 allows
    independent distros. Supplied archives are copied, never modified/extracted
    on the host. No global WSL configuration or user distro is modified.
    """

    def __init__(
        self, *, runner: Callable = subprocess.run, workspace: Path | None = None,
        lock_root: Path | None = None, probe_timeout: float = 5,
        lifecycle_timeout: float = 30, observed_concurrency: int = 1,
    ) -> None:
        self.runner = runner
        self.workspace = workspace
        self.lock_root = Path(lock_root or Path(tempfile.gettempdir()) / "engram-wsl2")
        self.probe_timeout = probe_timeout
        self.lifecycle_timeout = lifecycle_timeout
        self.observed_concurrency = observed_concurrency
        self._probing = False
        self._availability: Availability | None = None
        self._jobs: dict[str, _Job] = {}

    def _run(self, argv: list[str], timeout: float, input: bytes | None = None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("process timeout must be finite and positive")
        # Omit input for ordinary commands to preserve existing runner signatures.
        kwargs = {} if input is None else {"input": input}
        try:
            return self.runner(argv, timeout=timeout, shell=False, capture_output=True, check=False, **kwargs)
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

    def _checked(self, argv: list[str], timeout: float, input: bytes | None = None):
        result = self._run(argv, timeout, input)
        if result.returncode != 0:
            hint = "" if self._probing else "; run `engram isolation check`"
            raise RuntimeError(f"{argv[0]} {argv[1]} failed with process exit {result.returncode}{hint}")
        return result

    @staticmethod
    def _decode(output: bytes | str) -> str:
        if isinstance(output, bytes):
            if output.startswith((b"\xff\xfe", b"\xfe\xff")):
                output = output.decode("utf-16")
            elif b"\x00" in output and len(output) % 2 == 0:
                output = output.decode("utf-16-le")
            else:
                try:
                    output = output.decode("utf-8-sig")
                except UnicodeDecodeError:
                    # UTF-16 names can consist entirely of non-ASCII code units
                    # and contain no NUL bytes. Strict decoding rejects damage.
                    output = output.decode("utf-16-le")
        if not isinstance(output, str):
            raise ValueError("invalid WSL output")
        return output.replace("\x00", "").lstrip("\ufeff")

    def _names(self) -> set[str]:
        text = self._decode(self._checked(["wsl.exe", "-l", "-q"], self.lifecycle_timeout).stdout)
        names = [line.strip() for line in text.splitlines() if line.strip()]
        if any(any(ord(c) < 32 or c == "\ufffd" for c in name) for name in names):
            raise ValueError("invalid WSL distro list")
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("duplicate WSL distro names")
        return {name.casefold() for name in names}

    def detect(self) -> Availability:
        def probe():
            for command in ("--version", "--status"):
                try:
                    result = self._run(["wsl.exe", command], self.probe_timeout)
                except FileNotFoundError as exc:
                    return Availability("UNAVAILABLE", f"Probe failed: {type(exc).__name__}: {exc}",
                                        Capabilities("wsl2", False, 0), "WSL_NOT_INSTALLED")
                except (OSError, subprocess.SubprocessError) as exc:
                    code = "WSL_NOT_INSTALLED" if isinstance(exc, subprocess.CalledProcessError) and exc.returncode & 0xffffffff == 0x8007019e else "WSL_PROBE_FAILED"
                    return Availability("UNAVAILABLE", f"Probe failed: {type(exc).__name__}: {exc}",
                                        Capabilities("wsl2", False, 0), code)
                if result.returncode != 0:
                    # Normalize signed Windows HRESULTs; never inspect localized output.
                    code = "WSL_NOT_INSTALLED" if result.returncode & 0xffffffff == 0x8007019e else "WSL_PROBE_FAILED"
                    return Availability("UNAVAILABLE",
                                        f"Probe failed: RuntimeError: wsl.exe {command} failed with process exit {result.returncode}",
                                        Capabilities("wsl2", False, 0), code)
            return Availability("AVAILABLE", _LIMITATIONS,
                                Capabilities("wsl2", True, self.observed_concurrency), "OK")
        self._probing = True
        try:
            availability = probe_availability(probe, backend="wsl2")
        finally:
            self._probing = False
        if availability.status == "UNAVAILABLE":
            availability = Availability(availability.status, availability.reason + "; " + _LIMITATIONS,
                                        availability.capabilities, availability.code)
        self._availability = availability
        return availability

    def _reserve(self, concurrency: int):
        self.lock_root.mkdir(parents=True, exist_ok=True)
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
        raise TimeoutError("WSL2 capacity is reserved by another provider job")

    @staticmethod
    def _rootfs(source: Path, target: Path) -> None:
        # Copy archive members without host extraction. Refuse symlinked /etc:
        # the generated config must actually be a per-distro regular file.
        with tarfile.open(source, "r:*") as incoming, tarfile.open(target, "w:gz") as outgoing:
            for member in incoming:
                name = str(PurePosixPath(member.name.removeprefix("./"))).rstrip("/")
                if name == "etc" and not member.isdir():
                    raise ValueError("rootfs /etc must be a directory")
                if name == "etc/wsl.conf":
                    continue
                stream = incoming.extractfile(member) if member.isfile() else None
                try:
                    outgoing.addfile(member, stream)
                finally:
                    if stream is not None:
                        stream.close()
            member = tarfile.TarInfo("etc/wsl.conf")
            member.mode, member.size = 0o644, len(_WSL_CONF)
            outgoing.addfile(member, io.BytesIO(_WSL_CONF))

    @staticmethod
    def _host_shell_path(path: Path) -> str:
        normalized = str(path).replace("\\", "/")
        for character in normalized:
            if not (character.isalpha() or character.isdigit() or character in " _.-/:"):
                raise ValueError(
                    f"unsupported host path character {character!r}: "
                    "wsl.exe passes arguments through a shell; "
                    "only letters/digits, space and _ . - / : are allowed"
                )
        return normalized

    def _guest_path(self, job: _Job, path: Path) -> str:
        host = self._host_shell_path(path)
        result = self._checked(["wsl.exe", "-d", job.name, "--", "wslpath", "-a", "-u", host], self.lifecycle_timeout)
        guest = self._decode(result.stdout).strip()
        if not guest.startswith("/") or any(ord(c) < 32 for c in guest):
            raise ValueError("wslpath did not return an absolute guest path")
        return guest

    @staticmethod
    def _script_input(script: str) -> bytes:
        return script.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")

    def _shell(self, job: _Job, script: str, timeout: float):
        return self._checked(["wsl.exe", "-d", job.name, "--", "sh"], timeout,
                             self._script_input(script))

    def create(self, profile: Profile, inputs: Sequence[Path], evidence_root: Path) -> Handle:
        if not isinstance(profile, Profile):
            raise ValueError("create requires a validated Profile")
        Profile(**{key: value for key, value in vars(profile).items() if key != "warnings"})
        # Check raw paths before resolution, which can reject NULs or normalize
        # away unsupported characters. Rootfs/import paths bypass guest shells.
        for path in [*inputs[1:], evidence_root]:
            self._host_shell_path(path)
        paths = tuple(Path(p).resolve(strict=True) for p in inputs)
        if not paths or not paths[0].is_file() or any(not p.is_dir() for p in paths[1:]):
            raise ValueError("first input must be a rootfs tar; remaining inputs must be directories")
        evidence = Path(evidence_root).resolve()
        workspace = None
        if profile.workspace_access != "none":
            if self.workspace is not None:
                self._host_shell_path(self.workspace)
            if self.workspace is None or not Path(self.workspace).is_dir():
                raise ValueError("workspace access requires an explicit existing directory")
            workspace = Path(self.workspace).resolve(strict=True)
        # Resolution can introduce parent or symlink-target path components.
        for path in [*paths[1:], evidence, *([workspace] if workspace else [])]:
            self._host_shell_path(path)
        mounts = [*paths, evidence, *([workspace] if workspace else [])]
        for index, path in enumerate(mounts):
            if any(path.is_relative_to(other) or other.is_relative_to(path) for other in mounts[:index]):
                raise ValueError("input/workspace/evidence paths overlap")
        if any("\x00" in str(p) or "\n" in str(p) or "\r" in str(p) for p in mounts):
            raise ValueError("invalid host path")
        availability = self._availability or self.detect()
        if availability.status != "AVAILABLE":
            raise RuntimeError(availability.reason + "; run `engram isolation check`")
        lease = self._reserve(availability.capabilities.concurrency)
        handle = Handle(uuid4().hex, evidence / uuid4().hex)
        job = _Job(handle, "engram-iso-" + uuid4().hex, lease)
        self._jobs[handle.id] = job
        archive = None
        try:
            if job.name.casefold() in self._names():
                raise RuntimeError("refusing to reuse an existing distro name")
            handle.evidence_root.mkdir(parents=True, exist_ok=False)
            runtime = self.lock_root / "jobs" / handle.id
            runtime.mkdir(parents=True, exist_ok=False)
            archive = runtime / "rootfs.tar.gz"
            self._rootfs(paths[0], archive)
            install = runtime / "distro"
            install.mkdir()
            job.uncertain = True
            self._checked(["wsl.exe", "--import", job.name, str(install), str(archive), "--version", "2"], self.lifecycle_timeout)
            job.created, job.uncertain = True, False
            if job.name.casefold() not in self._names():
                raise RuntimeError("imported distro is not listed")
            job.guest_evidence = self._guest_path(job, handle.evidence_root)
            self._shell(job, "test -d " + shlex.quote(job.guest_evidence) + " && test -w " + shlex.quote(job.guest_evidence), self.lifecycle_timeout)
            entries = [(p, f"/engram/input-{i}", True) for i, p in enumerate(paths[1:])]
            if workspace is not None:
                entries.append((workspace, "/engram/workspace", profile.workspace_access == "read-only"))
            for host, guest, readonly in entries:
                source = shlex.quote(self._guest_path(job, host))
                target = shlex.quote(guest)
                script = f"mkdir -p {target} && mount --bind {source} {target}"
                if readonly:
                    script += f" && mount -o remount,bind,ro {target}"
                self._shell(job, script, self.lifecycle_timeout)
            return handle
        except Exception as exc:
            if job.uncertain:
                raise WSLLifecycleError("Import ownership is uncertain; refusing unregister; reservation retained", handle) from exc
            self.destroy(handle)
            raise
        finally:
            if archive is not None and archive.exists():
                archive.unlink()

    def _job(self, handle: Handle) -> _Job:
        job = self._jobs.get(handle.id)
        if job is None or job.handle != handle:
            raise ValueError("unknown WSL2 handle")
        return job

    def _command(self, job: _Job, execution_id: str, argv: Sequence[str]) -> str:
        directory = shlex.quote(job.guest_evidence + "/" + execution_id)
        # IDs are validated ASCII tokens. Only exit_code/outcome vary at runtime.
        record = ('{"schema_version":1,"handle_id":"' + job.handle.id +
                  '","execution_id":"' + execution_id + '","complete":true,'
                  '"outcome":"%s","exit_code":%s,"log_refs":["stdout.log","stderr.log"]}')
        return f"""directory={directory}
export ENGRAM_EVIDENCE_DIR="$directory"
{shlex.join(argv)} > "$directory/stdout.log" 2> "$directory/stderr.log"
code=$?
outcome=failed
if [ "$code" -eq 0 ]; then outcome=passed; fi
printf {shlex.quote(record)} "$outcome" "$code" > "$directory/result.json.tmp" || exit 125
sync || exit 125
mv -- "$directory/result.json.tmp" "$directory/result.json" || exit 125
sync || exit 125
exit "$code"
"""

    def exec(self, handle: Handle, argv: Sequence[str], timeout: float) -> ExecResult:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("execution timeout must be finite and positive")
        if not argv or isinstance(argv, (str, bytes)) or any(not isinstance(a, str) or "\x00" in a for a in argv) or not argv[0]:
            raise ValueError("argv must contain a guest executable and valid string arguments")
        job = self._job(handle)
        if job.destroyed or not job.created:
            raise ValueError("distro is not active")
        execution_id = uuid4().hex
        (handle.evidence_root / execution_id).mkdir(exist_ok=False)
        job.executions.add(execution_id)
        try:
            # Guest result, not pipe contents or the WSL process exit, is canonical.
            self._run(["wsl.exe", "-d", job.name, "--", "sh"], timeout,
                      self._script_input(self._command(job, execution_id, argv)))
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
        if job.uncertain:
            raise WSLLifecycleError("Cannot unregister a distro without proven job ownership", handle)
        if job.unregister_returned:
            try:
                gone = job.name.casefold() not in self._names()
            except Exception as exc:
                raise WSLLifecycleError("Cannot verify unregister postcondition; reservation retained", handle) from exc
            if gone:
                job.lease.close()
                job.destroyed = True
                return
        evidence_error = None
        if job.created:
            # Terminate first: an exec timeout kills wsl.exe, not necessarily its
            # guest descendants. Never let them write evidence during collection.
            self._checked(["wsl.exe", "--terminate", job.name], self.lifecycle_timeout)
            for execution in job.executions:
                if (handle.evidence_root / execution / "result.json").exists():
                    try:
                        self.collect_evidence(handle, execution)
                    except EvidenceValidationError as exc:
                        evidence_error = exc
            self._checked(["wsl.exe", "--unregister", job.name], self.lifecycle_timeout)
            job.unregister_returned = True
            try:
                remains = job.name.casefold() in self._names()
            except Exception as exc:
                raise WSLLifecycleError("Cannot verify unregister postcondition; reservation retained", handle) from exc
            if remains:
                raise WSLLifecycleError("WSL distro remains listed after unregister; reservation retained", handle)
        job.lease.close()
        job.destroyed = True
        if evidence_error is not None:
            raise evidence_error
