from __future__ import annotations

import json
import hashlib
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))
sys.path.insert(0, str(SYS_DIR / "core"))

import check_peer_capability_canary as cpc  # noqa: E402


VALID_FP = {
    "peer": "cx",
    "profile": "standard",
    "model_id": "test-model",
    "reasoning_effort": "low",
    "adapter": "CodexAdapter",
    "invoke_args": ["exec", "{query}"],
    "profile_config_sha256": "a" * 64,
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


def test_same_runtime_rejects_same_model_binary_different_reasoning_effort():
    changed = {**VALID_FP, "reasoning_effort": "high"}

    assert cpc._same_runtime(VALID_FP, changed) is False


def test_same_runtime_rejects_different_adapter():
    changed = {**VALID_FP, "adapter": "AgyAdapter"}

    assert cpc._same_runtime(VALID_FP, changed) is False


def test_same_runtime_accepts_identical_v2_tuple():
    assert cpc.runtime_fingerprint_valid(VALID_FP) is True
    assert cpc._same_runtime(VALID_FP, dict(VALID_FP)) is True


def test_legacy_runtime_fingerprint_is_invalid_and_stale():
    legacy = {
        "model_id": VALID_FP["model_id"],
        "binary": dict(VALID_FP["binary"]),
    }

    assert cpc.runtime_fingerprint_valid(legacy) is False
    assert cpc._same_runtime(legacy, VALID_FP) is False


def test_record_with_changed_profile_config_hash_falls_back_from_empirical(tmp_path):
    prior: list[dict] = []
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    for index in range(3):
        prior.append(_successful_entry(tmp_path, prior=prior, now=now + timedelta(seconds=index)))
    expected = {**VALID_FP, "profile_config_sha256": "b" * 64}

    assert cpc.is_capability_record_valid(
        prior[-1], now=now + timedelta(seconds=3), expected_runtime_fingerprint=expected
    ) is False


def test_resolve_runtime_fingerprint_hashes_raw_profile_config_deterministically(monkeypatch):
    profile = {
        "profile_args": ["--model", "test-model"],
        "reasoning_effort": "low",
        "model_id": "test-model",
        "intelligence_evidence": {"estimate": {"kind": "point", "value": 99}},
    }
    orch = {
        "hub_nodes": [{
            "node_id": "cx",
            "type": "peer",
            "adapter_class": "CodexAdapter",
            "invoke": "codex",
            "invoke_args": ["exec", "{query}"],
            "profiles": {"standard": profile},
        }]
    }
    monkeypatch.setattr(cpc, "real_binary", lambda _peer, _orch: Path("codex"))
    monkeypatch.setattr(cpc, "fingerprint", lambda _binary: {"exists": True, "sha256": "binary"})

    first = cpc.resolve_runtime_fingerprint(orch, "cx", "standard")
    reordered = json.loads(json.dumps(orch, sort_keys=True))
    second = cpc.resolve_runtime_fingerprint(reordered, "cx", "standard")
    expected_hash = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    assert first == second
    assert first["profile_config_sha256"] == expected_hash
    assert first["reasoning_effort"] == "low"
    assert first["adapter"] == "CodexAdapter"
    assert first["invoke_args"] == ["exec", "{query}"]


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


def test_pty_invoker_uses_hub_daemon_reader_transport(monkeypatch, tmp_path):
    orch = {
        "hub_nodes": [{
            "node_id": "ag.deepthink",
            "type": "profile",
            "adapter_class": "AgyAdapter",
            "invoke": "agy",
            "requires_pty": True,
        }]
    }
    
    called_args = []
    class DummyPtyResult:
        text = "T21_TARGET_VALUE_REPLACED"
        elapsed = 5
        exit_code = 0
        timed_out = False
        timeout_kind = None
        transport_error = None
        pid = 42

    def fake_ask_with_pty(cmd, node_id, timeout_sec, process_env, quiet=False, ai_root=None, ask_id=None, cwd=None):
        called_args.append((cmd, node_id, timeout_sec, cwd))
        return DummyPtyResult()

    import hub
    monkeypatch.setattr(hub, "_ask_with_pty", fake_ask_with_pty)
    
    import sys
    from types import ModuleType
    mock_winpty = ModuleType("winpty")
    monkeypatch.setitem(sys.modules, "winpty", mock_winpty)

    res = cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="full byte-exact fixture instructions",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    assert len(called_args) == 1
    # T49-revert: inline delivery — the full prompt is the -p arg (the prompt-via-
    # file pointer doubled agy wall time and did not fix CRLF).
    assert called_args[0][0] == [
        "agy",
        "--dangerously-skip-permissions",
        "-p",
        "full byte-exact fixture instructions",
    ]
    assert called_args[0][1] == "ag.deepthink"
    assert called_args[0][2] == 10
    assert called_args[0][3] == str(tmp_path)


def test_pty_invoker_sanitizes_agy_output_before_retention(monkeypatch, tmp_path):
    orch = {
        "hub_nodes": [{
            "node_id": "ag.deepthink",
            "type": "profile",
            "adapter_class": "AgyAdapter",
            "invoke": "agy",
            "requires_pty": True,
        }]
    }
    
    class DummyPtyResult:
        text = "\x1b[31mHello\rWorld\b!" * 300
        elapsed = 5
        exit_code = 0
        timed_out = False
        timeout_kind = None
        transport_error = None
        pid = 42

    import hub
    monkeypatch.setattr(hub, "_ask_with_pty", lambda *a, **kw: DummyPtyResult())
    
    import sys
    from types import ModuleType
    monkeypatch.setitem(sys.modules, "winpty", ModuleType("winpty"))

    res = cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="hello",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    assert len(res.stdout) <= 2000
    assert "\x1b[31m" not in res.stdout


def test_pty_timeout_or_transport_error_cannot_pass(monkeypatch, tmp_path):
    orch = {
        "hub_nodes": [{
            "node_id": "ag.deepthink",
            "type": "profile",
            "adapter_class": "AgyAdapter",
            "invoke": "agy",
            "requires_pty": True,
        }]
    }

    class TimeoutResult:
        text = "some output"
        elapsed = 10
        exit_code = None
        timed_out = True
        timeout_kind = "execution_deadline"
        transport_error = None
        pid = 42

    import hub
    monkeypatch.setattr(hub, "_ask_with_pty", lambda *a, **kw: TimeoutResult())
    import sys
    from types import ModuleType
    monkeypatch.setitem(sys.modules, "winpty", ModuleType("winpty"))

    res1 = cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="hello",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    assert res1.returncode != 0
    assert res1.timeout_kind == "execution_deadline"
    assert res1.transport_error is None

    class TransportErrorResult:
        text = ""
        elapsed = 0
        exit_code = None
        timed_out = False
        timeout_kind = None
        transport_error = "pty_spawn_failed: access denied"
        pid = -1

    monkeypatch.setattr(hub, "_ask_with_pty", lambda *a, **kw: TransportErrorResult())
    res2 = cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="hello",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    assert res2.returncode != 0
    assert res2.transport_error == "pty_spawn_failed: access denied"


def test_pty_artifacts_are_scored_by_same_t21_judge(monkeypatch, tmp_path):
    called_workspace = []
    orig_score_workspace = cpc.score_workspace
    def fake_score_workspace(workspace, fixture):
        called_workspace.append(workspace)
        return orig_score_workspace(workspace, fixture)
    monkeypatch.setattr(cpc, "score_workspace", fake_score_workspace)

    def fake_invoker(peer, profile, prompt, workspace, orch, timeout):
        _apply_success(workspace, cpc.prepare_fixture(workspace))
        return cpc.PtyCompletedProcess(
            returncode=0,
            stdout="success",
            stderr="",
            transport="pty",
        )

    monkeypatch.setattr(cpc, "resolve_runtime_fingerprint", lambda orch, peer, profile: VALID_FP)

    artifact_dir = tmp_path / "artifacts"
    entry = cpc.run_one_pass(
        peer="ag",
        profile="deepthink",
        orch={},
        artifact_dir=artifact_dir,
        runtime_fingerprint=VALID_FP,
        prior_entries=[],
        invoker=fake_invoker,
    )
    assert len(called_workspace) == 1
    assert called_workspace[0] == artifact_dir / "workspace"
    assert entry["passed"] is False
    assert entry["base_passed"] is True


def test_three_passes_certify_transport_with_transient_retry(monkeypatch, tmp_path):
    attempts = 0
    def fake_invoker(peer, profile, prompt, workspace, orch, timeout):
        nonlocal attempts
        attempts += 1
        _apply_success(workspace, cpc.prepare_fixture(workspace))
        if attempts in (1, 3):
            return cpc.PtyCompletedProcess(
                returncode=1,
                stdout="timed out",
                stderr="timeout",
                transport="pty",
                elapsed_sec=30,
                exit_code=None,
                timeout_kind="execution_deadline",
                transport_error="transient timeout",
            )
        else:
            return cpc.PtyCompletedProcess(
                returncode=0,
                stdout="success",
                stderr="",
                transport="pty",
                elapsed_sec=5,
                exit_code=0,
                timeout_kind=None,
                transport_error=None,
            )

    monkeypatch.setattr(cpc, "resolve_runtime_fingerprint", lambda orch, peer, profile: VALID_FP)
    scores_path = tmp_path / "peer-capability-scores.jsonl"
    artifact_root = tmp_path / "artifacts"

    entries = cpc.run_canary(
        peer="ag",
        profile="deepthink",
        orch={},
        passes=3,
        scores_path=scores_path,
        artifact_root=artifact_root,
        invoker=fake_invoker,
        now=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    assert attempts == 5
    assert len(entries) == 5
    assert entries[-1]["passed"] is True
    assert entries[-1]["score"] == 100


def test_ag_blocked_feasibility_survives_failed_or_missing_spike(monkeypatch, tmp_path):
    dec_path = SYS_DIR / "_sys" / "ai" / "capability-declarations.json"
    if dec_path.exists():
        decs = json.loads(dec_path.read_text(encoding="utf-8"))
        ag_deepthink = decs.get("subjects", {}).get("ag.deepthink", {})
        feasibility = ag_deepthink.get("measurement_feasibility", {}).get("performance", {})
        assert feasibility.get("status") == "blocked_pending_pty_harness"
        assert feasibility.get("reason_code") == "agy_pty_harness_uncertified"


def test_non_pty_profile_rejects_pty_transport(monkeypatch):
    orch = {
        "hub_nodes": [{
            "node_id": "cx.standard",
            "type": "profile",
            "adapter_class": "CodexAdapter",
            "invoke": "codex",
            "requires_pty": False,
        }]
    }
    monkeypatch.setattr(cpc, "_load_orchestration", lambda path: orch)
    
    res = cpc.main(["--peer", "cx.standard", "--transport", "pty", "--execute"])
    assert res != 0


def test_pty_cwd_is_cast_to_str(monkeypatch, tmp_path):
    orch = {
        "hub_nodes": [{
            "node_id": "ag.deepthink",
            "type": "profile",
            "adapter_class": "AgyAdapter",
            "invoke": "agy",
            "requires_pty": True,
        }]
    }
    
    called_cwd = []
    class DummyPtyResult:
        text = "success"
        elapsed = 1
        exit_code = 0
        timed_out = False
        timeout_kind = None
        transport_error = None
        pid = 42

    def fake_ask_with_pty(*args, **kwargs):
        called_cwd.append(kwargs.get("cwd"))
        return DummyPtyResult()

    import hub
    monkeypatch.setattr(hub, "_ask_with_pty", fake_ask_with_pty)
    import sys
    from types import ModuleType
    monkeypatch.setitem(sys.modules, "winpty", ModuleType("winpty"))

    cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="hello",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    
    assert len(called_cwd) == 1
    assert isinstance(called_cwd[0], str)
    assert called_cwd[0] == str(tmp_path)


def test_pty_import_failure_is_caught_as_transport_error(monkeypatch, tmp_path):
    orch = {
        "hub_nodes": [{
            "node_id": "ag.deepthink",
            "type": "profile",
            "adapter_class": "AgyAdapter",
            "invoke": "agy",
            "requires_pty": True,
        }]
    }

    import sys
    monkeypatch.setitem(sys.modules, "winpty", None)
    
    res = cpc.invoke_peer_native_write_pty(
        peer="ag",
        profile="deepthink",
        prompt="hello",
        workspace=tmp_path,
        orch=orch,
        timeout=10,
    )
    
    assert res.returncode != 0
    assert res.transport_error is not None
    assert "winpty" in res.transport_error


def test_pty_prompt_file_is_excluded_from_scope_scoring(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = cpc.prepare_fixture(workspace)
    _apply_success(workspace, fixture)
    (workspace / cpc.PTY_PROMPT_FILE).write_text("harness payload", encoding="utf-8")

    scored = cpc.score_workspace(workspace, fixture)

    scope = scored["subchecks"]["target_scope"]
    assert scope["passed"] is True
    assert cpc.PTY_PROMPT_FILE not in scope["details"]["extra_files"]


def _run_characterization(monkeypatch, tmp_path, pattern, *, requested=None):
    attempts = []
    outcomes = iter(pattern)

    def fake_invoker(peer, profile, prompt, workspace, orch, timeout):
        outcome = next(outcomes)
        attempts.append(outcome)
        fixture = cpc.prepare_fixture(workspace)
        _apply_success(workspace, fixture)
        if outcome == "hard_fail":
            (workspace / cpc.LF_FILE).write_bytes(
                cpc.LF_TEXT.replace("\n", "\r\n").encode("utf-8")
            )
        if outcome == "transport":
            return cpc.PtyCompletedProcess(
                returncode=1,
                stdout="",
                stderr="timeout",
                timeout_kind="execution_deadline",
                transport_error="transient timeout",
            )
        if outcome == "incomplete":
            return cpc.PtyCompletedProcess(
                returncode=1,
                stdout="",
                stderr="process failed",
                exit_code=1,
            )
        return cpc.PtyCompletedProcess(returncode=0, stdout="ok", stderr="", exit_code=0)

    monkeypatch.setattr(cpc, "resolve_runtime_fingerprint", lambda orch, peer, profile: VALID_FP)
    scores_path = tmp_path / "scores.jsonl"
    entries = cpc.run_canary(
        peer="ag",
        profile="deepthink",
        orch={},
        characterize=requested or len(pattern),
        scores_path=scores_path,
        artifact_root=tmp_path / "artifacts",
        invoker=fake_invoker,
        now=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    return attempts, entries, [json.loads(line) for line in scores_path.read_text(encoding="utf-8").splitlines()]


def test_characterize_runs_all_complete_passes_and_marks_variation_flaky(monkeypatch, tmp_path):
    attempts, entries, records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["pass", "hard_fail", "pass"],
    )

    aggregate = entries[-1]
    assert attempts == ["pass", "hard_fail", "pass"]
    assert aggregate["runs"] == [95, 80, 95]
    assert aggregate["evidence_state"] == "flaky"
    assert aggregate["pass_rate"] == 2 / 3
    assert aggregate["hard_failure_fingerprints"] == ["line_endings_and_bom"]
    assert records[-1] == aggregate
    assert len(records) == 4  # three additive per-pass records plus one aggregate
    assert {
        "capability_id", "peer", "profile", "runtime_fingerprint", "runs",
        "median", "minimum", "maximum", "range", "pass_rate",
        "hard_failure_fingerprints", "evidence_state", "source_tag", "measured_at",
    } <= aggregate.keys()


def test_characterize_all_pass_is_stable_certified(monkeypatch, tmp_path):
    _attempts, entries, _records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["pass", "pass", "pass"],
    )

    aggregate = entries[-1]
    assert aggregate["evidence_state"] == "stable_certified"
    assert aggregate["pass_rate"] == 1.0
    assert aggregate["hard_failure_fingerprints"] == []


def test_characterize_repeated_same_hard_failure_is_stable_failed(monkeypatch, tmp_path):
    _attempts, entries, _records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["hard_fail", "hard_fail", "hard_fail"],
    )

    aggregate = entries[-1]
    assert aggregate["evidence_state"] == "stable_failed"
    assert aggregate["runs"] == [80, 80, 80]
    assert aggregate["hard_failure_fingerprints"] == ["line_endings_and_bom"]


def test_characterize_retries_transport_but_counts_genuine_failure(monkeypatch, tmp_path):
    attempts, entries, _records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["transport", "hard_fail", "pass"],
        requested=2,
    )

    aggregate = entries[-1]
    assert attempts == ["transport", "hard_fail", "pass"]
    assert aggregate["runs"] == [80, 95]
    assert aggregate["evidence_state"] == "flaky"


