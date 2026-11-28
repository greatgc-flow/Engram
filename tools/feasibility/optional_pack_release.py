"""Signed TEST_ONLY release admission, materialization and isolated execution."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import file_digest, sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from tempfile import TemporaryDirectory, TemporaryFile
from time import monotonic
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from core.python_registry import _plain as _system_path
from optional_pack_group import _activation, _execution_lease, _fixture_root, publish, retire

from optional_pack_catalog import _KEY, decode_document

_MAX_ARCHIVE = 8 * 1024 * 1024
_MAX_EXPANDED = 16 * 1024 * 1024
_MAX_MEMBERS = 256
_MAX_OUTPUT = 65536
_PATH = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")
_DEVICE = re.compile(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", re.IGNORECASE)
_DIGEST = re.compile(r"[a-f0-9]{64}")
_FIELDS = set("""fixture_only schema_version package_id version profile host manager_protocol artifact_ref
artifact_sha256 artifact_bytes expanded_bytes members runtime_lock_sha256 sbom_sha256 license_evidence_ref
signing_key_id signature_ref app_entry_rel adapter_entry_rel read_schema_min read_schema_max""".split())


@dataclass(frozen=True)
class TrustPolicy:
    openssl: Path
    openssl_sha256: str
    key_id: str
    public_pem: bytes
    valid_until: datetime
    revoked: bool
    runtime_lock_sha256: str
    sbom_sha256: str
    license_ref: str


@dataclass(frozen=True)
class AdmittedRelease:
    manifest_sha256: str
    entry: str
    adapter_entry: str | None
    package: str
    policy: TrustPolicy
    members: tuple[tuple[str, bytes], ...]


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _plain(path):
    info = path.lstat()
    return not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or stat.S_ISLNK(info.st_mode))


def _environment():
    return {key: value for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}


def _pin_executable(path, expected):
    _need(path.is_absolute() and path.is_file() and _plain(path), "expected exact ordinary executable path")
    with path.open("rb") as stream:
        _need(file_digest(stream, "sha256").hexdigest() == expected, "executable pin mismatch")


def _fresh(policy, now):
    _need(isinstance(now, datetime) and now.utcoffset() == timedelta(0)
          and isinstance(policy.valid_until, datetime) and policy.valid_until.utcoffset() == timedelta(0)
          and policy.revoked is False and now < policy.valid_until, "publisher trust is expired or revoked")


def _verify(policy, manifest, signature, now):
    _fresh(policy, now)
    _need(type(signature) is bytes and len(signature) == 64, "invalid Ed25519 signature size")
    _need(type(policy.public_pem) is bytes and 0 < len(policy.public_pem) <= 4096, "invalid publisher key")
    _pin_executable(policy.openssl, policy.openssl_sha256)
    with TemporaryDirectory(prefix="engram-release-trust-") as tmp:
        root = Path(tmp)
        (root / "public.pem").write_bytes(policy.public_pem)
        (root / "manifest.json").write_bytes(manifest)
        (root / "manifest.sig").write_bytes(signature)
        (root / "openssl.cnf").touch()
        environment = _environment() | {"OPENSSL_CONF": str(root / "openssl.cnf")}
        result = subprocess.run([policy.openssl, "pkeyutl", "-verify", "-pubin", "-inkey", "public.pem",
                                 "-rawin", "-in", "manifest.json", "-sigfile", "manifest.sig"],
                                cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        _need(result.returncode == 0, "detached signature verification failed")


def _path(value):
    _need(type(value) is str and 0 < len(value) <= 240, "invalid release member path")
    parts = value.split("/")
    _need(all(_PATH.fullmatch(p) and not p.endswith(".")
              and not _DEVICE.fullmatch(p.split(".", 1)[0]) for p in parts), "unsafe release member path")
    return parts


def _dig(value):
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _size(value, maximum, minimum=0):
    return type(value) is int and minimum <= value <= maximum


def _inventory(doc):
    raw = doc["members"]
    _need(type(raw) is list and 0 < len(raw) <= _MAX_MEMBERS, "invalid release inventory size")
    seen, files = {}, {}
    for row in raw:
        _need(type(row) is dict and row.keys() == {"path_rel", "sha256", "bytes", "asset_class"}
              and row["asset_class"] == "PROGRAM" and _dig(row["sha256"])
              and _size(row["bytes"], _MAX_EXPANDED), "invalid release member declaration")
        name = row["path_rel"]
        parts = _path(name)
        for count in range(1, len(parts) + 1):
            path = "/".join(parts[:count])
            member = count == len(parts)
            folded = path.casefold()
            if folded in seen:
                _need(not member and seen[folded] == (path, False), "release path collision")
            seen[folded] = (path, member)
        files[name] = row
    required = [doc["app_entry_rel"]]
    if doc["adapter_entry_rel"] is not None:
        required.append(doc["adapter_entry_rel"])
    for entry in required:
        _path(entry)
        _need(entry.endswith(".py") and entry in files, "signed Python entry must be an exact member")
    _need(_size(doc["expanded_bytes"], _MAX_EXPANDED, 1)
          and sum(row["bytes"] for row in files.values()) == doc["expanded_bytes"], "expanded byte total mismatch")
    return files


def admit(descriptor, policy, manifest, signature, archive, manifest_sha256, now):
    """Validate all inputs before writes to a generation root."""
    doc = decode_document(manifest)
    _need(type(doc) is dict and doc.keys() == _FIELDS, "unexpected release manifest contract")
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    digest = sha256(manifest).hexdigest()
    _need(manifest == canonical and digest == manifest_sha256, "manifest bytes differ from reviewed plan")
    _need(doc["fixture_only"] is True and doc["schema_version"] == doc["manager_protocol"] == "1.0"
          and doc["host"] == "windows-x64" and doc["package_id"] == descriptor.package_id
          and doc["profile"] in [p.id for p in descriptor.profiles], "wrong release identity or protocol")
    for field in ("artifact_ref", "license_evidence_ref", "signing_key_id", "signature_ref"):
        _need(type(doc[field]) is str and _KEY.fullmatch(doc[field]), "invalid manifest identifier")
    _need(type(doc["version"]) is str and re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)",
                                                     doc["version"]), "invalid version")
    _need(all(type(doc[key]) is int for key in ("read_schema_min", "read_schema_max"))
          and 0 <= doc["read_schema_min"] <= doc["read_schema_max"], "invalid schema range")
    _need(doc["signing_key_id"] == policy.key_id and doc["signing_key_id"] in descriptor.trust_key_ids
          and _dig(doc["runtime_lock_sha256"]) and doc["runtime_lock_sha256"] == policy.runtime_lock_sha256
          and _dig(doc["sbom_sha256"]) and doc["sbom_sha256"] == policy.sbom_sha256
          and doc["license_evidence_ref"] == policy.license_ref, "release differs from pinned trust evidence")
    _need(type(archive) is bytes and _size(doc["artifact_bytes"], _MAX_ARCHIVE, 1)
          and len(archive) == doc["artifact_bytes"] and sha256(archive).hexdigest() == doc["artifact_sha256"],
          "archive bytes or digest mismatch")
    files = _inventory(doc)
    _verify(policy, manifest, signature, now)

    try:
        with ZipFile(BytesIO(archive)) as zipped:
            info = zipped.infolist()
            _need(len(info) == len(files) and {row.filename for row in info} == files.keys(),
                  "archive members differ from signed inventory")
            members = []
            for entry in info:
                row = files[entry.filename]
                unix_type = stat.S_IFMT(entry.external_attr >> 16)
                _need(entry.orig_filename == entry.filename and unix_type in (0, stat.S_IFREG)
                      and not entry.flag_bits & 1 and entry.file_size == row["bytes"],
                      "unsupported archive member or declared size")
                with zipped.open(entry) as stream:
                    data = stream.read(row["bytes"] + 1)
                _need(len(data) == row["bytes"] and sha256(data).hexdigest() == row["sha256"],
                      "archive member differs from signed bytes")
                members.append((entry.filename, data))
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("invalid release archive") from exc
    return AdmittedRelease(digest, doc["app_entry_rel"], doc["adapter_entry_rel"],
                           descriptor.package_id, policy, tuple(sorted(members)))


def stage(release, root):
    """Write the admitted, exact members to a fresh generation directory."""
    root.mkdir()
    try:
        for name, data in release.members:
            path = root.joinpath(*_path(name))
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
    except BaseException:
        shutil.rmtree(root)
        raise


def _staged_members(root):
    _need(root.is_dir() and _plain(root), "invalid staged generation")
    for path in root.iterdir():
        _need(_plain(path), "staged generation contains a link or reparse point")
        if path.is_dir():
            yield from _staged_members(path)
        else:
            _need(path.is_file(), "unsupported staged generation member")
            yield path


def _verified_paths(release, root):
    expected = dict(release.members)
    observed = {p.relative_to(root).as_posix(): p for p in _staged_members(root)}
    _need(observed.keys() == expected.keys(), "staged generation inventory mismatch")
    for name, data in expected.items():
        with observed[name].open("rb") as stream:
            _need(stream.read(len(data) + 1) == data, "staged release bytes changed")
    return observed


def _run(release, root, executable, executable_sha256, guard, entry, args, wire, timeout=30):
    _pin_executable(executable, executable_sha256)
    end = monotonic() + timeout

    def remaining():
        delay = end - monotonic()
        if delay <= 0:
            raise subprocess.TimeoutExpired(entry, timeout)
        return delay

    with TemporaryFile() as stdin, ExitStack() as child_scope:
        if wire is not None:
            stdin.write(wire)
            stdin.seek(0)
        with guard:
            paths = _verified_paths(release, root)
            remaining()
            child = child_scope.enter_context(subprocess.Popen(
                [executable, "-I", "-B", "-S", paths[entry], *args], cwd=root,
                env=_environment(), stdin=subprocess.DEVNULL if wire is None else stdin,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL))
        with ThreadPoolExecutor(max_workers=1) as reader:
            pending = reader.submit(child.stdout.read, _MAX_OUTPUT + 1)
            try:
                try:
                    output = pending.result(timeout=remaining())
                except TimeoutError as exc:
                    raise subprocess.TimeoutExpired(entry, timeout) from exc
                _need(len(output) <= _MAX_OUTPUT, "signed fixture output exceeds its limit")
                _need(child.wait(timeout=remaining()) == 0, "signed fixture entry did not complete")
            except BaseException:
                child.kill()
                child.wait()
                raise
    return output


def run_staged(release, root, executable, executable_sha256):
    """Run the pinned signed entry from an ordinary verified fixture generation."""
    return _run(release, root, executable, executable_sha256, nullcontext(), release.entry, (), None)


def _generation_rel(descriptor, release):
    return f"{descriptor.slot_rel}/app/generations/gen-{release.manifest_sha256}"


def _admitted(root, descriptor, release, policy, now):
    _fixture_root(root)
    _need(release.package == descriptor.package_id and release.policy == policy, "changed release trust")
    _fresh(policy, now)
    return _system_path(root, _generation_rel(descriptor, release))


def install_signed(root, descriptor, expected_revision, runtime_id, release, *, policy, now,
                   registry_proposal=None, crash_after=None, reuse_retained=False):
    """Stage only an admitted release and publish its manifest digest through the existing journal."""
    def materialize():
        generation = _admitted(root, descriptor, release, policy, now)
        generation.parent.mkdir(parents=True, exist_ok=True)
        try:
            stage(release, generation)
        except FileExistsError:
            _verified_paths(release, generation)

    marker = BytesIO()
    with ZipFile(marker, "w", compression=ZIP_STORED) as archive:
        archive.writestr("app.txt", release.manifest_sha256.encode("ascii"))
    raw = marker.getvalue()
    return publish(root, descriptor, expected_revision, runtime_id, raw, sha256(raw).hexdigest(),
                   registry_proposal=registry_proposal, crash_after=crash_after,
                   reuse_retained=reuse_retained, verify_artifact=materialize)


def remove_signed(root, descriptor, expected_revision, release, *, policy, now, crash_after=None):
    """Retire a verified active fixture generation with user data and rollback assets retained."""
    def verify():
        _verified_paths(release, _admitted(root, descriptor, release, policy, now))

    return retire(root, descriptor, expected_revision, release.manifest_sha256.encode("ascii"),
                  verify_artifact=verify, crash_after=crash_after)


@contextmanager
def _signed_activation(root, descriptor, release, execution):
    with _activation(root, descriptor) as active:
        _need(active is not None and active[2] == release.manifest_sha256.encode("ascii"),
              "release is outside the active signed generation")
        execution.enter_context(_execution_lease(root, descriptor.package_id, active[0]))
        yield


def launch_signed(root, descriptor, release, executable, executable_sha256, *, policy, now):
    generation = _admitted(root, descriptor, release, policy, now)
    with ExitStack() as execution:
        return _run(release, generation, executable, executable_sha256,
                    _signed_activation(root, descriptor, release, execution), release.entry, (), None)


_ECHO = ("fixture_only", "schema_version", "protocol_version", "request_id", "parent_op_id",
         "installation_id", "package_id", "generation", "operation")


class AdapterOutcomeUnknown(ValueError):
    """An effectful adapter started without trustworthy completion evidence."""


def _reply(raw, request, *, effectful):
    reply = decode_document(raw)
    _need(type(reply) is dict and reply.keys() == set(_ECHO) | {"status", "findings", "receipt", "next_action"}
          and reply["fixture_only"] is True and all(reply[k] == request[k] for k in _ECHO),
          "adapter response echo does not match")
    status = reply["status"]
    _need(status in ("OK", "BLOCKED", "UNSUPPORTED", "UNKNOWN", "FAILED")
          and reply["next_action"] in ("NONE", "REPLAN", "RECONCILE", "REPAIR", "STOP"),
          "invalid adapter outcome")
    findings = reply["findings"]
    _need(type(findings) is list and len(findings) <= 32, "bad finding count")
    for item in findings:
        _need(type(item) is dict and item.keys() == {"code", "message"}
              and type(item["code"]) is str and _KEY.fullmatch(item["code"])
              and type(item["message"]) is str and 0 < len(item["message"]) <= 512, "invalid finding")
    receipt = reply["receipt"]
    if status == "OK" or receipt is not None:
        _need(type(receipt) is dict and receipt.keys() == {"effect_id", "checkpoint_sha256",
                                                         "observed_state", "owned_process_ids"}
              and type(receipt["effect_id"]) is str and _KEY.fullmatch(receipt["effect_id"])
              and receipt["observed_state"] in ("NEW", "OLD", "UNCHANGED", "UNKNOWN")
              and receipt["owned_process_ids"] == []
              and (receipt["checkpoint_sha256"] is None or _dig(receipt["checkpoint_sha256"])),
              "invalid fixture receipt")
        if status == "OK":
            expected = "NEW" if effectful else "UNCHANGED"
            _need(reply["next_action"] == "NONE" and receipt["observed_state"] == expected
                  and (receipt["checkpoint_sha256"] is not None) == effectful,
                  "successful adapter reply lacks operation evidence")
    return reply


def launch_adapter(root, descriptor, release, executable, executable_sha256, request, args, *, policy, now):
    """Run an admitted adapter and validate one v1 response against its request."""
    generation = _admitted(root, descriptor, release, policy, now)
    rel = _generation_rel(descriptor, release)
    _need(type(request) is dict and request.keys() == set(_ECHO) | {
        "phase", "plan_digest", "scope", "deadline", "working_rel", "checkpoint_rel"},
        "unknown adapter request shape")
    _need(release.adapter_entry is not None and request["fixture_only"] is True
          and request["protocol_version"] == request["schema_version"] == "1.0"
          and request["package_id"] == descriptor.package_id and request["working_rel"] == rel
          and request["generation"] == rel.rsplit("/", 1)[1]
          and request["operation"] in descriptor.operations
          and _dig(request["plan_digest"])
          and all(type(request[k]) is str and _KEY.fullmatch(request[k])
                  for k in ("request_id", "parent_op_id", "installation_id"))
          and type(request["deadline"]) is str, "adapter request does not match signed generation")
    deadline = datetime.fromisoformat(request["deadline"])
    _need(deadline.utcoffset() == timedelta(0) and now < deadline, "expired adapter request")
    wire = json.dumps(request, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
    _need(len(wire) <= _MAX_OUTPUT, "oversized adapter request")
    effectful = request["operation"] in ("checkpoint", "restore", "migrate", "relocate")
    try:
        with ExitStack() as execution:
            raw = _run(release, generation, executable, executable_sha256,
                       _signed_activation(root, descriptor, release, execution), release.adapter_entry, args, wire,
                       timeout=min(30, (deadline - now).total_seconds()))
            return _reply(raw, request, effectful=effectful)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        if effectful:
            raise AdapterOutcomeUnknown("fixture effect needs reconciliation") from exc
        raise
