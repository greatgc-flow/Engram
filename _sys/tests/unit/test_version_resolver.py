# _sys/tests/unit/test_version_resolver.py
from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "core"))

import version_resolver as vr  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self._status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload

    def getcode(self):
        return self._status


def test_github_200_returns_version_url_and_updates_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(vr.shutil, "which", lambda name: None)
    release = {
        "tag_name": "v1.2.3",
        "html_url": "https://github.example/release",
        "assets": [
            {"name": "tool-linux.tar.gz", "browser_download_url": "https://example/linux"},
            {"name": "tool-v1.2.3-windows-amd64.zip", "browser_download_url": "https://example/win.zip"},
        ],
    }
    monkeypatch.setattr(
        vr.urllib.request,
        "urlopen",
        lambda req, timeout=30: FakeResponse(json.dumps(release), headers={"ETag": '"abc"'}),
    )

    cache_path = tmp_path / "tool_discovery_cache.json"
    result = vr.resolve_latest("tool", "github_releases", "1.0.0", "owner/repo", cache_path)

    assert result["status"] == "ok"
    assert result["latest_version"] == "1.2.3"
    assert result["url"] == "https://example/win.zip"

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["github_releases"]["owner/repo"]["etag"] == '"abc"'
    assert cache["github_releases"]["owner/repo"]["cached_latest_version"] == "1.2.3"


def test_github_403_is_discovery_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(vr.shutil, "which", lambda name: None)

    def fail(req, timeout=30):
        raise urllib.error.HTTPError(
            req.full_url,
            403,
            "rate limited",
            {"X-RateLimit-Remaining": "0"},
            io.BytesIO(b"API rate limit exceeded"),
        )

    monkeypatch.setattr(vr.urllib.request, "urlopen", fail)

    result = vr.resolve_latest("gh", "github_releases", "1.0.0", "cli/cli", tmp_path / "cache.json")

    assert result["status"] == "discovery_unavailable"
    assert result["error_type"] == "rate_limited"


def test_github_304_returns_cached_version(monkeypatch, tmp_path):
    monkeypatch.setattr(vr.shutil, "which", lambda name: None)
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({
        "github_releases": {
            "owner/repo": {
                "etag": '"abc"',
                "last_checked_at": "2026-07-10T00:00:00Z",
                "cached_latest_version": "2.0.0",
                "cached_url": "https://example/tool.zip",
            }
        }
    }), encoding="utf-8")

    def not_modified(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 304, "not modified", {}, io.BytesIO(b""))

    monkeypatch.setattr(vr.urllib.request, "urlopen", not_modified)

    result = vr.resolve_latest("tool", "github_releases", "1.0.0", "owner/repo", cache_path)

    assert result["status"] == "ok"
    assert result["latest_version"] == "2.0.0"
    assert result["url"] == "https://example/tool.zip"
    assert result["source"] == "cache_304"


def test_github_network_error_is_not_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(vr.shutil, "which", lambda name: None)

    def boom(req, timeout=30):
        raise urllib.error.URLError("dns failed")

    monkeypatch.setattr(vr.urllib.request, "urlopen", boom)

    result = vr.resolve_latest("tool", "github_releases", "1.0.0", "owner/repo", tmp_path / "cache.json")

    assert result["status"] == "error"
    assert result["error_type"] == "network_error"


def test_npm_200_returns_version_and_registry_integrity(monkeypatch):
    payload = {
        "version": "3.4.5",
        "dist": {
            "tarball": "https://registry.npmjs.org/pkg/-/pkg-3.4.5.tgz",
            "integrity": "sha512-abc123",
        },
    }
    monkeypatch.setattr(
        vr.urllib.request,
        "urlopen",
        lambda req, timeout=30: FakeResponse(json.dumps(payload)),
    )

    result = vr.resolve_latest("codex", "npm", "3.0.0", "@openai/codex")

    assert result["status"] == "ok"
    assert result["latest_version"] == "3.4.5"
    assert result["checksum_algo"] == "integrity"
    assert result["checksum_value"] == "sha512-abc123"
    assert result["checksum_source"] == "registry_integrity"


def test_sqlite_page_parse_success_with_sha3(monkeypatch):
    # Real sqlite.org pages use a LITERAL "PRODUCT" constant in the PRODUCT
    # column (documented on the page itself) - the artifact must be selected
    # by matching discovery_id against the RELATIVE-URL filename, not the
    # PRODUCT column. Multiple rows (arm64 + x64) exercise that selection.
    html = """
    <html><body>
    <!--
    PRODUCT,VERSION,RELATIVE-URL,SIZE-IN-BYTES,SHA3-HASH
    PRODUCT,3.53.1,2026/sqlite-tools-win-arm64-3530100.zip,99999,ffffff
    PRODUCT,3.53.1,2026/sqlite-tools-win-x64-3530100.zip,12345,abcdef012345
    -->
    </body></html>
    """
    monkeypatch.setattr(
        vr.urllib.request,
        "urlopen",
        lambda req, timeout=30: FakeResponse(html),
    )

    result = vr.resolve_latest("sqlite", "sqlite_org_page", "3.50.0", "sqlite-tools-win-x64")

    assert result["status"] == "ok"
    assert result["latest_version"] == "3.53.1"
    assert result["url"] == "https://www.sqlite.org/2026/sqlite-tools-win-x64-3530100.zip"
    assert result["checksum_algo"] == "sha3_256"
    assert result["checksum_value"] == "abcdef012345"
