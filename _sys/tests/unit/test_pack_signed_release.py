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


def test_signed_activation_relocates_and_blocks_wrong_active_release(tmp_path, signing):
    from optional_pack_group import initialize_fixture
    from optional_pack_release import admit, install_signed, launch_signed

    policy, descriptor = policy_and_descriptor(signing)
    root = tmp_path / "old root"
    root.mkdir()
    initialize_fixture(root)
    doc, artifact = build_release({"bin/app.py": b"print('signed generation')"})
    data = wire(doc)
    release = admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)
    exe = Path(sys.executable).resolve()
    exe_pin = sha256(exe.read_bytes()).hexdigest()
    assert install_signed(root, descriptor, 0, "runtime-a", release, policy=policy, now=NOW)["phase"] == "COMMITTED"
    assert launch_signed(root, descriptor, release, exe, exe_pin, policy=policy, now=NOW).strip() == b"signed generation"
    moved = tmp_path / "moved 경로"
    root.rename(moved)
    assert launch_signed(moved, descriptor, release, exe, exe_pin, policy=policy, now=NOW).strip() == b"signed generation"
    new_doc, new_artifact = build_release({"bin/app.py": b"print('foreign generation')"})
    new_data = wire(new_doc)
    foreign = admit(descriptor, policy, new_data, signing[2](new_data), new_artifact,
                    sha256(new_data).hexdigest(), NOW)
    with pytest.raises(ValueError):
        launch_signed(moved, descriptor, foreign, exe, exe_pin, policy=policy, now=NOW)
    assert launch_signed(moved, descriptor, release, exe, exe_pin, policy=policy, now=NOW).strip() == b"signed generation"


def test_signed_generation_switch_recovers_without_touching_retained_state(tmp_path, signing):
    from core.env_ops import SimulatedCrash
    from optional_pack_group import initialize_fixture, recover
    from optional_pack_release import admit, install_signed, launch_signed

    policy, descriptor = policy_and_descriptor(signing)
    root = tmp_path / "fixture"
    root.mkdir()
    initialize_fixture(root)
    state = root / "ContentFlow/data/user.txt"
    state.parent.mkdir(parents=True)
    state.write_bytes(b"durable owner bytes")

    def release(label):
        doc, artifact = build_release({"bin/app.py": f"print({label!r})".encode()})
        data = wire(doc)
        return admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)

    old, new = release("old"), release("new")
    exe = Path(sys.executable).resolve()
    pinned = sha256(exe.read_bytes()).hexdigest()
    install_signed(root, descriptor, 0, "runtime-a", old, policy=policy, now=NOW)
    with pytest.raises(SimulatedCrash):
        install_signed(root, descriptor, 1, "runtime-b", new, policy=policy, now=NOW,
                       crash_after="fixture-runtime")
    with pytest.raises(ValueError, match="recovery"):
        launch_signed(root, descriptor, old, exe, pinned, policy=policy, now=NOW)
    assert recover(root, descriptor, "rollback")["phase"] == "ROLLED_BACK"
    assert launch_signed(root, descriptor, old, exe, pinned, policy=policy, now=NOW).strip() == b"old"
    assert state.read_bytes() == b"durable owner bytes"


def test_adapter_starts_signed_member_and_rejects_wrong_echo(tmp_path, signing):
    from optional_pack_group import initialize_fixture
    from optional_pack_release import AdapterOutcomeUnknown, admit, install_signed, launch_adapter

    policy, descriptor = policy_and_descriptor(signing)
    root = tmp_path / "fixture"
    root.mkdir()
    initialize_fixture(root)
    app = b"raise RuntimeError('application should not run for adapter calls')"
    adapter = b"""import json, sys
req = json.load(sys.stdin)
keys = ('fixture_only', 'schema_version', 'protocol_version', 'request_id', 'parent_op_id',
        'installation_id', 'package_id', 'generation', 'operation')
reply = {k: req[k] for k in keys}
if sys.argv[1:] == ['wrong']:
    reply['parent_op_id'] = 'wrong'
if sys.argv[1:] == ['slow']:
    import time
    time.sleep(0.5)
if sys.argv[1:] == ['oversize']:
    print('x' * 65537)
    raise SystemExit(0)
reply.update(status='OK', findings=[], receipt={'effect_id':'receipt','checkpoint_sha256':None,
    'observed_state':'UNCHANGED','owned_process_ids':[]}, next_action='NONE')
if req['operation'] == 'checkpoint':
    reply['receipt'].update(observed_state='NEW',checkpoint_sha256='b'*64)
print(json.dumps(reply))
"""
    doc, artifact = build_release({"bin/app.py": app, "bin/adapter.py": adapter})
    doc["adapter_entry_rel"] = "bin/adapter.py"
    data = wire(doc)
    release = admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)
    exe = Path(sys.executable).resolve()
    pin = sha256(exe.read_bytes()).hexdigest()
    install_signed(root, descriptor, 0, "runtime-a", release, policy=policy, now=NOW)
    generation = "gen-" + release.manifest_sha256
    request = {"fixture_only": True, "schema_version": "1.0", "protocol_version": "1.0",
               "request_id": "req", "parent_op_id": "op", "installation_id": "fixture",
               "package_id": "contentflow", "generation": generation, "operation": "health",
               "working_rel": "ContentFlow/app/generations/" + generation, "checkpoint_rel": None,
               "phase": "COMMITTED", "plan_digest": "a"*64, "scope": ["PROGRAM"],
               "deadline": (NOW + timedelta(minutes=1)).isoformat()}
    answer = launch_adapter(root, descriptor, release, exe, pin, request, (), policy=policy, now=NOW)
    assert answer["status"] == "OK" and answer["request_id"] == "req"
    with pytest.raises(ValueError, match="echo"):
        launch_adapter(root, descriptor, release, exe, pin, request, ("wrong",), policy=policy, now=NOW)

    with pytest.raises(ValueError, match="output"):
        launch_adapter(root, descriptor, release, exe, pin, request, ("oversize",), policy=policy, now=NOW)
    short = request | {"operation": "checkpoint", "phase": "DRAINED", "scope": ["BACKUP"],
                       "checkpoint_rel": "ContentFlow/checkpoints/first",
                       "deadline": (NOW + timedelta(milliseconds=150)).isoformat()}
    with pytest.raises(AdapterOutcomeUnknown) as exc:
        launch_adapter(root, descriptor, release, exe, pin, short, ("slow",), policy=policy, now=NOW)
    assert isinstance(exc.value.__cause__, subprocess.TimeoutExpired)