def test_characterize_transport_attempt_budget_is_honest(monkeypatch, tmp_path):
    attempts, entries, _records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["transport", "transport", "transport", "transport"],
        requested=2,
    )

    aggregate = entries[-1]
    assert len(attempts) == 4
    assert aggregate["runs"] == []
    assert aggregate["evidence_state"] == "transport_unstable"


def test_characterize_nontransport_incomplete_is_insufficient(monkeypatch, tmp_path):
    attempts, entries, _records = _run_characterization(
        monkeypatch,
        tmp_path,
        ["incomplete", "pass", "pass"],
        requested=2,
    )

    assert attempts == ["incomplete"]
    assert entries[-1]["evidence_state"] == "insufficient"


def test_characterize_cli_threads_requested_count_without_spawning(monkeypatch, tmp_path, capsys):
    orch = {
        "hub_nodes": [{
            "node_id": "cx.standard",
            "type": "profile",
            "adapter_class": "CodexAdapter",
            "invoke": "codex",
        }]
    }
    captured = {}

    def fake_run_canary(**kwargs):
        captured.update(kwargs)
        return [{"evidence_state": "stable_certified"}]

    monkeypatch.setattr(cpc, "_load_orchestration", lambda path=None: orch)
    monkeypatch.setattr(cpc, "run_canary", fake_run_canary)

    rc = cpc.main([
        "--peer", "cx.standard",
        "--characterize", "4",
        "--scores-path", str(tmp_path / "scores.jsonl"),
        "--artifact-root", str(tmp_path / "artifacts"),
        "--execute",
    ])

    assert rc == 0
    assert captured["characterize"] == 4
    assert "stable_certified" in capsys.readouterr().out


