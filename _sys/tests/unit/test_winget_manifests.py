import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.winget.build_package import (
    generate_manifest_version,
    generate_manifest_installer,
    generate_manifest_locale_en,
    generate_manifest_locale_ko,
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