def test_retire_and_update_refuse_live_signed_program_then_preserve_workspace(tmp_path, signing, monkeypatch):
    from contextlib import contextmanager
    from threading import Event, Thread

    from core import env_lock
    from optional_pack_group import initialize_fixture
    import optional_pack_release
    from optional_pack_release import admit, install_signed, launch_signed, remove_signed

    policy, descriptor = policy_and_descriptor(signing)
    root = tmp_path / "fixture"
    root.mkdir()
    initialize_fixture(root)
    release_child = tmp_path / "let-child-finish"
    program = ("from pathlib import Path\n"
               "from time import monotonic, sleep\n"
               f"stop = Path({ascii(str(release_child))})\n"
               "deadline = monotonic() + 15\n"
               "while not stop.is_file() and monotonic() < deadline:\n"
               "    sleep(0.01)\n"
               "assert stop.is_file()\n"
               "print('owned signed child')\n").encode("ascii")
    doc, artifact = build_release({"bin/app.py": program})
    data = wire(doc)
    release = admit(descriptor, policy, data, signing[2](data), artifact, sha256(data).hexdigest(), NOW)
    exe = Path(sys.executable).resolve()
    pin = sha256(exe.read_bytes()).hexdigest()
    trust = dict(policy=policy, now=NOW)
    install_signed(root, descriptor, 0, "runtime-a", release, **trust)
    state = root / "ContentFlow/workspaces/user.txt"
    state.parent.mkdir()
    state.write_bytes(b"original workspace")
    gate_released = Event()
    spawn = subprocess.Popen
    activation = optional_pack_release._activation
    children = []

    def observed_start(*args, **kwargs):
        children.append(spawn(*args, **kwargs))
        return children[-1]

    @contextmanager
    def observed_activation(*args):
        with activation(*args) as current:
            yield current
        gate_released.set()

    result = []
    with monkeypatch.context() as changes:
        changes.setattr("optional_pack_release.subprocess.Popen", observed_start)
        changes.setattr(optional_pack_release, "_activation", observed_activation)
        runner = Thread(target=lambda: result.append(launch_signed(root, descriptor, release, exe, pin, **trust)))
        runner.start()
        try:
            assert gate_released.wait(10)
            assert env_lock.inspect(root)["state"] == "free"
            assert children[0].poll() is None
            with pytest.raises(ValueError, match="execution lease"):
                remove_signed(root, descriptor, 1, release, **trust)
            with pytest.raises(ValueError, match="execution lease"):
                install_signed(root, descriptor, 1, "runtime-a", release, **trust)
        finally:
            release_child.touch()
            runner.join(timeout=10)
    assert result and result[0].strip() == b"owned signed child"
    assert remove_signed(root, descriptor, 1, release, **trust)["phase"] == "COMMITTED"
    with pytest.raises(ValueError, match="active signed generation"):
        launch_signed(root, descriptor, release, exe, pin, **trust)
    assert install_signed(root, descriptor, 2, "runtime-a", release, reuse_retained=True,
                          **trust)["phase"] == "COMMITTED"
    assert launch_signed(root, descriptor, release, exe, pin, **trust).strip() == b"owned signed child"
    assert state.read_bytes() == b"original workspace"
