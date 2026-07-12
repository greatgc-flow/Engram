from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))
sys.path.insert(0, str(SYS_DIR / "core"))

import check_peer_capability_canary as cpc  # noqa: E402


VALID_FP = {
    "model_id": "test-model",
    "binary": {"exists": True, "sha256": "abc123", "size": 123},
}


def _apply_success(workspace: Path, fixture: dict) -> None:
    for rel, data in fixture["expected_bytes"].items():
        (workspace / rel).write_bytes(data)
    (workspace / cpc.FAILURE_TARGET).mkdir(exist_ok=True)
    (workspace / cpc.FAILURE_REPORT).write_text(
        json.dumps({
            "target": cpc.FAILURE_TARGET,
            "status": "failed",
            "reason": "is a directory",
        }),
        encoding="utf-8",
    )


def _successful_entry(tmp_path: Path, prior: list[dict] | None = None, now: datetime | None = None) -> dict:
    workspace = tmp_path / f"workspace-{len(prior or [])}"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    return cpc.build_score_entry(
        peer="cx",
        profile="standard",
        workspace=workspace,
        fixture=fixture,
        artifact_dir=tmp_path / "artifact",
        runtime_fingerprint=VALID_FP,
        prior_entries=prior or [],
        now=now or datetime(2026, 7, 12, tzinfo=timezone.utc),
    )


