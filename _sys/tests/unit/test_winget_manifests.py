import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# tools/ is a maintainer-only release-packaging directory, deliberately
# excluded from the portable zip build (SYS_EXCLUDE_DIR_PATTERNS covers
# _sys/tools/, and repo-root tools/ is never walked at all) -- see
# tools/winget/build_package.py's own "zero-bloat portable runtime"
# contract. A real, from-scratch install of a release zip has this test
# file (it ships under _sys/tests/) but not the module it imports; skip
# rather than fail collection when that's the case, instead of shipping
# dev-only packaging tooling just to keep this one test importable.
pytest.importorskip(
    "tools.winget.build_package",
    reason="tools/ is excluded from the portable release zip by design",
)

from tools.winget.build_package import (
    generate_manifest_version,
    generate_manifest_installer,
    generate_manifest_locale_en,
    generate_manifest_locale_ko,
    collect_package_files,
    create_portable_archive,
    ROOT_FILES_ALLOW,
)

def test_manifest_generation():
    version = "3.0.0"
    sha256 = "1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF"
    url = "https://example.com/installer.zip"
    
    # 1. Version manifest
    v_yaml = generate_manifest_version(version)
    assert "PackageVersion: 3.0.0" in v_yaml

    # 2. Installer manifest
    i_yaml = generate_manifest_installer(version, sha256, url)
    assert "PackageVersion: 3.0.0" in i_yaml
    assert f"InstallerSha256: {sha256}" in i_yaml

    # 3. Locale EN manifest
    l_en_yaml = generate_manifest_locale_en(version)
    
    # Assert no stale AI-product claims
    l_en_lower = l_en_yaml.lower()
    assert "multi-agent" not in l_en_lower
    assert "orchestrates" not in l_en_lower
    
    # Check tags
    assert "- ai\n" not in l_en_lower
    assert "- agent\n" not in l_en_lower
    assert "- peerhub\n" not in l_en_lower
    assert "- telemetry\n" not in l_en_lower

    # 4. Locale KO manifest
    l_ko_yaml = generate_manifest_locale_ko(version)
    
    assert "멀티 에이전트" not in l_ko_yaml
    assert "에이전트" not in l_ko_yaml
    assert "통합 조율" not in l_ko_yaml
    assert "오케스트레이션" not in l_ko_yaml
    assert "텔레메트리" not in l_ko_yaml
    # A tag-line mention of peerhub (claiming Engram itself IS/bundles peerhub)
    # is still forbidden, matching the EN "- peerhub\n" tag check above; a
    # prose mention that peerhub is a separate, optional companion package
    # is accurate post-separation and is allowed (DESC_KO says exactly that).
    assert "\n  - peerhub\n" not in l_ko_yaml.lower()


def test_root_files_allow_matches_p1_10_contract():
    """P1-10: ROOT_FILES_ALLOW is exactly the 4 files the ratified doc names."""
    assert ROOT_FILES_ALLOW == {"engram.cmd", "Engram.exe", "README.md", "LICENSE"}


def test_portable_archive_matches_p1_10_contract(tmp_path):
    """P1-10: build a real archive from this checkout and verify its contents.

    create_portable_archive always writes _sys/core/release-manifest.json and
    _sys/core/release-manifests/<version>.json into the real repo tree as a
    side effect (that's the release-manifest-generation contract, not a test
    artifact) -- use an unmistakably disposable version string and delete
    both afterward so no fake entry lingers in the historical manifests dir.
    """
    import json
    import zipfile

    version = "0.0.0-test-p1-10"
    manifest_path = repo_root / "_sys" / "core" / "release-manifest.json"
    version_manifest_path = (
        repo_root / "_sys" / "core" / "release-manifests" / f"{version}.json"
    )
    assert not version_manifest_path.exists(), (
        "disposable test version manifest already exists; pick a different "
        "version string or investigate why it wasn't cleaned up last run"
    )

    try:
        zip_path, sha256_hex, count, total_uncompressed = create_portable_archive(
            repo_root, tmp_path, version
        )

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())

        root_entries = {n for n in names if "/" not in n}
        assert root_entries == {"engram.cmd", "Engram.exe", "README.md", "LICENSE"}
        assert any(n == "_sys/" or n.startswith("_sys/") for n in names)

        excluded_dir_prefixes = (
            "_sys/env/",
            "_sys/tools/",
            "_sys/data/state/",
            "_sys/data/logs/",
            "_sys/data/temp/",
        )
        for name in names:
            assert not name.startswith(excluded_dir_prefixes), name

        assert "_sys/runtimes.json" not in names
        assert "_sys/tool-catalog.v1.json" not in names
        assert not any(n.startswith(".ai/") or n == ".ai" for n in names)
        assert not any(n.startswith("_archive/") or n == "_archive" for n in names)
        assert not any(n.endswith(".bat") and "/" not in n for n in names)
        assert not any(n.endswith("wrapper.cs") for n in names)

        assert "_sys/core/release-manifest.json" in names
        with zipfile.ZipFile(zip_path) as zf:
            manifest_data = json.loads(zf.read("_sys/core/release-manifest.json"))
        assert manifest_data["version"] == version
        manifest_files = manifest_data["files"]
        # Every zip entry except the manifest itself must appear in its own
        # file list with a matching hash, and the manifest must not list any
        # file that isn't actually in the zip.
        assert set(manifest_files) == (names - {"_sys/core/release-manifest.json"})
        for arcname, expected_hash in manifest_files.items():
            with zipfile.ZipFile(zip_path) as zf:
                import hashlib

                actual = hashlib.sha256(zf.read(arcname)).hexdigest().upper()
            assert actual == expected_hash, arcname
    finally:
        manifest_path.unlink(missing_ok=True)
        version_manifest_path.unlink(missing_ok=True)
