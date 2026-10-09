"""Check downloaded assets against the frozen candidate before use or publish."""
import hashlib
import json
import os
from pathlib import Path
import sys

candidate = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for field, variable in (("tag", "GITHUB_REF_NAME"), ("commit", "GITHUB_SHA")):
    if os.environ.get(variable) and candidate.get(field) != os.environ[variable]:
        raise SystemExit(f"HOLD: candidate {field} differs from workflow identity")
if len(sys.argv) == 4:
    evidence = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    for field, variable in (("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT")):
        if not os.environ.get(variable) or evidence.get(field) != os.environ[variable]:
            raise SystemExit(f"HOLD: evidence {field} differs from workflow identity")
assets = Path(sys.argv[2])
actual = {}
for path in sorted(assets.rglob("*")):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise SystemExit("HOLD: downloaded assets contain links")
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual[path.relative_to(assets).as_posix()] = digest.hexdigest()
if not actual or actual != candidate["candidate_sha256s"]:
    raise SystemExit("HOLD: downloaded asset hashes differ from candidate")
print("PASS: downloaded assets match candidate")