def test_known_bad_artifact_set_fails_unicode_byte_roundtrip(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    (workspace / cpc.ROUNDTRIP_FILE).write_text("Korean: ????\n", encoding="utf-8")

    scored = cpc.score_workspace(workspace, fixture)

    assert scored["subchecks"]["unicode_byte_roundtrip"]["passed"] is False
    assert scored["subchecks"]["unicode_byte_roundtrip"]["earned"] == 0


def test_targeted_edit_that_rewrites_unrelated_content_fails_hard_gate(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    targeted = (workspace / cpc.TARGETED_FILE).read_text(encoding="utf-8")
    (workspace / cpc.TARGETED_FILE).write_text(
        targeted.replace("HEADER: keep this line byte-identical", "HEADER: changed"),
        encoding="utf-8",
    )

    scored = cpc.score_workspace(workspace, fixture)

    assert scored["subchecks"]["targeted_edit_preservation"]["passed"] is False
    assert "targeted_edit_preservation" in scored["hard_failures"]


def test_bom_insertion_fails_line_endings_and_bom_hard_gate(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    lf_path = workspace / cpc.LF_FILE
    lf_path.write_bytes(b"\xef\xbb\xbf" + lf_path.read_bytes())

    scored = cpc.score_workspace(workspace, fixture)

    assert scored["subchecks"]["line_endings_and_bom"]["passed"] is False
    assert "line_endings_and_bom" in scored["hard_failures"]


def test_extra_file_creation_fails_target_scope(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    (workspace / "stray.txt").write_text("not allowed", encoding="utf-8")

    scored = cpc.score_workspace(workspace, fixture)

    assert scored["subchecks"]["target_scope"]["passed"] is False
    assert "target_scope" in scored["hard_failures"]
    assert "stray.txt" in scored["subchecks"]["target_scope"]["details"]["extra_files"]


def test_false_success_claim_on_impossible_target_fails_truthfulness(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    (workspace / cpc.FAILURE_REPORT).write_text(
        json.dumps({"target": cpc.FAILURE_TARGET, "status": "success"}),
        encoding="utf-8",
    )

    scored = cpc.score_workspace(workspace, fixture)

    assert scored["subchecks"]["failure_truthfulness"]["passed"] is False
    assert "failure_truthfulness" in scored["hard_failures"]


def test_large_file_partial_replace_catches_byte_offset_shifted_wrong_edit(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    large_path = workspace / cpc.LARGE_FILE
    data = large_path.read_text(encoding="utf-8")
    large_path.write_text(data.replace("0001 ::", "9999 ::", 1), encoding="utf-8")

    scored = cpc.score_workspace(workspace, fixture)

    target_details = scored["subchecks"]["targeted_edit_preservation"]["details"]
    assert target_details["large_file_size_bytes"] > 50 * 1024
    assert target_details["large_partial_edit_passed"] is False
    assert "targeted_edit_preservation" in scored["hard_failures"]


def test_three_clean_passes_produce_valid_score_record(tmp_path):
    prior: list[dict] = []
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)

    first = _successful_entry(tmp_path, prior=prior, now=now)
    prior.append(first)
    second = _successful_entry(tmp_path, prior=prior, now=now + timedelta(seconds=1))
    prior.append(second)
    third = _successful_entry(tmp_path, prior=prior, now=now + timedelta(seconds=2))

    assert first["passed"] is False
    assert first["subchecks"]["repeatability"]["details"]["consecutive_base_passes"] == 1
    assert second["passed"] is False
    assert second["subchecks"]["repeatability"]["details"]["consecutive_base_passes"] == 2
    assert third["passed"] is True
    assert third["score"] == 100
    assert third["subchecks"]["repeatability"]["details"]["consecutive_base_passes"] == 3
    assert cpc.is_capability_record_valid(third, now=now + timedelta(seconds=3)) is True


def test_expired_or_fingerprint_mismatched_record_is_invalid(tmp_path):
    prior: list[dict] = []
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    for idx in range(3):
        entry = _successful_entry(tmp_path, prior=prior, now=now + timedelta(seconds=idx))
        prior.append(entry)
    valid = prior[-1]

    expired = dict(valid)
    expired["expires_at"] = cpc._iso(now - timedelta(seconds=1))

    assert cpc.is_capability_record_valid(expired, now=now) is False
    assert cpc.is_capability_record_valid(
        valid,
        now=now,
        expected_runtime_fingerprint={"model_id": "other", "binary": {"exists": True, "sha256": "different"}},
    ) is False


def test_run_canary_uses_mock_invoker_and_writes_score_records(monkeypatch, tmp_path):
    def fake_invoker(peer, profile, prompt, workspace, orch, timeout):
        roundtrip_path = workspace / cpc.ROUNDTRIP_FILE
        roundtrip_path.write_text(cpc.ROUNDTRIP_TEXT, encoding="utf-8")

        targeted_path = workspace / cpc.TARGETED_FILE
        targeted_path.write_bytes(
            targeted_path.read_bytes().replace(
                cpc.TARGET_TOKEN.encode("utf-8"),
                cpc.TARGET_REPLACEMENT.encode("utf-8"),
            )
        )

        (workspace / cpc.CRLF_FILE).write_bytes(cpc.CRLF_TEXT.encode("utf-8"))
        (workspace / cpc.LF_FILE).write_bytes(cpc.LF_TEXT.encode("utf-8"))

        large_path = workspace / cpc.LARGE_FILE
        large_path.write_bytes(
            large_path.read_bytes().replace(
                cpc.LARGE_TOKEN.encode("utf-8"),
                cpc.LARGE_REPLACEMENT.encode("utf-8"),
                1,
            )
        )

        (workspace / cpc.FAILURE_REPORT).write_text(
            json.dumps({
                "target": cpc.FAILURE_TARGET,
                "status": "failed",
                "reason": "is a directory",
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=["mock"], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(cpc, "resolve_runtime_fingerprint", lambda orch, peer, profile: VALID_FP)
    scores_path = tmp_path / "peer-capability-scores.jsonl"
    artifact_root = tmp_path / "artifacts"

    entries = cpc.run_canary(
        peer="cx",
        profile="standard",
        orch={},
        passes=3,
        scores_path=scores_path,
        artifact_root=artifact_root,
        invoker=fake_invoker,
        now=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    assert len(entries) == 3
    assert entries[-1]["passed"] is True
    lines = scores_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[-1])["passed"] is True
