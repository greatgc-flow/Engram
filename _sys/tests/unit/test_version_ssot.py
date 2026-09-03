import sys
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from _sys.core.version import load_version_info

def test_version_json_exists():
    version_file = repo_root / "_sys" / "core" / "version.json"
    assert version_file.exists(), "version.json does not exist"

def test_version_json_valid():
    info = load_version_info()
    assert "version" in info
    assert "winget_schema_version" in info
    
    # Simple semver check for version
    version_parts = info["version"].split(".")
    assert len(version_parts) == 3
    for p in version_parts:
        assert p.isdigit()

def test_build_package_default_version():
    # Import build_package and check DEFAULT_VERSION
    from tools.winget.build_package import DEFAULT_VERSION, SCHEMA_VERSION
    info = load_version_info()
    assert DEFAULT_VERSION == info["version"]
    assert SCHEMA_VERSION == info["winget_schema_version"]
