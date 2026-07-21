"""_SameHostRedirectHandler used to reject ANY cross-host redirect, which
blocked legitimate GitHub release downloads (github.com always 302s to a
time-limited signed URL on a different githubusercontent.com host). Added a
narrow allowlist; these tests exercise redirect_request's host-checking logic
directly, without touching the network."""
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import provisioner as pv  # noqa: E402


def _fake_request(url: str) -> MagicMock:
    req = MagicMock()
    req.full_url = url
    return req


def test_allows_github_to_release_assets_cdn(monkeypatch):
    handler = pv._SameHostRedirectHandler()
    monkeypatch.setattr(
        urllib.request.HTTPRedirectHandler, "redirect_request",
        lambda self, req, fp, code, msg, headers, newurl: "OK",
    )
    result = handler.redirect_request(
        _fake_request("https://github.com/BurntSushi/ripgrep/releases/download/15.2.0/rg.zip"),
        None, 302, "Found", {},
        "https://release-assets.githubusercontent.com/abc?se=2026-07-21T10%3A00%3A00Z",
    )
    assert result == "OK"


def test_allows_github_to_objects_cdn(monkeypatch):
    handler = pv._SameHostRedirectHandler()
    monkeypatch.setattr(
        urllib.request.HTTPRedirectHandler, "redirect_request",
        lambda self, req, fp, code, msg, headers, newurl: "OK",
    )
    result = handler.redirect_request(
        _fake_request("https://github.com/cli/cli/releases/download/v2.96.0/gh.zip"),
        None, 302, "Found", {},
        "https://objects.githubusercontent.com/xyz",
    )
    assert result == "OK"


def test_rejects_github_to_untrusted_third_party():
    handler = pv._SameHostRedirectHandler()
    with pytest.raises(urllib.error.URLError, match="Cross-host redirect rejected"):
        handler.redirect_request(
            _fake_request("https://github.com/foo/bar/releases/download/v1/x.zip"),
            None, 302, "Found", {},
            "https://evil-mirror.example.com/x.zip",
        )


def test_rejects_cross_host_for_non_github_source():
    """The allowlist is keyed on the SOURCE host too - a redirect away from
    some other origin (e.g. a compromised python.org mirror) must still be
    rejected outright, even if the target happens to be a githubusercontent
    host."""
    handler = pv._SameHostRedirectHandler()
    with pytest.raises(urllib.error.URLError, match="Cross-host redirect rejected"):
        handler.redirect_request(
            _fake_request("https://python.org/ftp/python/foo.zip"),
            None, 302, "Found", {},
            "https://release-assets.githubusercontent.com/abc",
        )
