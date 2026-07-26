"""Cluster C11: evidence classification, unified store, and dispatch wiring."""
from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parent.parent.parent
for path in (SYS_DIR, SYS_DIR / "checks", SYS_DIR / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import check_cli_reality as ccr  # noqa: E402
import core.hub as hub  # noqa: E402
import core.hub_context as hub_context  # noqa: E402


ATTEMPTS = [
    ccr.PROBE_COMPLETE,
    ccr.PROBE_PARTIAL,
    ccr.PROBE_FAILED,
    ccr.PROBE_SKIPPED,
]
COMPLETENESS = [
    ccr.EVIDENCE_COMPLETE_CATALOG,
    ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
]


@pytest.mark.parametrize(
    ("attempt", "completeness"),
    [(attempt, completeness) for attempt in ATTEMPTS for completeness in COMPLETENESS],
)
def test_missing_model_4x2_matrix_blocks_only_complete_catalog_success(
    attempt,
    completeness,
):
    status, hard_block = ccr.classify_reality_evidence(
        model_present=False,
        probe_attempt_status=attempt,
        evidence_completeness=completeness,
        fresh=True,
        provenance_verified=True,
    )
    expected_block = (
        attempt == ccr.PROBE_COMPLETE
        and completeness == ccr.EVIDENCE_COMPLETE_CATALOG
    )
    assert hard_block is expected_block
    assert status == (
        ccr.REALITY_CONTRADICTED
        if expected_block
        else ccr.REALITY_UNVERIFIED_INCOMPLETE
    )


@pytest.mark.parametrize(
    ("attempt", "completeness"),
    [(attempt, completeness) for attempt in ATTEMPTS for completeness in COMPLETENESS],
)
def test_present_model_4x2_matrix_always_allows(attempt, completeness):
    status, hard_block = ccr.classify_reality_evidence(
        model_present=True,
        probe_attempt_status=attempt,
        evidence_completeness=completeness,
        fresh=True,
        provenance_verified=True,
    )
    assert status == ccr.REALITY_PRESENT
    assert hard_block is False


def _update(
    peer: str,
    *,
    models: list[str],
    attempt: str,
    completeness: str,
    captured_at: datetime,
    sha256: str = "a" * 64,
) -> dict:
    return {
        "identity_namespace": f"peer:{peer}",
        "models": list(models),
        "confirmed_models": list(models),
        "catalog_models": (
            list(models)
            if completeness == ccr.EVIDENCE_COMPLETE_CATALOG
            else []
        ),
        "probe_attempt_status": attempt,
        "evidence_completeness": completeness,
        "captured_at": captured_at.isoformat(),
        "last_attempt_at": captured_at.isoformat(),
        "binary": {
            "launcher_path": f"{peer}.cmd",
            "fingerprint_target_path": f"{peer}.exe",
            "fingerprint_kind": "direct_binary",
            "provenance_verified": True,
            "fingerprint": {
                "path": f"{peer}.exe",
                "sha256": sha256,
                "size": 1,
                "mtime_ns": 1,
            },
        },
        "provenance": [],
    }


def test_missing_cx_cache_entry_is_unmeasured_and_never_blocked(tmp_path):
    now = datetime.now(timezone.utc)
    ccr.merge_observation_updates(
        {
            "cc": _update(
                "cc",
                models=["claude-opus-4-8"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=now,
            )
        },
        ai_root=tmp_path,
        now=now,
    )
    dispatch_target = {
        "profile_id": "cx.deepthink",
        "reality_model_key": "gpt-5.6-sol",
    }
    status = ccr.get_cached_reality_status(
        dispatch_target,
        ai_root=tmp_path,
        now=now,
    )
    assert status.status == ccr.REALITY_UNMEASURED
    assert status.hard_block is False
    assert status.allow_dispatch is True


def test_stale_complete_catalog_warns_and_allows(tmp_path):
    now = datetime.now(timezone.utc)
    ccr.merge_observation_updates(
        {
            "cx": _update(
                "cx",
                models=["some-other-model"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=now - timedelta(hours=25),
            )
        },
        ai_root=tmp_path,
        now=now,
    )
    status = ccr.get_cached_reality_status(
        {
            "profile_id": "cx.deepthink",
            "reality_model_key": "gpt-5.6-sol",
        },
        ai_root=tmp_path,
        now=now,
    )
    assert status.status == ccr.REALITY_STALE_LAST_KNOWN_PRESENT
    assert status.hard_block is False
    assert status.warning is True


def test_partial_refresh_merges_positive_models_instead_of_replacing(tmp_path):
    first = datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    ccr.merge_observation_updates(
        {
            "cc": _update(
                "cc",
                models=["Model-A"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
                captured_at=first,
            )
        },
        ai_root=tmp_path,
        now=first,
    )
    ccr.merge_observation_updates(
        {
            "cc": _update(
                "cc",
                models=["Model-B"],
                attempt=ccr.PROBE_PARTIAL,
                completeness=ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
                captured_at=second,
            )
        },
        ai_root=tmp_path,
        now=second,
    )
    entry = ccr.read_observation_store(ai_root=tmp_path)["peers"]["cc"]
    assert entry["models"] == ["Model-A", "Model-B"]
    assert entry["confirmed_models"] == ["Model-A", "Model-B"]
    assert entry["probe_attempt_status"] == ccr.PROBE_PARTIAL
    assert (
        entry["evidence_completeness"]
        == ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY
    )


def test_failed_refresh_does_not_make_old_positive_evidence_fresh(tmp_path):
    old = datetime(2026, 7, 24, 0, 0, tzinfo=timezone.utc)
    now = old + timedelta(hours=25)
    ccr.merge_observation_updates(
        {
            "cx": _update(
                "cx",
                models=["gpt-5.6-sol"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
                captured_at=old,
            )
        },
        ai_root=tmp_path,
        now=old,
    )
    failed = _update(
        "cx",
        models=[],
        attempt=ccr.PROBE_FAILED,
        completeness=ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
        captured_at=now,
    )
    ccr.merge_observation_updates({"cx": failed}, ai_root=tmp_path, now=now)

    entry = ccr.read_observation_store(ai_root=tmp_path)["peers"]["cx"]
    assert entry["captured_at"] == old.isoformat()
    assert entry["last_attempt_at"] == now.isoformat()
    status = ccr.get_cached_reality_status(
        {
            "profile_id": "cx.deepthink",
            "reality_model_key": "gpt-5.6-sol",
        },
        ai_root=tmp_path,
        now=now,
    )
    assert status.status == ccr.REALITY_STALE_LAST_KNOWN_PRESENT
    assert status.hard_block is False


def test_new_complete_catalog_is_authoritative_over_old_confirmation(tmp_path):
    first = datetime(2026, 7, 25, 0, 0, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    ccr.merge_observation_updates(
        {
            "ag": _update(
                "ag",
                models=["old-model"],
                attempt=ccr.PROBE_PARTIAL,
                completeness=ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY,
                captured_at=first,
            )
        },
        ai_root=tmp_path,
        now=first,
    )
    ccr.merge_observation_updates(
        {
            "ag": _update(
                "ag",
                models=["current-model"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=second,
            )
        },
        ai_root=tmp_path,
        now=second,
    )
    status = ccr.get_cached_reality_status(
        {
            "profile_id": "ag.deepthink",
            "reality_model_key": "old-model",
        },
        ai_root=tmp_path,
        now=second,
    )
    assert status.status == ccr.REALITY_CONTRADICTED
    assert status.hard_block is True


def test_complete_catalog_without_real_sha_provenance_never_blocks(tmp_path):
    now = datetime.now(timezone.utc)
    update = _update(
        "cx",
        models=["different-model"],
        attempt=ccr.PROBE_COMPLETE,
        completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
        captured_at=now,
        sha256="declared-but-not-a-real-sha",
    )
    ccr.merge_observation_updates({"cx": update}, ai_root=tmp_path, now=now)
    status = ccr.get_cached_reality_status(
        {
            "profile_id": "cx.deepthink",
            "reality_model_key": "gpt-5.6-sol",
        },
        ai_root=tmp_path,
        now=now,
    )
    assert status.status == ccr.REALITY_UNVERIFIED_INCOMPLETE
    assert status.hard_block is False


def test_hot_reader_is_cache_only_and_sub_millisecond_warm(
    monkeypatch,
    tmp_path,
):
    now = datetime.now(timezone.utc)
    ccr.merge_observation_updates(
        {
            "cx": _update(
                "cx",
                models=["gpt-5.6-sol"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=now,
            )
        },
        ai_root=tmp_path,
        now=now,
    )
    target = {
        "profile_id": "cx.deepthink",
        "reality_model_key": "gpt-5.6-sol",
    }
    monkeypatch.setattr(
        ccr,
        "fingerprint",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("hot path must not SHA-256")
        ),
    )
    monkeypatch.setattr(
        ccr.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("hot path must not spawn")
        ),
    )

    for _ in range(20):
        assert ccr.get_cached_reality_status(
            target,
            ai_root=tmp_path,
            now=now,
        ).status == ccr.REALITY_PRESENT

    durations = []
    for _ in range(500):
        started = time.perf_counter_ns()
        ccr.get_cached_reality_status(target, ai_root=tmp_path, now=now)
        durations.append((time.perf_counter_ns() - started) / 1_000_000_000)
    assert statistics.median(durations) < 0.001
    assert sorted(durations)[int(len(durations) * 0.95)] < 0.005


def test_cc_and_cx_fingerprint_real_payload_not_npm_cmd_shim():
    for peer in ("cc", "cx"):
        boundary = ccr.real_binary(peer)
        assert boundary.status == ccr.BOUNDARY_BINARY_PRESENT
        assert boundary.launcher_path is not None
        assert boundary.fingerprint_path is not None
        assert boundary.launcher_path.suffix.casefold() == ".cmd"
        assert boundary.fingerprint_path.suffix.casefold() == ".exe"
        assert boundary.fingerprint_path != boundary.launcher_path
        assert boundary.fingerprint_path.stat().st_size > boundary.launcher_path.stat().st_size
        assert boundary.provenance_verified is True


def test_probe_version_reads_success_token_from_real_stderr_process(tmp_path):
    script = tmp_path / "stderr-version.cmd"
    script.write_text(
        "@ECHO OFF\r\n"
        "1>&2 ECHO peer-cli 9.8.7\r\n"
        "EXIT /B 0\r\n",
        encoding="utf-8",
    )
    orch = {
        "hub_nodes": [
            {
                "node_id": "p",
                "type": "peer",
                "enabled": True,
                "invoke": str(script),
            }
        ]
    }
    result = ccr.probe_version("p", orch)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert "9.8.7" in result.stderr
    assert result.version == "9.8.7"
    assert result.attempt_status == ccr.PROBE_COMPLETE


def test_probe_version_rejects_nonzero_even_with_version_token(tmp_path):
    script = tmp_path / "failed-version.cmd"
    script.write_text(
        "@ECHO OFF\r\n"
        "1>&2 ECHO fatal protocol 9.8.7 unsupported\r\n"
        "EXIT /B 1\r\n",
        encoding="utf-8",
    )
    orch = {
        "hub_nodes": [
            {
                "node_id": "p",
                "type": "peer",
                "enabled": True,
                "invoke": str(script),
            }
        ]
    }
    result = ccr.probe_version("p", orch)
    assert result.returncode == 1
    assert result.version is None
    assert result.attempt_status == ccr.PROBE_FAILED


def test_legacy_store_is_read_as_positive_only_not_false_negative(tmp_path):
    captured = datetime.now(timezone.utc).isoformat()
    (tmp_path / ccr.OBSERVATION_STORE_FILENAME).write_text(
        json.dumps(
            {
                "cc": {
                    "models": ["claude-opus-4-8"],
                    "captured_at": captured,
                    "provenance": [],
                }
            }
        ),
        encoding="utf-8",
    )
    store = ccr.read_observation_store(ai_root=tmp_path)
    assert store["schema_version"] == 2
    assert (
        store["peers"]["cc"]["evidence_completeness"]
        == ccr.EVIDENCE_POSITIVE_CONFIRMATIONS_ONLY
    )
    status = ccr.get_cached_reality_status(
        {
            "profile_id": "cc.fable",
            "reality_model_key": "claude-fable-5",
        },
        ai_root=tmp_path,
        now=datetime.now(timezone.utc),
    )
    assert status.hard_block is False


def test_composed_dispatch_target_keeps_capacity_and_reality_side_by_side():
    target = hub_context.ContextGate().resolve_dispatch_target("ag.effort")
    assert target.profile_id == "ag.effort"
    assert target.context_target.profile_id == "ag.effort"
    assert target.context_target.admission_limit > 0
    assert target.reality_model_key == "gemini-3-5-flash-high"


def test_action_pre_dispatch_gate_stops_fresh_verified_contradiction(
    monkeypatch,
    tmp_path,
    capsys,
):
    ai_root = tmp_path / ".ai"
    now = datetime.now(timezone.utc)
    ccr.merge_observation_updates(
        {
            "cx": _update(
                "cx",
                models=["some-other-model"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=now,
            )
        },
        ai_root=ai_root,
        now=now,
    )
    surfaced = []
    monkeypatch.setattr(hub, "_select_ask_profile", lambda to, query: (to, None))
    monkeypatch.setattr(hub, "_guard_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        hub,
        "_load_nodes",
        lambda root: {
            "cx.deepthink": {"invoke": "must-not-run", "requires_pty": False}
        },
    )
    monkeypatch.setattr(hub, "_load_orchestration", lambda: {})
    monkeypatch.setattr(hub, "is_routable", lambda *args, **kwargs: True)
    monkeypatch.setattr(hub, "_HUB_PEER_AVAILABLE", False)
    monkeypatch.setattr(hub, "_CONTEXT_GATE_AVAILABLE", True)
    monkeypatch.setattr(hub, "_ContextGate", lambda: object())
    monkeypatch.setattr(hub, "_resolve_profile_id", lambda to: "cx.deepthink")
    monkeypatch.setattr(
        hub,
        "_compose_dispatch_target",
        lambda profile_id, gate=None: {
            "profile_id": profile_id,
            "reality_model_key": "gpt-5.6-sol",
        },
    )
    monkeypatch.setattr(
        hub,
        "_surface_pre_dispatch_failure",
        lambda *args, **kwargs: surfaced.append((args, kwargs)),
    )

    with pytest.raises(SystemExit) as exc:
        hub._action_ask_inner(
            "cx.deepthink",
            "query",
            None,
            10,
            ai_root,
            _depth=1,
        )
    assert exc.value.code == 1
    assert surfaced
    assert surfaced[0][0][2] == "cli_reality_contradicted"
    assert "[HUB:BLOCK] CLI reality contradicted cx.deepthink" in capsys.readouterr().err


def test_c3_excludes_fresh_hard_negative_candidate(
    monkeypatch,
    tmp_path,
):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()
    (ai_root / "state.json").write_text(
        json.dumps({"version": 1, "human_interface_peer": "cx"}),
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc)
    ccr.merge_observation_updates(
        {
            "cc": _update(
                "cc",
                models=["some-other-claude"],
                attempt=ccr.PROBE_COMPLETE,
                completeness=ccr.EVIDENCE_COMPLETE_CATALOG,
                captured_at=now,
            )
        },
        ai_root=ai_root,
        now=now,
    )

    rows = [
        {
            "profile": "cc.deepthink",
            "peer": "cc",
            "state": "eligible",
            "headroom": 0.99,
        },
        {
            "profile": "ag.deepthink",
            "peer": "ag",
            "state": "eligible",
            "headroom": 0.80,
        },
    ]
    monkeypatch.setattr(hub.snapshot, "collect_snapshot", lambda use_cache=True: {})
    monkeypatch.setattr(hub.snapshot, "_derive_headroom_rows", lambda snap: rows)
    monkeypatch.setattr(hub, "_SNAPSHOT_AVAILABLE", True)

    plan = hub._plan_context_aware_failover(
        ai_root=ai_root,
        source_to="cx.effort",
        user_query_raw="x " * 35000,
    )
    assert plan is not None
    assert plan.target_profile == "ag.deepthink"
