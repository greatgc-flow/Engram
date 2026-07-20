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


def _asset(name, url=None):
    return {"name": name, "browser_download_url": url or f"https://example/{name}"}


def test_classify_windows_asset_arch_x64_markers():
    for name in ("ripgrep-15.2.0-x86_64-pc-windows-msvc.zip", "gh_2.96.0_windows_amd64.zip",
                 "tool-windows-x64.exe", "tool-x86-64-win.zip"):
        assert vr._classify_windows_asset_arch(name) == "x64", name


def test_classify_windows_asset_arch_arm_markers():
    for name in ("ripgrep-15.2.0-aarch64-pc-windows-msvc.zip", "tool-windows-arm64.exe",
                 "tool-armv7-windows.zip"):
        assert vr._classify_windows_asset_arch(name) == "arm", name


def test_classify_windows_asset_arch_x86_32bit_not_confused_with_x64():
    assert vr._classify_windows_asset_arch("tool-i686-pc-windows-msvc.zip") == "x86"
    assert vr._classify_windows_asset_arch("tool-i386-windows.zip") == "x86"


def test_pick_windows_asset_prefers_x86_64_regardless_of_asset_order():
    # Regression for the live incident: a real x86_64 build and a real
    # aarch64 build used to tie under the old substring-score heuristic
    # ("arm64" check missed "aarch64", "x64"/"amd64" check missed "x86_64"),
    # so whichever GitHub listed first in the release payload won.
    release_arm_first = {"assets": [
        _asset("ripgrep-15.2.0-aarch64-pc-windows-msvc.zip", "https://x/aarch64.zip"),
        _asset("ripgrep-15.2.0-x86_64-pc-windows-msvc.zip", "https://x/x86_64.zip"),
    ]}
    release_x64_first = {"assets": [
        _asset("ripgrep-15.2.0-x86_64-pc-windows-msvc.zip", "https://x/x86_64.zip"),
        _asset("ripgrep-15.2.0-aarch64-pc-windows-msvc.zip", "https://x/aarch64.zip"),
    ]}
    assert vr._pick_windows_asset(release_arm_first) == "https://x/x86_64.zip"
    assert vr._pick_windows_asset(release_x64_first) == "https://x/x86_64.zip"


def test_pick_windows_asset_excludes_arm_even_when_only_candidate():
    release = {"assets": [_asset("tool-windows-arm64.zip")]}
    assert vr._pick_windows_asset(release) is None


def test_pick_windows_asset_excludes_checksum_and_signature_files():
    release = {"assets": [
        _asset("tool-windows-amd64.zip.sha256"),
        _asset("checksums.txt"),
        _asset("tool-windows-amd64.zip.sig"),
        _asset("tool-windows-amd64.zip", "https://x/real.zip"),
    ]}
    assert vr._pick_windows_asset(release) == "https://x/real.zip"


def test_pick_windows_asset_falls_back_to_x86_when_no_x64_build_exists():
    release = {"assets": [_asset("tool-i686-pc-windows-msvc.zip", "https://x/x86.zip")]}
    assert vr._pick_windows_asset(release) == "https://x/x86.zip"


def test_pick_windows_asset_ignores_non_windows_and_non_archive_assets():
    release = {"assets": [
        _asset("tool-linux-amd64.tar.gz"),
        _asset("tool-macos-amd64.tar.gz"),
        _asset("README.md"),
        _asset("tool-windows-amd64.exe", "https://x/win.exe"),
    ]}
    assert vr._pick_windows_asset(release) == "https://x/win.exe"


def test_pick_windows_asset_no_windows_assets_returns_none():
    release = {"assets": [_asset("tool-linux-amd64.tar.gz")]}
    assert vr._pick_windows_asset(release) is None


def test_pick_windows_asset_non_list_assets_returns_none():
    assert vr._pick_windows_asset({"assets": "not-a-list"}) is None
    assert vr._pick_windows_asset({}) is None
