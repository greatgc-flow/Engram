"""Tested signed admission with an independently pinned, ephemeral trust key."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/feasibility"))
from pack_catalog import load_fixtures

NOW = datetime(2026, 11, 28, tzinfo=timezone.utc)
LOCK = sha256(b"synthetic runtime lock").hexdigest()
SBOM = sha256(b"synthetic SBOM").hexdigest()


@pytest.fixture
def signing(tmp_path):
    mapped = shutil.which("openssl")
    if mapped is None and os.name == "nt":
        git = shutil.which("git")
        candidate = Path(git).parents[1] / "usr/bin/openssl.exe" if git else None
        if candidate and candidate.is_file():
            mapped = candidate
    if mapped is None:
        pytest.skip("OpenSSL CLI is unavailable")
    openssl = Path(mapped).resolve()
    private, public = tmp_path / "private.pem", tmp_path / "public.pem"

    def run(*args):
        subprocess.run([openssl, *args], check=True, capture_output=True, timeout=15)

    run("genpkey", "-algorithm", "ED25519", "-out", private)
    run("pkey", "-in", private, "-pubout", "-out", public)

    def sign(raw):
        manifest, signature = tmp_path / "manifest.json", tmp_path / "manifest.sig"
        manifest.write_bytes(raw)
        run("pkeyutl", "-sign", "-inkey", private, "-rawin", "-in", manifest, "-out", signature)
        return signature.read_bytes()

    return openssl, public.read_bytes(), sign


def build_release(members):
    bundle = BytesIO()
    with ZipFile(bundle, "w") as zipped:
        for name, data in members.items():
            zipped.writestr(name, data)
    bundle = bundle.getvalue()
    manifest = {"fixture_only": True, "schema_version": "1.0", "package_id": "contentflow",
                "version": "0.1.0", "profile": "lite", "host": "windows-x64", "manager_protocol": "1.0",
                "artifact_ref": "synthetic-package", "artifact_sha256": sha256(bundle).hexdigest(),
                "artifact_bytes": len(bundle), "expanded_bytes": sum(map(len, members.values())),
                "members": [{"path_rel": name, "sha256": sha256(data).hexdigest(),
                             "bytes": len(data), "asset_class": "PROGRAM"} for name, data in members.items()],
                "runtime_lock_sha256": LOCK, "sbom_sha256": SBOM, "license_evidence_ref": "fixture-license",
                "signing_key_id": "synthetic-key", "signature_ref": "manifest.sig", "app_entry_rel": "bin/app.py",
                "adapter_entry_rel": None, "read_schema_min": 1, "read_schema_max": 1}
    return manifest, bundle


def wire(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def policy_and_descriptor(signing):
    from optional_pack_release import TrustPolicy
    openssl, public, _ = signing
    policy = TrustPolicy(openssl, sha256(openssl.read_bytes()).hexdigest(), "synthetic-key",
                         public, NOW + timedelta(days=1), False, LOCK, SBOM, "fixture-license")
    descriptor, = load_fixtures([REPO / "_sys/tests/fixtures/optional-pack/cf.descriptor.json"])
    return policy, descriptor


def test_signed_release_stage_and_exact_program_execution(tmp_path, signing):
    from optional_pack_release import admit, run_staged, stage

    policy, descriptor = policy_and_descriptor(signing)
    program = b'import json; print(json.dumps({"fixture": True, "status": "ready"}))\n'
    doc, artifact = build_release({"bin/app.py": program})
    data = wire(doc)
    result = admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)
    root = tmp_path / "staged Korean 경로"
    stage(result, root)
    output = run_staged(result, root, Path(sys.executable).resolve(),
                        sha256(Path(sys.executable).resolve().read_bytes()).hexdigest())
    assert json.loads(output) == {"fixture": True, "status": "ready"}
    (root / "bin/app.py").write_bytes(b"changed")
    with pytest.raises(ValueError):
        run_staged(result, root, Path(sys.executable).resolve(),
                   sha256(Path(sys.executable).resolve().read_bytes()).hexdigest())


def test_signed_release_rejects_stale_trust_and_byte_mismatch(signing):
    from optional_pack_release import admit
    policy, descriptor = policy_and_descriptor(signing)
    doc, artifact = build_release({"bin/app.py": b"print('fixture')"})
    data = wire(doc)
    signature = signing[2](data)
    for trust, raw, sig, archive, expected, now in (
        (replace(policy, revoked=True), data, signature, artifact, sha256(data).hexdigest(), NOW),
        (policy, data, signature, artifact, sha256(data).hexdigest(), policy.valid_until),
        (policy, data, signature, artifact, "0" * 64, NOW),
        (policy, data, bytes(64), artifact, sha256(data).hexdigest(), NOW),
        (policy, data, signature, artifact[:-1] + b"X", sha256(data).hexdigest(), NOW),
        (replace(policy, openssl_sha256="0" * 64), data, signature, artifact, sha256(data).hexdigest(), NOW),
    ):
        with pytest.raises(ValueError):
            admit(descriptor, trust, raw, sig, archive, expected, now)


@pytest.mark.parametrize("name", ["../outside", "bin/APP.PY", "bin/com1.txt", "bin/sub/../x", "bin/app.py/x"])
def test_valid_signature_does_not_admit_unsafe_archive_names(name, signing):
    from optional_pack_release import admit
    policy, descriptor = policy_and_descriptor(signing)
    doc, artifact = build_release({"bin/app.py": b"print('fixture')", name: b"unexpected"})
    data = wire(doc)
    with pytest.raises(ValueError):
        admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)
