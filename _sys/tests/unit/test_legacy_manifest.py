import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from _sys.core.root import find_root

repo_root = find_root(__file__).parent
manifest_path = repo_root / "_sys" / "core" / "release-manifests" / "3.2.6.json"


def test_legacy_manifest_engram_cmd_hash():
    if not manifest_path.exists():
        pytest.skip(f"{manifest_path} not present in this checkout")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.loads(f.read())

    assert "engram.cmd" in manifest["files"]
    manifest_hash = manifest["files"]["engram.cmd"]

    proc = subprocess.run(
        ["git", "cat-file", "-p", "v3.2.6:engram.cmd"],
        cwd=str(repo_root),
        capture_output=True,
    )
    assert proc.returncode == 0, f"git cat-file v3.2.6:engram.cmd failed: {proc.stderr!r}"
    blob_hash = hashlib.sha256(proc.stdout).hexdigest().upper()
    assert manifest_hash == blob_hash, f"Manifest hash {manifest_hash} != blob hash {blob_hash}"
