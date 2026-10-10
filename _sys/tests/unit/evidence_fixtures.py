"""Complete promotion evidence fixtures for offline tests."""
import json
from pathlib import Path

def evidence_fixture(candidate, kind, run_id="12", run_attempt="1"):
    candidate = Path(candidate)
    hashes = json.loads(candidate.read_text())["candidate_sha256s"]
    data = dict(status="PASS", candidate_sha256s=hashes, cancelled=False, skipped=False,
                run_id=run_id, run_attempt=run_attempt)
    if kind == "upgrade":
        data.update(previous_tag="v0", updater_source="previous", scenarios={"upgrade": "PASS", "rollback": "PASS"})
    path = candidate.parent / ("fixture-" + kind + ".json")
    path.write_text(json.dumps(data))
    return path

from contextlib import contextmanager
import shutil
import uuid

@contextmanager
def temporary_directory(tmp_path, dir=None, prefix="evidence-fixture-", **kwargs):
    path = Path(tmp_path) / (prefix + uuid.uuid4().hex)
    path.mkdir(mode=0o777)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)
