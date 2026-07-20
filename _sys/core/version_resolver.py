"""Measured latest-version discovery for portable runtime/tool entries.

This module reports discovery results only. It never installs, updates, or
rewrites runtimes.json.
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SYS_DIR = Path(__file__).resolve().parents[1]
_PORTABLE_ROOT = _SYS_DIR.parent
_DEFAULT_CACHE = _PORTABLE_ROOT / ".ai" / "tool_discovery_cache.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_cache(cache_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _cache_get(cache: dict[str, Any], provider: str, discovery_id: str) -> dict[str, Any]:
    provider_cache = cache.get(provider, {})
    if not isinstance(provider_cache, dict):
        provider_cache = {}
    entry = provider_cache.get(discovery_id, {})
    return entry if isinstance(entry, dict) else {}


def _cache_put(
    cache_path: Path,
    cache: dict[str, Any],
    provider: str,
    discovery_id: str,
    values: dict[str, Any],
) -> None:
    provider_cache = cache.setdefault(provider, {})
    if not isinstance(provider_cache, dict):
        provider_cache = {}
        cache[provider] = provider_cache
    current = provider_cache.get(discovery_id, {})
    if not isinstance(current, dict):
        current = {}
    current.update(values)
    current["last_checked_at"] = _now_utc()
    provider_cache[discovery_id] = current
    _save_cache(cache_path, cache)


def _normalize_version(version: str) -> str:
    version = str(version).strip()
    return version[1:] if version.startswith("v") and len(version) > 1 else version


def _result(
    *,
    status: str,
    provider: str,
    discovery_id: str,
    latest_version: str | None = None,
    url: str | None = None,
    checksum_algo: str | None = None,
    checksum_value: str | None = None,
    checksum_source: str | None = None,
    source: str | None = None,
    detail: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    out = {
        "status": status,
        "provider": provider,
        "discovery_id": discovery_id,
    }
    if latest_version is not None:
        out["latest_version"] = latest_version
    if url is not None:
        out["url"] = url
    if checksum_algo is not None:
        out["checksum_algo"] = checksum_algo
    if checksum_value is not None:
        out["checksum_value"] = checksum_value
    if checksum_source is not None:
        out["checksum_source"] = checksum_source
    if source is not None:
        out["source"] = source
    if detail is not None:
        out["detail"] = detail
    if error_type is not None:
        out["error_type"] = error_type
    return out


def _header_get(headers: Any, key: str) -> str | None:
    if not headers:
        return None
    try:
        value = headers.get(key)
    except AttributeError:
        value = None
    if value is None:
        try:
            value = headers.get(key.lower())
        except AttributeError:
            value = None
    return str(value) if value is not None else None


def _split_gh_include(stdout: str) -> tuple[int | None, dict[str, str], str]:
    parts = re.split(r"\r?\n\r?\n", stdout, maxsplit=1)
    header_text = parts[0] if parts else ""
    body = parts[1] if len(parts) > 1 else ""
    lines = header_text.splitlines()
    status_code = None
    headers: dict[str, str] = {}
    if lines:
        match = re.search(r"\s(\d{3})\s", lines[0])
        if match:
            status_code = int(match.group(1))
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return status_code, headers, body


def _gh_api_latest(discovery_id: str, etag: str | None) -> tuple[int, dict[str, str], str] | None:
    if not shutil.which("gh"):
        return None
    try:
        auth = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if auth.returncode != 0:
        return None

    args = ["gh", "api", "--include", f"repos/{discovery_id}/releases/latest"]
    if etag:
        args.extend(["-H", f"If-None-Match: {etag}"])
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None

    status_code, headers, body = _split_gh_include(cp.stdout)
    if status_code is None:
        return None
    return status_code, headers, body


# Order matters: "x86_64"/"amd64"/"x64" must be checked before the generic
# "x86" marker, since "x86" is a substring of "x86_64" (a false match there
# would misclassify a 64-bit asset as 32-bit).
_ARM_ASSET_MARKERS = ("aarch64", "arm64", "armv7", "armhf")
_X64_ASSET_MARKERS = ("x86_64", "x86-64", "amd64", "x64")
_X86_ASSET_MARKERS = ("i686", "i386", "x86")
_CHECKSUM_ASSET_MARKERS = ("sha256", "sha512", "checksums", ".sig", ".asc", ".sbom")


def _classify_windows_asset_arch(name: str) -> str:
    if any(marker in name for marker in _ARM_ASSET_MARKERS):
        return "arm"
    if any(marker in name for marker in _X64_ASSET_MARKERS):
        return "x64"
    if any(marker in name for marker in _X86_ASSET_MARKERS):
        return "x86"
    return "unknown"


def _pick_windows_asset(release: dict[str, Any]) -> str | None:
    """Deterministic asset selection: filter to real Windows archives/binaries,
    hard-exclude ARM builds and checksum/signature files, then prefer an
    explicit 64-bit x86 build. Previously this ranked assets by a substring
    score that missed "aarch64" (only checked "arm64") and missed "x86_64"
    (only checked "x64"/"amd64"), so a real x86_64 build and a real aarch64
    build could tie -- picking whichever GitHub happened to list first in
    that release's asset order (confirmed live: an aarch64 ripgrep build was
    proposed for an x86_64 machine, see runtimes.json history)."""
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return None
    candidates: list[tuple[str, str]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", "")).lower()
        url = asset.get("browser_download_url")
        if not url:
            continue
        if not ("win" in name or "windows" in name):
            continue
        if any(marker in name for marker in _CHECKSUM_ASSET_MARKERS):
            continue
        if not name.endswith((".zip", ".exe", ".7z")):
            continue
        arch = _classify_windows_asset_arch(name)
        if arch == "arm":
            continue
        candidates.append((arch, str(url)))
    for wanted in ("x64", "x86", "unknown"):
        for arch, url in candidates:
            if arch == wanted:
                return url
    return None


def _github_from_http_result(
    *,
    discovery_id: str,
    status_code: int,
    headers: Any,
    body: str,
    cached: dict[str, Any],
    cache: dict[str, Any],
    cache_path: Path,
) -> dict[str, Any]:
    provider = "github_releases"

    if status_code == 304:
        cached_version = cached.get("cached_latest_version")
        if cached_version:
            return _result(
                status="ok",
                provider=provider,
                discovery_id=discovery_id,
                latest_version=str(cached_version),
                url=cached.get("cached_url"),
                checksum_algo=cached.get("checksum_algo"),
                checksum_value=cached.get("checksum_value"),
                checksum_source=cached.get("checksum_source"),
                source="cache_304",
            )
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail="GitHub returned 304 but no cached_latest_version exists",
            error_type="cache_miss",
        )

    if status_code == 403:
        return _result(
            status="discovery_unavailable",
            provider=provider,
            discovery_id=discovery_id,
            detail="GitHub discovery unavailable or rate limited",
            error_type="rate_limited",
        )

    if status_code != 200:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=f"GitHub returned HTTP {status_code}",
            error_type="http_error",
        )

    try:
        release = json.loads(body)
    except json.JSONDecodeError as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=f"invalid GitHub JSON: {exc.msg}",
            error_type="parse_error",
        )

    tag = release.get("tag_name") or release.get("name")
    if not tag:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail="GitHub release has no tag_name",
            error_type="missing_version",
        )

    latest_version = _normalize_version(str(tag))
    url = _pick_windows_asset(release) or release.get("html_url")
    etag = _header_get(headers, "ETag")
    cache_values = {
        "cached_latest_version": latest_version,
        "cached_url": url,
    }
    if etag:
        cache_values["etag"] = etag
    _cache_put(cache_path, cache, provider, discovery_id, cache_values)

    return _result(
        status="ok",
        provider=provider,
        discovery_id=discovery_id,
        latest_version=latest_version,
        url=url,
        source="github_api",
    )


def _resolve_github(discovery_id: str, cache_path: Path | None = None) -> dict[str, Any]:
    cache_path = cache_path or _DEFAULT_CACHE
    provider = "github_releases"
    cache = _load_cache(cache_path)
    cached = _cache_get(cache, provider, discovery_id)
    etag = cached.get("etag")

    gh_result = _gh_api_latest(discovery_id, str(etag) if etag else None)
    if gh_result is not None:
        status_code, headers, body = gh_result
        return _github_from_http_result(
            discovery_id=discovery_id,
            status_code=status_code,
            headers=headers,
            body=body,
            cached=cached,
            cache=cache,
            cache_path=cache_path,
        )

    url = f"https://api.github.com/repos/{discovery_id}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "portable-dev-version-resolver"}
    if etag:
        headers["If-None-Match"] = str(etag)
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return _github_from_http_result(
                discovery_id=discovery_id,
                status_code=int(resp.getcode()),
                headers=resp.headers,
                body=body,
                cached=cached,
                cache=cache,
                cache_path=cache_path,
            )
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read() if hasattr(exc, "read") else b""
        body = body_bytes.decode("utf-8", errors="replace") if isinstance(body_bytes, bytes) else str(body_bytes)
        return _github_from_http_result(
            discovery_id=discovery_id,
            status_code=int(exc.code),
            headers=exc.headers,
            body=body,
            cached=cached,
            cache=cache,
            cache_path=cache_path,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=str(exc),
            error_type="network_error",
        )


def _resolve_npm(package: str) -> dict[str, Any]:
    provider = "npm"
    encoded = urllib.parse.quote(package, safe="")
    req = urllib.request.Request(
        f"https://registry.npmjs.org/{encoded}/latest",
        headers={"User-Agent": "portable-dev-version-resolver"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if int(resp.getcode()) != 200:
                return _result(
                    status="error",
                    provider=provider,
                    discovery_id=package,
                    detail=f"npm returned HTTP {resp.getcode()}",
                    error_type="http_error",
                )
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=package,
            detail=f"npm returned HTTP {exc.code}",
            error_type="http_error",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=package,
            detail=str(exc),
            error_type="network_error",
        )
    except json.JSONDecodeError as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=package,
            detail=f"invalid npm JSON: {exc.msg}",
            error_type="parse_error",
        )

    version = data.get("version")
    if not version:
        return _result(
            status="error",
            provider=provider,
            discovery_id=package,
            detail="npm latest response has no version",
            error_type="missing_version",
        )
    dist = data.get("dist", {}) if isinstance(data.get("dist"), dict) else {}
    integrity = dist.get("integrity")
    return _result(
        status="ok",
        provider=provider,
        discovery_id=package,
        latest_version=str(version),
        url=dist.get("tarball"),
        checksum_algo="integrity" if integrity else None,
        checksum_value=str(integrity) if integrity else None,
        checksum_source="registry_integrity" if integrity else None,
        source="npm_registry",
    )


def _sqlite_rows_from_html(html: str) -> list[list[str]]:
    # sqlite.org's own data rows use a LITERAL "PRODUCT" constant in column 1
    # (documented on the page: "for convenient regular expression matching"),
    # so only the very first line (the true header) can be skipped by
    # content - every subsequent row also starts with "PRODUCT".
    rows: list[list[str]] = []
    for comment in re.findall(r"<!--(.*?)-->", html, flags=re.DOTALL):
        if "PRODUCT,VERSION,RELATIVE-URL,SIZE-IN-BYTES,SHA3-HASH" not in comment:
            continue
        reader = csv.reader(io.StringIO(comment.strip()))
        for i, row in enumerate(reader):
            if i == 0 or not row:
                continue
            if len(row) >= 5:
                rows.append([cell.strip() for cell in row[:5]])
    return rows


def _resolve_sqlite(discovery_id: str = "sqlite-tools-win-x64") -> dict[str, Any]:
    provider = "sqlite_org_page"
    req = urllib.request.Request(
        "https://www.sqlite.org/download.html",
        headers={"User-Agent": "portable-dev-version-resolver"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if int(resp.getcode()) != 200:
                return _result(
                    status="error",
                    provider=provider,
                    discovery_id=discovery_id,
                    detail=f"sqlite.org returned HTTP {resp.getcode()}",
                    error_type="http_error",
                )
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=f"sqlite.org returned HTTP {exc.code}",
            error_type="http_error",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=str(exc),
            error_type="network_error",
        )

    for _product, version, rel_url, _size, sha3_hash in _sqlite_rows_from_html(html):
        # The CSV's PRODUCT column is a literal constant "PRODUCT" (per
        # sqlite.org's own page text) - the artifact is identified by its
        # filename in RELATIVE-URL instead, e.g. "sqlite-tools-win-x64".
        if discovery_id in rel_url:
            return _result(
                status="ok",
                provider=provider,
                discovery_id=discovery_id,
                latest_version=str(version),
                url=urllib.parse.urljoin("https://www.sqlite.org/", rel_url),
                checksum_algo="sha3_256",
                checksum_value=sha3_hash,
                checksum_source="sqlite_org_csv",
                source="sqlite_org_download_page",
            )

    return _result(
        status="error",
        provider=provider,
        discovery_id=discovery_id,
        detail=f"sqlite.org CSV has no row for {discovery_id}",
        error_type="not_found",
    )


def resolve_latest(
    tool_name: str,
    provider: str,
    current_version: str,
    discovery_id: str,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    if provider == "github_releases":
        result = _resolve_github(discovery_id, cache_path)
    elif provider == "npm":
        result = _resolve_npm(discovery_id)
    elif provider == "sqlite_org_page":
        result = _resolve_sqlite(discovery_id)
    elif provider == "manual":
        result = _result(status="manual", provider=provider, discovery_id=discovery_id)
    else:
        result = _result(
            status="error",
            provider=provider,
            discovery_id=discovery_id,
            detail=f"unsupported discovery_provider: {provider}",
            error_type="unsupported_provider",
        )

    result["tool"] = tool_name
    result["current_version"] = current_version
    return result
