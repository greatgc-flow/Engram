"""Default Windows tool artifacts must be pinned before executable canaries.

These checks are offline and intentionally do not duplicate the declared hash
values. Source provenance for the eight newly pinned assets is in Issue #100.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse


DEFAULTS = Path(__file__).resolve().parents[2] / "defaults" / "runtimes.json"


def test_all_default_url_binaries_have_a_valid_declared_digest():
    defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    rows = {}
    for group in ("runtimes", "tools"):
        for name, spec in defaults[group].items():
            if not spec.get("url"):
                continue
            rows[f"{group}/{name}"] = spec
            lengths = {"sha256": 64, "sha3_256": 64, "sha512": 128}
            declared = [(algo, spec[algo]) for algo in lengths if spec.get(algo)]
            assert len(declared) == 1, f"{group}/{name} requires one pinned digest"
            algorithm, checksum = declared[0]
            assert isinstance(checksum, str) and re.fullmatch(
                rf"[0-9a-f]{{{lengths[algorithm]}}}", checksum
            ), f"{group}/{name} has malformed {algorithm}"
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
