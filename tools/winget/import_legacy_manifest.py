#!/usr/bin/env python3
"""
Imports legacy release manifest for version 3.2.6 from GitHub.
Downloads the zip, extracts it, computes sha256 for all files,
and writes release-manifests/3.2.6.json along with its defaults.
"""

import argparse
import hashlib
import json
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
import sys

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="3.2.6")
    args = parser.parse_args()
    version = args.version

    repo_root = Path(__file__).resolve().parent.parent.parent
    manifests_dir = repo_root / "_sys" / "core" / "release-manifests"
    defaults_dir = manifests_dir / f"{version}-defaults"
    
    # Create directories
    manifests_dir.mkdir(parents=True, exist_ok=True)
    defaults_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching release data for v{version}...")
    api_url = f"https://api.github.com/repos/greatgc-flow/Engram/releases/tags/v{version}"
    try:
        with urllib.request.urlopen(api_url) as resp:
            release_data = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"Failed to fetch release info: {e}")
        return 1
    
    asset = next((a for a in release_data["assets"] if a["name"] == f"Engram-v{version}-portable-x64.zip"), None)
    if not asset:
        print("Could not find the expected zip asset.")
        return 1

    api_digest = asset.get("digest")
    if not api_digest or not api_digest.lower().startswith("sha256:"):
        print(f"Release has no usable sha256 digest for the asset; refusing (got: {api_digest!r}).")
        return 1
    expected_sha256 = api_digest.split(":", 1)[1].lower()

    download_url = asset["browser_download_url"]
    print(f"Downloading {download_url}...")

    with tempfile.TemporaryFile() as tmp_file:
        with urllib.request.urlopen(download_url) as resp:
            shutil_copyfileobj = getattr(urllib.request, "shutil", __import__("shutil")).copyfileobj
            shutil_copyfileobj(resp, tmp_file)

        tmp_file.seek(0)
        zip_sha256 = hashlib.sha256()
        while True:
            chunk = tmp_file.read(65536)
            if not chunk:
                break
            zip_sha256.update(chunk)
        zip_sha256_hex = zip_sha256.hexdigest().lower()
        print(f"Zip SHA256: {zip_sha256_hex}")

        # Verify against the GitHub API's own digest for this asset -- this is
        # the authenticity gate: everything downstream (M1 migration's decision
        # about which files are safely "shipped and deletable") trusts this
        # manifest, so a mismatch must refuse rather than merely warn.
        if zip_sha256_hex != expected_sha256:
            print(
                f"REFUSING: downloaded zip sha256 ({zip_sha256_hex}) does not match "
                f"the GitHub API asset digest ({expected_sha256})."
            )
            return 1
        print("Zip SHA256 verified against the GitHub API asset digest.")

        tmp_file.seek(0)
        manifest_data = {
            "version": version,
            "files": {}
        }
        
        with zipfile.ZipFile(tmp_file, "r") as zf:
            for item in zf.infolist():
                if item.is_dir():
                    continue
                # compute hash
                with zf.open(item) as f:
                    content = f.read()
                    manifest_data["files"][item.filename] = compute_sha256(content)
                    
                    # Extract defaults
                    if item.filename == "_sys/runtimes.json":
                        (defaults_dir / "runtimes.json").write_bytes(content)
                        print(f"Extracted {item.filename} to defaults.")
                    elif item.filename == "_sys/tool-catalog.v1.json":
                        (defaults_dir / "tool-catalog.v1.json").write_bytes(content)
                        print(f"Extracted {item.filename} to defaults.")

    manifest_path = manifests_dir / f"{version}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)
    
    print(f"Wrote manifest to {manifest_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
