"""Publisher-scoped Windows CPython discovery and consumer evidence selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import http.client
import json
import re
import urllib.request

from core.python_artifact import Artifact, DIGEST, ProviderError, VERSION, require
from core.network_tls import install_urllib_platform_trust

API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"
WEB = "https://github.com/astral-sh/python-build-standalone/releases"
_MAX_RESPONSE = 8 << 20
_PAGE_SIZE = 100
_MAX_PAGES = 50


@dataclass(frozen=True)
class Release:
    tag: str
    observed_on: date
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True)
class ConsumerReceipt:
    """Trusted runner input for one tested build and content-addressed consumer lock."""

    artifact: Artifact
    consumer: str
    lock_sha256: str
    outcome: str
    evidence_sha256: str


class _FixedOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("unexpected provider metadata redirect")


def _read_api(url):
    install_urllib_platform_trust()
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "engram-python-provider"}
    )
    try:
        with urllib.request.build_opener(_FixedOrigin()).open(request, timeout=15) as response:
            require(response.status == 200 and response.geturl() == url, "unexpected publisher response")
            raw = response.read(_MAX_RESPONSE + 1)
            require(len(raw) <= _MAX_RESPONSE, "publisher response too large")
            return json.loads(raw.decode("utf-8"))
    except ProviderError:
        raise
    except (OSError, ValueError, RecursionError, http.client.HTTPException) as exc:
        raise ProviderError(f"publisher metadata unavailable: {type(exc).__name__}") from exc


def asset_name(artifact):
    return f"cpython-{artifact.version}+{artifact.tag}-x86_64-pc-windows-msvc-install_only.tar.gz"


def download_url(artifact):
    return f"{WEB}/download/{artifact.tag}/" + asset_name(artifact).replace("+", "%2B")


def fetch_release(*, today=None, tag=None) -> Release:
    """Read the current release and enumerate that immutable release by numeric ID."""
    today = today or datetime.now(timezone.utc).date()
    requested = tag
    if requested is not None:
        require(
            isinstance(requested, str) and re.fullmatch(r"[0-9]{8}", requested),
            "invalid selected release tag",
        )
    release = _read_api(API + ("/tags/" + requested if requested else "/latest"))
    require(isinstance(release, dict), "invalid release metadata")
    tag = release.get("tag_name")
    rid = release.get("id")
    require(
        isinstance(tag, str) and re.fullmatch(r"[0-9]{8}", tag) and type(rid) is int and rid > 0,
        "invalid publisher release identity",
    )
    require(requested is None or tag == requested, "publisher returned a different release tag")
    base = f"{API}/{rid}"
    require(
        release.get("url") == base
        and release.get("assets_url") == base + "/assets"
        and release.get("html_url") == WEB + "/tag/" + tag,
        "foreign release metadata",
    )
    require(
        release.get("immutable") is True
        and release.get("draft") is False
        and release.get("prerelease") is False,
        "release is not immutable and stable",
    )
    try:
        published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
        require(
            published.tzinfo is not None and published.astimezone(timezone.utc).date() <= today,
            "unreleased publisher metadata",
        )
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ProviderError("invalid publisher date") from exc

    names = set()
    ids = set()
    artifacts = []
    pattern = re.compile(rf"cpython-({VERSION})\+{tag}-x86_64-pc-windows-msvc-install_only\.tar\.gz")
    for page in range(1, _MAX_PAGES + 1):
        rows = _read_api(f"{base}/assets?per_page={_PAGE_SIZE}&page={page}")
        require(isinstance(rows, list) and len(rows) <= _PAGE_SIZE, "invalid asset page")
        for row in rows:
            require(isinstance(row, dict), "invalid asset record")
            name, ident = row.get("name"), row.get("id")
            require(
                isinstance(name, str)
                and name
                and name not in names
                and type(ident) is int
                and ident > 0
                and ident not in ids,
                "ambiguous asset inventory",
            )
            names.add(name)
            ids.add(ident)
            match = pattern.fullmatch(name)
            if match:
                url = f"{WEB}/download/{tag}/" + name.replace("+", "%2B")
                require(
                    row.get("url") == f"{API}/assets/{ident}"
                    and row.get("browser_download_url") == url
                    and row.get("state") == "uploaded",
                    "invalid publisher asset origin or state",
                )
                digest = row.get("digest")
                require(isinstance(digest, str) and digest.startswith("sha256:"), "missing publisher digest")
                artifacts.append(Artifact(tag, match[1], ident, digest[7:], row.get("size")))
        if len(rows) < _PAGE_SIZE:
            # The release detail may embed only a subset. Every advertised ID must appear.
            embedded = release.get("assets", [])
            require(
                isinstance(embedded, list)
                and all(
                    isinstance(a, dict) and type(a.get("id")) is int and a["id"] in ids for a in embedded
                ),
                "incomplete publisher asset inventory",
            )
            return Release(tag, today, tuple(artifacts))
    raise ProviderError("publisher inventory exceeds page budget")


def _compatible(artifact, locks, receipts):
    if not isinstance(locks, dict) or not locks or not all(isinstance(r, ConsumerReceipt) for r in receipts):
        return False
    for consumer, lock in locks.items():
        if not (
            isinstance(consumer, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", consumer)
            and isinstance(lock, str)
            and re.fullmatch(DIGEST, lock)
        ):
            return False
        evidence = [
            r for r in receipts if r.artifact == artifact and r.consumer == consumer and r.lock_sha256 == lock
        ]
        if not evidence or any(
            r.outcome != "PASS"
            or not isinstance(r.evidence_sha256, str)
            or not re.fullmatch(DIGEST, r.evidence_sha256)
            for r in evidence
        ):
            return False
    return True


def assess(source, release, locks, receipts, *, today=None):
    """Join source, one publisher release and trusted test receipts without altering inputs."""
    today = today or datetime.now(timezone.utc).date()
    if not isinstance(source, dict) or not isinstance(source.get("series"), dict):
        source = {"coverage": "UNKNOWN", "observed_on": None, "series": {}}
    provider_fresh = release is not None and release.observed_on == today
    coverage = "UNKNOWN"
    if release is not None:
        coverage = "MEASURED" if provider_fresh else "STALE"
    result = {
        **source,
        "binary_release": release.tag if release else None,
        "binary_coverage": coverage,
        "binary_observed_on": release.observed_on.isoformat() if release else None,
        "series": {},
    }
    receipts = tuple(receipts)
    for minor, source_row in source.get("series", {}).items():
        if not isinstance(source_row, dict):
            source_row = {"source_version": None, "support_phase": "UNKNOWN"}
        row = {
            **source_row,
            "windows_binary": None,
            "compatible_candidate": None,
            "binary_status": "UNVERIFIABLE",
            "binary_identity": None,
            "candidate_identity": None,
        }
        result["series"][minor] = row
        version = row.get("source_version")
        if (
            not isinstance(version, str)
            or not re.fullmatch(VERSION, version)
            or version.rsplit(".", 1)[0] != minor
        ):
            continue
        builds = (
            sorted(
                (a for a in release.artifacts if a.version.rsplit(".", 1)[0] == minor),
                key=lambda a: int(a.version.rsplit(".", 1)[1]),
                reverse=True,
            )
            if release
            else []
        )
        if builds:
            row["windows_binary"] = builds[0].version
            row["binary_identity"] = builds[0].identity()
        incomplete = source.get("incomplete_series")
        source_known = (
            source.get("coverage") == "MEASURED"
            or source.get("coverage") == "PARTIAL"
            and isinstance(incomplete, list)
            and minor not in incomplete
        )
        if not (provider_fresh and source_known and source.get("observed_on") == today.isoformat()):
            continue
        if builds and int(builds[0].version.rsplit(".", 1)[1]) > int(version.rsplit(".", 1)[1]):
            continue
        row["binary_status"] = (
            "AVAILABLE" if builds and builds[0].version == version else "SOURCE_NEWER_NO_BINARY"
        )
        if row.get("support_phase") in ("BUGFIX", "SECURITY_ONLY"):
            for artifact in builds:
                if _compatible(artifact, locks, receipts):
                    row["compatible_candidate"] = artifact.version
                    row["candidate_identity"] = artifact.identity()
                    break
    return result
