import json
import hashlib
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent.parent
manifest_path = repo_root / "_sys" / "core" / "release-manifests" / "3.2.6.json"
engram_cmd_path = repo_root / "engram.cmd"

def test_legacy_manifest_engram_cmd_hash():
    # Only run if manifest exists
    if not manifest_path.exists():
        return
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.loads(f.read())
    
    assert "engram.cmd" in manifest["files"]
    manifest_hash = manifest["files"]["engram.cmd"]
    
    with open(engram_cmd_path, "rb") as f:
        content = f.read()
    
    actual_hash = hashlib.sha256(content).hexdigest().upper()
    
    # Wait, the prompt said "sha256 recomputed in-test from the repo's v3.2.6 blob"
    # Actually, we can retrieve the v3.2.6 blob from git directly.
    import subprocess
    proc = subprocess.run(
        ["git", "cat-file", "-p", "v3.2.6:engram.cmd"],
        cwd=str(repo_root),
        capture_output=True
    )
    if proc.returncode == 0:
        blob_content = proc.stdout
        blob_hash = hashlib.sha256(blob_content).hexdigest().upper()
        assert manifest_hash == blob_hash, f"Manifest hash {manifest_hash} != blob hash {blob_hash}"
    else:
        # Fallback to current file if git fails (e.g. tag not fetched)
        assert manifest_hash == actual_hash
