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
        args = (*args, "--no-winget-evidence")
    env = dict(os.environ, RELEASE_TAG="v1.2.3", GITHUB_SHA=COMMIT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True, text=True, env=env, check=False,
    )


def write_json(path, value):
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
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("status", [None, "FAIL", "CANCELLED", "SKIPPED", "PENDING", "RUNNING", "UNKNOWN", "STALE", "UNAVAILABLE", "pass"])
def test_non_pass_status_holds(tmp_path, candidate, status):
    evidence = write_json(tmp_path / "evidence.json", {
        "status": status, "candidate_sha256s": {"release.zip": HASH},
    })
    result = run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence")
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize("hashes", [{}, {"release.zip": "b" * 64}, {"other.zip": HASH}, {"release.zip": HASH, "extra.zip": HASH}, None, [HASH]])
def test_missing_extra_or_mismatched_hashes_hold(tmp_path, candidate, hashes):
    evidence = write_json(tmp_path / "evidence.json", {
        "status": "PASS", "candidate_sha256s": hashes,
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence").returncode != 0


@pytest.mark.parametrize("flag", ["cancelled", "skipped"])
def test_pass_cannot_override_cancelled_or_skipped(tmp_path, candidate, flag):
    evidence = write_json(tmp_path / "evidence.json", {
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
        "status": "PASS", "candidate_sha256s": data["candidate_sha256s"],
    })
    assert run_cli("verify", "--candidate", candidate, "--evidence", evidence, "--no-upgrade-evidence").returncode != 0


def test_upgrade_evidence_pass_promotes(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("status", [None, "FAIL", "HOLD", "CANCELLED", "SKIPPED"])
def test_upgrade_evidence_non_pass_holds(tmp_path, candidate, status):
    evidence = write_json(tmp_path / "evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": status, "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
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
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": prev_tag, "cancelled": False, "skipped": False,
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")


def test_upgrade_evidence_hash_mismatch_holds(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    upgrade_evidence = write_json(tmp_path / "upgrade_evidence.json", {
        "status": "PASS", "candidate_sha256s": {"release.zip": "0" * 64},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
    })
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade_evidence,
    )
    assert result.returncode != 0
    assert result.stdout.startswith("HOLD:")


def test_upgrade_evidence_missing_file_holds(tmp_path, candidate):
    evidence = write_json(tmp_path / "evidence.json", {
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
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
    })
    data = {
        "status": "PASS", "candidate_sha256s": {"release.zip": HASH},
        "previous_tag": "v1.2.2", "cancelled": False, "skipped": False,
    }
    if value == "missing":
        del data[flag]
    else:
        data[flag] = value
    upgrade = write_json(tmp_path / "upgrade.json", data)
    result = run_cli(
        "verify", "--candidate", candidate, "--evidence", evidence,
        "--upgrade-evidence", upgrade,
    )
    assert result.returncode == 1
    assert result.stdout == f"HOLD: upgrade evidence is {flag} or has an invalid flag\n"
