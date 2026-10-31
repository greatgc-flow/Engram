"""Default Windows tool artifacts must be pinned before executable canaries.

These checks are offline and intentionally do not duplicate the declared hash
values. Source provenance for the eight newly pinned assets is in Issue #100.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse


DEFAULTS = Path(__file__).resolve().parents[2] / "defaults" / "runtimes.json"


def test_all_default_url_binaries_are_pinned_by_sha256():
    defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    rows = {}
    for group in ("runtimes", "tools"):
        for name, spec in defaults[group].items():
            if not spec.get("url"):
                continue
            rows[f"{group}/{name}"] = spec
            checksum = spec.get("sha256")
            assert isinstance(checksum, str) and re.fullmatch(
                r"[0-9a-f]{64}", checksum
            ), f"{group}/{name} has no valid pinned SHA-256"
            assert urlparse(spec["url"]).scheme == "https"
    assert rows, "missing default artifact inventory"


def test_newly_pinned_github_assets_use_immutable_versioned_paths():
    tools = json.loads(DEFAULTS.read_text(encoding="utf-8"))["tools"]
    names = ("ripgrep", "bat", "fd", "delta", "fzf", "jq", "gh", "oh-my-posh")
    for name in names:
        spec = tools[name]
        # The embedded version should agree with the immutable release URL.
        # GitHub adds a leading v on some projects; jq embeds a product prefix.
        version = spec["version"]
        assert version in spec["url"], name
        assert "/releases/download/" in spec["url"], name
        assert spec["sha256"], name
