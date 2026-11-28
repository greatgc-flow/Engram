"""Signed TEST_ONLY release admission, materialization and isolated execution."""
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
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from optional_pack_group import _activation, _fixture_root, _path as _group_path, publish

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


def _run(release, root, executable, executable_sha256, guard, entry, args, wire):
    _pin_executable(executable, executable_sha256)
    with TemporaryFile() as stdout, ExitStack() as child_scope:
        with guard:
            paths = _verified_paths(release, root)
            child = child_scope.enter_context(subprocess.Popen(
                [executable, "-I", "-B", "-S", paths[entry], *args], cwd=root,
                env=_environment(), stdin=subprocess.DEVNULL if wire is None else subprocess.PIPE,
                stdout=stdout, stderr=subprocess.DEVNULL))
        try:
            child.communicate(wire, timeout=30)
        except BaseException:
            child.kill()
            child.communicate()
            raise
        stdout.seek(0)
        output = stdout.read(_MAX_OUTPUT + 1)
    _need(child.returncode == 0 and len(output) <= _MAX_OUTPUT, "signed fixture entry did not complete")
    return output


def run_staged(release, root, executable, executable_sha256):
    """Run the pinned signed entry from an ordinary verified fixture generation."""
    return _run(release, root, executable, executable_sha256, nullcontext(), release.entry, (), None)


def _admitted(root, descriptor, release, policy, now):
    _fixture_root(root)
    _need(release.package == descriptor.package_id and release.policy == policy, "changed release trust")
    _fresh(policy, now)
    return _group_path(root, descriptor.package_id, "signed/" + release.manifest_sha256)


def install_signed(root, descriptor, expected_revision, runtime_id, release, *, policy, now,
                   registry_proposal=None, crash_after=None):
    """Stage only an admitted release and publish its manifest digest through the existing journal."""
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
                   registry_proposal=registry_proposal, crash_after=crash_after)


@contextmanager
def _signed_activation(root, descriptor, release):
    with _activation(root, descriptor) as active:
        _need(active is not None and active[2] == release.manifest_sha256.encode("ascii"),
              "release is outside the active signed generation")
        yield


def launch_signed(root, descriptor, release, executable, executable_sha256, *, policy, now):
    generation = _admitted(root, descriptor, release, policy, now)
    return _run(release, generation, executable, executable_sha256,
                _signed_activation(root, descriptor, release), release.entry, (), None)