def test_pty_timeout_is_marked_transport_unstable_not_a_capability_score(monkeypatch, tmp_path):
    """T49 root cause: a PTY DEADLINE timeout produced partial artifacts that were
    mis-scored as a capability 10 (because PtyCompletedProcess dropped timed_out).
    A timed-out run must be flagged measurement_status=transport_unstable and be
    treated as transport-unstable (excluded from capability aggregation)."""
    monkeypatch.setattr(cpc, "resolve_runtime_fingerprint", lambda orch, peer, profile: VALID_FP)

    def timeout_invoker(peer, profile, prompt, workspace, orch, timeout):
        # a deadline timeout: partial/empty workspace, timed_out True, deadline kind
        return cpc.PtyCompletedProcess(
            returncode=1, stdout="", stderr="", transport="pty",
            elapsed_sec=600, exit_code=None, timed_out=True, timeout_kind="deadline",
        )

    entry = cpc.run_one_pass(
        peer="ag", profile="deepthink", orch={}, artifact_dir=tmp_path / "art",
        runtime_fingerprint=VALID_FP, prior_entries=[], invoker=timeout_invoker,
    )
    assert entry.get("measurement_status") == "transport_unstable"
    assert cpc._is_transport_unstable(entry["invocation"]) is True
    assert cpc._is_transient_pty_entry(entry) is True


def test_is_transport_unstable_catches_timeout_kind_even_if_timed_out_missing(monkeypatch):
    """Defense in depth: a dropped timed_out flag must NOT hide a timeout —
    timeout_kind alone still marks the run transport-unstable (the exact shape of
    the mis-scored T49 char-2 record: timeout_kind=deadline, timed_out absent)."""
    assert cpc._is_transport_unstable(
        {"transport": "pty", "timeout_kind": "deadline"}
    ) is True
    assert cpc._is_transport_unstable(
        {"transport": "pty", "transport_error": "x"}
    ) is True
    # a clean run is NOT transport-unstable
    assert cpc._is_transport_unstable(
        {"transport": "pty", "exit_code": 0}
    ) is False
