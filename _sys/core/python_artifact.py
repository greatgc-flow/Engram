"""Admit a cached Windows CPython archive against a trusted provider selection."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import gzip
import hashlib
import os
from pathlib import Path
import re
import struct
import tarfile
import tempfile
import zlib

VERSION = r"3\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})"
DIGEST = r"[a-f0-9]{64}"
MAX_COMPRESSED = 256 << 20
MAX_EXPANDED = 512 << 20
MAX_MEMBERS = 20000
BLOCK = 1 << 20


class ProviderError(ValueError):
    """Provider evidence is unavailable, ambiguous or outside the supported profile."""


def require(condition, detail):
    if not condition:
        raise ProviderError(detail)


@dataclass(frozen=True)
class Artifact:
    """A subject selected by the fixed publisher adapter or a reviewed repository lock."""

    tag: str
    version: str
    asset_id: int
    sha256: str
    size: int

    def __post_init__(self):
        require(isinstance(self.tag, str) and re.fullmatch(r"[0-9]{8}", self.tag), "invalid release tag")
        require(isinstance(self.version, str) and re.fullmatch(VERSION, self.version), "invalid stable version")
        require(type(self.asset_id) is int and self.asset_id > 0, "invalid asset ID")
        require(isinstance(self.sha256, str) and re.fullmatch(DIGEST, self.sha256), "invalid publisher SHA-256")
        require(type(self.size) is int and 0 < self.size <= MAX_COMPRESSED, "unsupported archive size")

    def identity(self):
        minor = self.version.split(".")[1]
        return {"implementation": "cpython", "version": self.version, "abi": f"cp3{minor}",
                "arch": "win_amd64", "flavor": "full", "provider": "python-build-standalone",
                "sha256": self.sha256, "artifact_ref": f"pbs-{self.tag}-{self.asset_id}"}


def validate_member_name(name):
    parts = name.split("/")
    require(parts[0] == "python" and len(name) <= 512, "invalid archive root or path length")
    for part in parts:
        require(re.fullmatch(r"[A-Za-z0-9._ -]{1,255}", part) and not part.endswith((".", " "))
                and not re.fullmatch(r"(?i)CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]", part.split(".", 1)[0].rstrip()),
                "invalid Windows path component")
    return parts


def _amd64(stream):
    header = stream.read(64)
    require(len(header) == 64 and header[:2] == b"MZ", "missing executable header")
    offset = struct.unpack_from("<I", header, 60)[0]
    require(64 <= offset <= 65536, "invalid PE offset")
    stream.read(offset - 64)
    require(stream.read(6) == b"PE\x00\x00\x64\x86", "expected an AMD64 PE image")


def _inspect(raw, artifact):
    # Spool the bounded expanded tar before parsing headers with extended lengths.
    # Never materialize member paths or execute code during admission.
    with tempfile.TemporaryFile() as expanded, gzip.GzipFile(fileobj=raw) as compressed:
        total = 0
        while block := compressed.read(BLOCK):
            total += len(block)
            require(total <= MAX_EXPANDED, "expanded archive exceeds admission budget")
            expanded.write(block)
        expanded.seek(0)
        with tarfile.open(fileobj=expanded, mode="r:") as archive:
            receipt = _inspect_members(archive, artifact, total)
            expanded.seek(archive.offset)
            require(total % 512 == 0 and total - archive.offset >= 1024, "incomplete tar terminator")
            while padding := expanded.read(BLOCK):
                require(not padding.strip(b"\x00"), "unexpected data after tar members")
            return receipt


def _inspect_members(archive, artifact, tar_bytes):
    minor = artifact.version.split(".")[1]
    dll = f"python/python3{minor}.dll"
    required = {"python/python.exe", dll, "python/include/patchlevel.h", "python/LICENSE.txt",
                "python/Lib/venv/__init__.py", "python/Lib/ensurepip/__init__.py"}
    nodes = {}
    explicit = set()
    files = set()
    content_bytes = 0
    bundled_pip = False
    for index, member in enumerate(archive, start=1):
        require(index <= MAX_MEMBERS, "archive has too many members")
        name = member.name
        parts = validate_member_name(name)
        require(member.isdir() or member.type in (tarfile.REGTYPE, tarfile.AREGTYPE), "unsupported archive member")
        require(member.sparse is None and not any("sparse" in k.lower() for k in member.pax_headers),
                "unsupported sparse archive member")
        require(name not in explicit and (name != "python" or member.isdir()), "duplicate or invalid archive member")
        explicit.add(name)
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            node = (prefix, end < len(parts) or member.isdir())
            require(nodes.setdefault(prefix.casefold(), node) == node, "case or file/directory collision")
        require(0 <= member.size <= tar_bytes - member.offset_data, "invalid archive extent")
        if member.isdir():
            require(member.size == 0, "unexpected directory payload")
            continue
        files.add(name)
        content_bytes += member.size
        if name in ("python/python.exe", dll):
            with archive.extractfile(member) as stream:
                _amd64(stream)
        elif name == "python/include/patchlevel.h":
            require(member.size <= 65536, "oversized version header")
            with archive.extractfile(member) as stream:
                versions = re.findall(rb'(?m)^#define[ \t]+PY_VERSION[ \t]+"([^"]+)"[ \t]*\r?$', stream.read())
            require(versions == [artifact.version.encode("ascii")], "CPython patch mismatch")
        elif re.fullmatch(r"python/python3[0-9]+(?:t|_d)?\.dll", name, re.IGNORECASE):
            raise ProviderError("unexpected CPython ABI DLL")
        elif re.fullmatch(r"python/Lib/ensurepip/_bundled/pip-[^/]+-py3-none-any\.whl", name):
            bundled_pip = member.size > 0 or bundled_pip
    require(required <= files and bundled_pip, "incomplete full CPython layout")
    return {"regular_files": len(files), "uncompressed_bytes": content_bytes, "python_pe_machine": "AMD64",
            "identity": artifact.identity()}


@contextmanager
def open_verified(path: Path, artifact: Artifact, expected_identity: dict):
    """Yield the same private compressed bytes checked against the approved plan."""
    require(artifact.identity() == expected_identity, "selected artifact differs from approved identity")
    with tempfile.TemporaryFile() as private:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as source:
                require(os.fstat(source.fileno()).st_size == artifact.size, "archive size mismatch")
                count = 0
                while chunk := source.read(BLOCK):
                    count += len(chunk)
                    require(count <= artifact.size, "archive grew during verification")
                    digest.update(chunk)
                    private.write(chunk)
            require(count == artifact.size and digest.hexdigest() == artifact.sha256, "archive digest mismatch")
            private.seek(0)
            receipt = _inspect(private, artifact)
        except (OSError, EOFError, tarfile.TarError, zlib.error) as exc:
            raise ProviderError(f"unable to verify cached archive: {type(exc).__name__}") from exc
        private.seek(0)
        yield private, receipt


# WIRING-EXEMPT: EXPORTED_API reason="The offline WP0 inventory command in tools/feasibility/windows_python.py calls this API."
def verify_cached(path: Path, artifact: Artifact, expected_identity: dict) -> dict:
    with open_verified(path, artifact, expected_identity) as (_, receipt):
        return receipt
