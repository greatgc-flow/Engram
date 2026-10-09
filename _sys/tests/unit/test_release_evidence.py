"""Offline release gate contracts; these fail when the checker is absent."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "release_evidence.py"
HASH = hashlib.sha256(b"release").hexdigest()
COMMIT = "a" * 40


def run_cli(*args):
    if args and args[0] == "verify":
        args = (*args, "--no-winget-evidence", "--run-id", "123", "--run-attempt", "1")
        if "--policy" not in args:
            args = (*args, "--policy", SCRIPT.parents[2] / "release_policy.json")
    env = dict(os.environ, RELEASE_TAG="v1.2.3", GITHUB_SHA=COMMIT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True, text=True, env=env, check=False,
    )


def write_json(path, value):
    if isinstance(value, dict) and 'status' in value:
        value = {"cancelled": False, "skipped": False, "run_id": "123", "run_attempt": "1", **value}
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def candidate(tmp_path):
    return write_json(tmp_path / "candidate.json", {
        "tag": "v1.2.3", "commit": COMMIT,
        "candidate_sha256s": {"release.zip": HASH},
    })


def test_freeze_hashes_every_asset_with_relative_names(tmp_path):
    assets = tmp_path / "assets"
    (assets / "nested").mkdir(parents=True)
    (assets / "release.zip").write_bytes(b"release")
    (assets / "nested" / "source.zip").write_bytes(b"source")
    out = tmp_path / "candidate.json"
    result = run_cli("freeze", "--assets", assets, "--out", out)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "tag": "v1.2.3", "commit": COMMIT,
        "candidate_sha256s": {
            "release.zip": HASH,
            "nested/source.zip": hashlib.sha256(b"source").hexdigest(),
        },
    }


def test_freeze_never_overwrites_existing_candidate(tmp_path, candidate):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "release.zip").write_bytes(b"rebuilt")
    before = candidate.read_bytes()
    result = run_cli("freeze", "--assets", assets, "--out", candidate)
    assert result.returncode != 0
    assert candidate.read_bytes() == before
    assert result.stdout.startswith("HOLD:")


@pytest.mark.parametrize("mode", ["missing", "empty", "output_inside_assets"])
def test_freeze_invalid_asset_directory_holds(tmp_path, mode):
    assets = tmp_path / "assets"
    out = tmp_path / "candidate.json"
    if mode != "missing":
        assets.mkdir()
    if mode == "output_inside_assets":
        (assets / "release.zip").write_bytes(b"release")
        out = assets / "candidate.json"
    result = run_cli("freeze", "--assets", assets, "--out", out)
    assert result.returncode != 0
    assert not out.exists()


def test_exact_pass_evidence_promotes(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("status", [None, "FAIL", "CANCELLED", "SKIPPED", "PENDING", "RUNNING", "UNKNOWN", "STALE", "UNAVAILABLE", "pass"])
def test_non_pass_status_holds(tmp_path, candidate, status):
    evidence = write_json(tmp_path / "evidence.json", {
                "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": status, "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence")
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize("hashes", [{}, {"release.zip": "b" * 64}, {"other.zip": HASH}, {"release.zip": HASH, "extra.zip": HASH}, None, [HASH]])
def test_missing_extra_or_mismatched_hashes_hold(tmp_path, candidate, hashes):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": hashes,
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence").returncode != 0


@pytest.mark.parametrize("flag", ["cancelled", "skipped"])
def test_pass_cannot_override_cancelled_or_skipped(tmp_path, candidate, flag):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH}, flag: True,
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence").returncode != 0


@pytest.mark.parametrize("content", [None, "{", "[]", '{"status":"PASS","status":"FAIL"}'])
def test_missing_or_malformed_evidence_holds(tmp_path, candidate, content):
    evidence = tmp_path / "evidence.json"
    if content is not None:
        evidence.write_text(content, encoding="utf-8")
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence")
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize("field,value", [("tag", ""), ("commit", "unknown"), ("candidate_sha256s", {}), ("candidate_sha256s", {"../release.zip": HASH}), ("candidate_sha256s", {"release.zip": "invalid"})])
def test_invalid_candidate_holds(tmp_path, candidate, field, value):
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data[field] = value
    write_json(candidate, data)
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": data["candidate_sha256s"],
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence").returncode != 0


def test_upgrade_evidence_pass_promotes(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
        "updater_source": "previous", "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("status", [None, "FAIL", "HOLD", "CANCELLED", "SKIPPED"])
def test_upgrade_evidence_non_pass_holds(tmp_path, candidate, status):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": status, "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
        "updater_source": "previous", "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")


@pytest.mark.parametrize("prev_tag", [None, "", "   ", "v1.2.3", "tag with spaces"])
def test_upgrade_evidence_invalid_or_matching_tag_holds(tmp_path, candidate, prev_tag):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": prev_tag, "cancelled": False, "skipped": False,
        "updater_source": "previous", "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")


def test_upgrade_evidence_hash_mismatch_holds(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": "0" * 64},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
        "updater_source": "previous", "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")


def test_upgrade_evidence_missing_file_holds(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", tmp_path / "nonexistent.json",
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")



def test_upgrade_evidence_required_by_default(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence)
    assert result.returncode == 1
    assert result.stdout == "HOLD: upgrade evidence is required\n"


def test_upgrade_evidence_options_are_mutually_exclusive(tmp_path, candidate):
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", tmp_path / "evidence.json",
        "--upgrade-evidence", tmp_path / "upgrade.json", "--no-upgrade-evidence",
    )
    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr


@pytest.mark.parametrize("flag", ["cancelled", "skipped"])
@pytest.mark.parametrize("value", ["missing", None, True, 0, 1, "false"])
def test_upgrade_evidence_requires_explicit_false_flags(tmp_path, candidate, flag, value):
    evidence = write_json(tmp_path / "evidence.json", {
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    data = {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
        "updater_source": "previous", "scenarios": {"upgrade": "PASS", "rollback": "PASS"},
    }
    if value == "missing":
        del data[flag]
    else:
        data[flag] = value
    upgrade = tmp_path / "upgrade.json"
    upgrade.write_text(json.dumps(data), encoding="utf-8")
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade,
    )
    assert result.returncode == 1
    assert result.stdout == f"HOLD: upgrade evidence is {flag} or has an invalid flag\n"


@pytest.mark.parametrize("provider,environment", [
    ("windows-sandbox", "self-hosted"),
    ("hosted-ephemeral-vm", "github-hosted"),
])
def test_policy_allows_provider_pairs(tmp_path, candidate, provider, environment):
    evidence = write_json(tmp_path / "sandbox.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "provider": provider, "runner_environment": environment,
        "workflow_run_id": "123", "image": "runner image version",
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence,
                     "--no-upgrade-evidence")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("field", ["provider", "runner_environment", "workflow_run_id", "image"])
@pytest.mark.parametrize("value", [None, "", "   ", 123])
def test_required_sandbox_metadata_holds(tmp_path, candidate, field, value):
    data = {"status": "PASS", "candidate_sha256s": {"release.zip": HASH},
            "provider": "windows-sandbox", "runner_environment": "self-hosted",
            "workflow_run_id": "123", "image": "Windows 11"}
    if value is None:
        del data[field]
    else:
        data[field] = value
    evidence = write_json(tmp_path / "sandbox.json", data)
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence,
                   "--no-upgrade-evidence").returncode == 1


@pytest.mark.parametrize("provider,environment", [
    ("unknown", "self-hosted"), ("windows-sandbox", "github-hosted"),
    ("hosted-ephemeral-vm", "self-hosted"),
])
def test_unknown_or_mismatched_provider_holds(tmp_path, candidate, provider, environment):
    evidence = write_json(tmp_path / "sandbox.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "provider": provider, "runner_environment": environment,
        "workflow_run_id": "123", "image": "Windows 11",
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence,
                   "--no-upgrade-evidence").returncode == 1


@pytest.mark.parametrize("policy_data", [None, {}, {"sandbox_providers": []},
    {"sandbox_providers": "windows-sandbox"}, {"sandbox_providers": ["unknown"]},
    {"sandbox_providers": ["hosted-ephemeral-vm"]}])
def test_missing_invalid_or_restrictive_policy_holds(tmp_path, candidate, policy_data):
    policy = tmp_path / "policy.json"
    if policy_data is not None:
        write_json(policy, policy_data)
    evidence = write_json(tmp_path / "sandbox.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "provider": "windows-sandbox", "runner_environment": "self-hosted",
        "workflow_run_id": "123", "image": "Windows 11",
        "sandbox_providers": ["windows-sandbox", "hosted-ephemeral-vm"],
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence,
                   "--no-upgrade-evidence", "--policy", policy).returncode == 1


def test_repository_policy_is_required_by_default(tmp_path, candidate):
    import importlib.util
    spec = importlib.util.spec_from_file_location("release_policy_gate", SCRIPT)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    evidence = write_json(tmp_path / "sandbox.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "provider": "hosted-ephemeral-vm", "runner_environment": "github-hosted",
        "workflow_run_id": "123", "image": "Windows runner image",
    })
    gate.verify(candidate, evidence, no_upgrade_evidence=True, no_winget_evidence=True,
                run_id="123", run_attempt="1")
    with pytest.raises((gate.Hold, OSError)):
        gate.verify(candidate, evidence, no_upgrade_evidence=True,
                    no_winget_evidence=True, policy_path=tmp_path / "missing.json",
                    run_id="123", run_attempt="1")
