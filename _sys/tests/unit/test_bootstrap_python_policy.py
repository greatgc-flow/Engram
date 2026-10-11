"""Static contracts for bootstrap.bat's Python policy (design sections 4.1 P9 and 6.4).

- Bootstrap installs only the validated pin; discovery is notice-only.
- The Python zip cache is versioned and carries a recorded sha256, so an offline re-bootstrap
  can reuse a verified cache and never trusts an unverified file.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOTSTRAP = REPO_ROOT / "_sys" / "core" / "bootstrap.bat"


@pytest.fixture(scope="module")
def text() -> str:
    return BOOTSTRAP.read_text(encoding="utf-8")


def _line_no(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines()):
        if needle in line:
            return i
    raise AssertionError(f"{needle!r} not found in bootstrap.bat")


# ---- pin-only bootstrap ------------------------------------------------------------

def test_bootstrap_never_auto_bumps_or_rewrites_the_pin(text):
    assert "_FRESH_ROOT" not in text
    assert "_PY_BUMP" not in text
    assert "runtimes.python.version=" not in text
    assert "ConvertTo-Json -Depth 10" not in text


def test_bootstrap_points_to_managed_updates(text):
    assert "engram update --only python" in text
    assert "engram update --check" in text
    assert "remove !SYS_DIR!\\env\\python" not in text


def test_skip_update_skips_only_the_notice_check(text):
    assert '--skip-update' in text
    assert 'if "!_SKIP_UPDATE!"=="0" (' in text
    assert "skips only this notice check" in text


# ---- versioned, verified cache -------------------------------------------------------

def test_cache_name_is_versioned_not_a_fixed_file(text):
    assert "python-bootstrap.zip" not in text
    assert "python-!PY_VER!-embed-amd64.zip" in text


def test_cache_has_recorded_sha256(text):
    assert ".sha256" in text
    assert "ComputeHash" in text
    assert "SHA256" in text.upper()


def test_verified_cache_is_reused_before_downloading(text):
    reuse = _line_no(text, "_CACHE_OK")
    download = _line_no(text, "Downloading Python embeddable zip")
    assert reuse < download


def test_download_is_hashed_after_it_succeeds(text):
    lines = text.splitlines()
    dl = _line_no(text, 'curl -fL "!PY_URL!"')
    after = "\n".join(lines[dl:dl + 25])
    assert "ComputeHash" in after


def test_declared_hash_is_enforced_when_runtimes_json_provides_one(text):
    assert "PY_SHA256" in text


# ---- batch hygiene (CONVENTION section 2) ------------------------------------------------

def test_bootstrap_stays_ascii_english_without_bom(text):
    raw = BOOTSTRAP.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM breaks the first cmd.exe command"
    assert all(ord(ch) < 128 for ch in text), "non-ASCII characters are forbidden in .bat files"
    assert "chcp" not in text.lower().replace("chcp is prohibited", "")


def test_hash_commands_escape_single_quotes_in_the_path(text):
    # cross-review ag.deepthink: a quote in the path would end the PowerShell string
    assert "_ZIP_PS" in text
    assert "!ZIP_PATH:'=''!" in text
    assert "-LiteralPath '!ZIP_PATH!'" not in text
