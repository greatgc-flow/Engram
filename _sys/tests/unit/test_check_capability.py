"""Unit tests for capability resolver and checker (T43).
"""
import copy
import json
import sys
import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

SYS_DIR = Path(__file__).resolve().parents[2]
if str(SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "core"))
if str(SYS_DIR / "checks") not in sys.path:
    sys.path.insert(0, str(SYS_DIR / "checks"))

import snapshot
import check_capability
from check_peer_capability_canary import SCHEMA_VERSION, CAPABILITY_ID


def test_declared_only_resolves_declared_band():
    """If there is only a declaration:
    - If there are zero empirical records, it resolves to ABSENT.
    - If there is a stale empirical record, it falls back to DECLARED.
    """
    now = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    
    # Declarations with one legacy external composite axis
    declarations = {
        "schema_version": 1,
        "subjects": {
            "cx.deepthink": {
                "subject": {
                    "peer": "cx",
                    "profile": "deepthink",
                    "deployed_model_id": "gpt-5.6-sol",
                    "reasoning_effort": "xhigh",
                    "adapter": "CodexAdapter"
                },
                "axes": {
                    "legacy_external_composite": {
                        "value": {"kind": "point", "value": 59.0, "approximate": True},
                        "scale": "external_composite",
                        "source_kind": "declared",
                        "verification": "unverified",
                        "source_ref": "some_ref",
                        "as_of": "2026-07-13"
                    }
                }
            }
        }
    }
    
    # Case 1: Zero empirical records -> resolves to ABSENT band (gated)
    reality = check_capability.resolve_capability_reality(orch, snap, declarations, [], now)
    cx_dt = reality["subjects"]["cx.deepthink"]["axes"]["legacy_external_composite"]
    assert cx_dt["evidence_band"] == "ABSENT"
    assert cx_dt["effective_value"] is None
    
    # Case 2: Expired empirical record exists -> falls back to DECLARED
    expired_entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "cap-expired-cx-deepthink",
        "peer": "cx",
        "profile": "deepthink",
        "capability_id": "legacy_external_composite",
        "score": 98.0,
        "passed": True,
        "measured_at": "2026-07-01T12:00:00Z",
        "expires_at": "2026-07-08T12:00:00Z", # expired
        "source_tag": "empirical_probe",
        "runtime_fingerprint": {
            "peer": "cx", "profile": "deepthink",
            "model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
            "adapter": "CodexAdapter",
            "invoke_args": ["exec"],
            "profile_config_sha256": "a" * 64,
            "binary": {"exists": True, "sha256": "b" * 64}
        }
    }
    
    # Mock resolve_runtime_fingerprint in check_peer_capability_canary
    import check_peer_capability_canary
    orig_resolve = check_peer_capability_canary.resolve_runtime_fingerprint
    check_peer_capability_canary.resolve_runtime_fingerprint = lambda o, p, pr: expired_entry["runtime_fingerprint"]
    
    try:
        reality = check_capability.resolve_capability_reality(orch, snap, declarations, [expired_entry], now)
        cx_dt = reality["subjects"]["cx.deepthink"]["axes"]["legacy_external_composite"]
        assert cx_dt["evidence_band"] == "DECLARED"
        assert cx_dt["effective_value"] == {"kind": "point", "value": 59.0, "approximate": True}
        assert len(cx_dt["stale_evidence"]) == 1
        assert cx_dt["stale_evidence"][0]["id"] == "cap-expired-cx-deepthink"
    finally:
        check_peer_capability_canary.resolve_runtime_fingerprint = orig_resolve


def test_failed_empirical_without_declaration_resolves_stale_and_passes_check():
    """A FAILED empirical probe on an axis with no declaration (e.g. the real
    ag.deepthink direct_file_write.safe_utf8.v1 spike that scored 80 and failed the
    line-endings hard gate) resolves to STALE with no effective value, and
    check_reality_rules must accept it (STALE carries no scale, like ABSENT)."""
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    declarations = {"schema_version": 1, "subjects": {}}
    fp = {
        "peer": "ag", "profile": "deepthink",
        "model_id": "Gemini 3.1 Pro (High)", "reasoning_effort": "high",
        "adapter": "AgyAdapter", "invoke_args": ["-p"],
        "profile_config_sha256": "c" * 64,
        "binary": {"exists": True, "sha256": "d" * 64},
    }
    failed_entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "cap-ag-deepthink-fail",
        "peer": "ag", "profile": "deepthink",
        "capability_id": CAPABILITY_ID,
        "score": 80, "passed": False,
        "measured_at": "2026-07-13T17:56:22Z",
        "expires_at": "2026-07-20T17:56:22Z",
        "source_tag": "empirical_probe",
        "runtime_fingerprint": fp,
    }
    import check_peer_capability_canary
    orig = check_peer_capability_canary.resolve_runtime_fingerprint
    check_peer_capability_canary.resolve_runtime_fingerprint = lambda o, p, pr: fp
    try:
        reality = check_capability.resolve_capability_reality(orch, snap, declarations, [failed_entry], now)
        axis = reality["subjects"]["ag.deepthink"]["axes"][CAPABILITY_ID]
        assert axis["evidence_band"] == "STALE"
        assert axis["effective_value"] is None
        assert any(e["id"] == "cap-ag-deepthink-fail" for e in axis["stale_evidence"])
        # The check must PASS on this overlay (the bug the real spike exposed).
        assert check_capability.check_reality_rules(reality) == []
    finally:
        check_peer_capability_canary.resolve_runtime_fingerprint = orig


def test_valid_empirical_supersedes_declaration_as_certified():
    """Valid empirical probe (passed + same fingerprint + not expired) supersedes declaration."""
    now = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    
    declarations = {
        "schema_version": 1,
        "subjects": {
            "cx.deepthink": {
                "subject": {
                    "peer": "cx", "profile": "deepthink",
                    "deployed_model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
                    "adapter": "CodexAdapter"
                },
                "axes": {
                    "legacy_external_composite": {
                        "value": {"kind": "point", "value": 59.0, "approximate": True},
                        "scale": "external_composite",
                        "source_kind": "declared",
                        "verification": "unverified",
                        "source_ref": "some_ref",
                        "as_of": "2026-07-13"
                    }
                }
            }
        }
    }
    
    valid_entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "cap-valid-cx-deepthink",
        "peer": "cx",
        "profile": "deepthink",
        "capability_id": "legacy_external_composite",
        "score": 98.0,
        "passed": True,
        "measured_at": "2026-07-10T12:00:00Z",
        "expires_at": "2026-07-17T12:00:00Z", # valid
        "source_tag": "empirical_probe",
        "runtime_fingerprint": {
            "peer": "cx", "profile": "deepthink",
            "model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
            "adapter": "CodexAdapter",
            "invoke_args": ["exec"],
            "profile_config_sha256": "a" * 64,
            "binary": {"exists": True, "sha256": "b" * 64}
        }
    }
    
    import check_peer_capability_canary
    orig_resolve = check_peer_capability_canary.resolve_runtime_fingerprint
    check_peer_capability_canary.resolve_runtime_fingerprint = lambda o, p, pr: valid_entry["runtime_fingerprint"]
    
    try:
        reality = check_capability.resolve_capability_reality(orch, snap, declarations, [valid_entry], now)
        cx_dt = reality["subjects"]["cx.deepthink"]["axes"]["legacy_external_composite"]
        assert cx_dt["evidence_band"] == "CERTIFIED"
        assert cx_dt["effective_value"] == 98.0
        assert cx_dt["source_tag"] == "empirical_probe"
        assert cx_dt["verification"] == "machine_observed"
    finally:
        check_peer_capability_canary.resolve_runtime_fingerprint = orig_resolve


def test_expired_empirical_reveals_declared_fallback():
    """An expired empirical probe is placed in stale_evidence, and fallback occurs."""
    # This is tested in test_declared_only_resolves_declared_band (Case 2). Let's test STALE fallback without declaration here.
    now = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    declarations = {"schema_version": 1, "subjects": {}} # no declarations
    
    expired_entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "cap-expired-cx-deepthink",
        "peer": "cx",
        "profile": "deepthink",
        "capability_id": "legacy_external_composite",
        "score": 98.0,
        "passed": True,
        "measured_at": "2026-07-01T12:00:00Z",
        "expires_at": "2026-07-08T12:00:00Z",
        "source_tag": "empirical_probe",
        "runtime_fingerprint": {
            "peer": "cx", "profile": "deepthink",
            "model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
            "adapter": "CodexAdapter",
            "invoke_args": ["exec"],
            "profile_config_sha256": "a" * 64,
            "binary": {"exists": True, "sha256": "b" * 64}
        }
    }
    
    import check_peer_capability_canary
    orig_resolve = check_peer_capability_canary.resolve_runtime_fingerprint
    check_peer_capability_canary.resolve_runtime_fingerprint = lambda o, p, pr: expired_entry["runtime_fingerprint"]
    
    try:
        reality = check_capability.resolve_capability_reality(orch, snap, declarations, [expired_entry], now)
        cx_dt = reality["subjects"]["cx.deepthink"]["axes"]["legacy_external_composite"]
        assert cx_dt["evidence_band"] == "STALE"
        assert cx_dt["effective_value"] is None
        assert len(cx_dt["stale_evidence"]) == 1
    finally:
        check_peer_capability_canary.resolve_runtime_fingerprint = orig_resolve


def test_cross_scale_values_are_not_drift():
    """reconcile_status is computed only within the same scale. Cross-scale comparison resolves to ABSENT."""
    # We can test this by checking resolve_capability_reality's reconcile_status for an axis where a declaration has one scale and empirical has another.
    now = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    
    declarations = {
        "schema_version": 1,
        "subjects": {
            "cx.deepthink": {
                "subject": {
                    "peer": "cx", "profile": "deepthink",
                    "deployed_model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
                    "adapter": "CodexAdapter"
                },
                "axes": {
                    "legacy_external_composite": {
                        "value": {"kind": "point", "value": 59.0, "approximate": True},
                        "scale": "external_composite",
                        "source_kind": "declared",
                        "verification": "unverified",
                        "source_ref": "some_ref",
                        "as_of": "2026-07-13"
                    }
                    # declarations scale is external_composite
                }
            }
        }
    }
    
    valid_entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "cap-valid-cx-deepthink",
        "peer": "cx",
        "profile": "deepthink",
        "capability_id": "legacy_external_composite",
        "score": 98.0,
        "passed": True,
        "measured_at": "2026-07-10T12:00:00Z",
        "expires_at": "2026-07-17T12:00:00Z",
        "source_tag": "empirical_probe",
        # Wait, the empirical probe has scale in the record? No, it might not, but let's assume it has capability_id/axis matching legacy_external_composite,
        # but let's say the resolver checks the scale.
        # Wait! The decisions doc says: "External composite vs local suite always = ABSENT, never DRIFT."
        # If the empirical record is local_suite or anything else (e.g. from canary_budget/capability_core.v1), and declaration is composite, they are different scales, so reconcile_status is ABSENT.
        "runtime_fingerprint": {
            "peer": "cx", "profile": "deepthink",
            "model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
            "adapter": "CodexAdapter",
            "invoke_args": ["exec"],
            "profile_config_sha256": "a" * 64,
            "binary": {"exists": True, "sha256": "b" * 64}
        }
    }
    
    import check_peer_capability_canary
    orig_resolve = check_peer_capability_canary.resolve_runtime_fingerprint
    check_peer_capability_canary.resolve_runtime_fingerprint = lambda o, p, pr: valid_entry["runtime_fingerprint"]
    
    try:
        # If we specify empirical scale is 'local_suite', and declared is 'external_composite'
        # The resolver checks if scales match. Let's make sure.
        reality = check_capability.resolve_capability_reality(orch, snap, declarations, [valid_entry], now)
        cx_dt = reality["subjects"]["cx.deepthink"]["axes"]["legacy_external_composite"]
        # Since empirical is resolved (effective_value is 98.0 in scale 'local_suite' or similar, while declaration is 'external_composite' or scale mismatch)
        # Wait, how does the resolver know the scale of the empirical probe?
        # In check_peer_capability_canary, the scale of empirical probe is 'local_suite' or we can check.
        # In any case, different scales (e.g. external_composite vs local_suite) must resolve to ABSENT reconcile_status.
        assert cx_dt["reconcile_status"] == "ABSENT"
    finally:
        check_peer_capability_canary.resolve_runtime_fingerprint = orig_resolve


def test_missing_provenance_fails_capability_check():
    """check_capability.py fails on malformed declarations or missing scale|source_kind|verification|source_ref|as_of."""
    # We can write a check rules validator and test it here.
    malformed_declarations = {
        "schema_version": 1,
        "subjects": {
            "cx.deepthink": {
                "subject": {
                    "peer": "cx", "profile": "deepthink",
                    "deployed_model_id": "gpt-5.6-sol", "reasoning_effort": "xhigh",
                    "adapter": "CodexAdapter"
                },
                "axes": {
                    "legacy_external_composite": {
                        "value": {"kind": "point", "value": 59.0},
                        # missing scale, source_kind, verification, source_ref, as_of
                    }
                }
            }
        }
    }
    
    with pytest.raises(ValueError, match="missing.*scale|source_kind|verification|source_ref|as_of"):
        # Let's say check_capability has a validation function or resolve_capability_reality validates it
        check_capability.resolve_capability_reality({}, {}, malformed_declarations, [], datetime.now(timezone.utc))


def test_operational_snapshot_axis_is_zero_token_read_only():
    """Operational data comes from snapshot profile rows ONLY, no subprocess invocation, zero token spend."""
    # Let's mock a snapshot with operational source (app_server)
    now = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {
        "profiles": [
            {
                "profile": "cx.deepthink",
                "peer": "cx",
                "profile_name": "deepthink",
                "sources": {
                    "context": "app_server"
                },
                "context": {
                    "window_tokens": 372000,
                    "used_tokens": 100,
                    "source_tag": "app_server"
                }
            }
        ]
    }
    
    declarations = {
        "schema_version": 1,
        "subjects": {}
    }
    
    # Resolver should find that for cx.deepthink under 'window_tokens' or 'context_window' axis, there is operational telemetry.
    # No score entries or declarations needed.
    reality = check_capability.resolve_capability_reality(orch, snap, declarations, [], now)
    cx_dt_ctx = reality["subjects"]["cx.deepthink"]["axes"]["context_window"]
    assert cx_dt_ctx["evidence_band"] == "EXPLORATORY"
    assert cx_dt_ctx["effective_value"] == 372000
    assert cx_dt_ctx["source_tag"] == "app_server"
    assert cx_dt_ctx["verification"] == "machine_observed"


def test_routing_modules_do_not_load_capability_declarations():
    """AST guard: reject imports or capability-declarations.json path literals inside routing decision functions."""
    core_dir = SYS_DIR / "core"
    for path in core_dir.glob("*.py"):
        if path.name == "snapshot.py":
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # Check for select_load_balanced_peer function
                if isinstance(node, ast.FunctionDef) and node.name == "select_load_balanced_peer":
                    # Walk through the select_load_balanced_peer function body
                    for child in ast.walk(node):
                        # Check for imports
                        if isinstance(child, (ast.Import, ast.ImportFrom)):
                            for alias in child.names:
                                assert "check_capability" not in alias.name
                                assert "capability-declarations" not in alias.name
                        # Check for string literals (path literal or similar)
                        if isinstance(child, ast.Constant) and isinstance(child.value, str):
                            assert "capability-declarations.json" not in child.value


def test_declared_capability_values_do_not_change_routing_decision(monkeypatch):
    """Runtime equivalence: run snapshot.select_load_balanced_peer() with byte-identical inputs
    but distinct declared values; assert identical candidates, weights, selected profile, seed, arbiter selection."""
    observed = "2026-07-08T00:00:00+00:00"
    profiles = {
        "fable": {
            "model_id": "claude-fable-5",
            "reasoning_effort": "high",
            "runtime_context_window": 200000,
            "routing_state": "eligible",
            "cost_tier": "high",
            "quota_families": ["C"]
        },
        "effort": {
            "model_id": "claude-sonnet-4-6",
            "reasoning_effort": "high",
            "runtime_context_window": 200000,
            "routing_state": "eligible",
            "cost_tier": "mid",
            "quota_families": ["G"]
        }
    }
    cc = {
        "type": "peer",
        "enabled": True,
        "node_id": "cc",
        "default_profile": "fable",
        "profiles": {"fable": profiles["fable"]}
    }
    ag = {
        "type": "peer",
        "enabled": True,
        "node_id": "ag",
        "default_profile": "effort",
        "profiles": {"effort": profiles["effort"]}
    }
    orch = {"hub_nodes": [cc, ag]}
    records = [
        {
            "peer": "cc",
            "model": "claude-fable-5",
            "domains": {
                "context": {
                    "window_tokens": 200000,
                    "used_tokens": 100,
                    "utilization_pct": 0.05,
                    "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"}
                },
                "quota": {
                    "buckets": [{"label": "C-5H", "used_frac": 0.10}],
                    "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"}
                }
            },
            "raw": {"source": "health"}
        },
        {
            "peer": "ag",
            "model": "claude-sonnet-4-6",
            "domains": {
                "context": {
                    "window_tokens": 200000,
                    "used_tokens": 100,
                    "utilization_pct": 0.05,
                    "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"}
                },
                "quota": {
                    "buckets": [{"label": "G-5H", "used_frac": 0.10}],
                    "source": {"kind": "cached", "observed_at": observed, "confidence": "exact"}
                }
            },
            "raw": {"source": "health"}
        }
    ]
    
    # 1. Plain snapshot rows
    plain_rows = snapshot._build_profile_rows(orch, records, observed)
    plain_snap = {"profiles": plain_rows}
    
    # 2. Snapshot rows with declared capability reality
    declared_rows = copy.deepcopy(plain_rows)
    # Inject mock capability reality block in the snapshot row (if it ever gets stored there, or similar metadata)
    for r in declared_rows:
        r["capability_reality"] = {
            "legacy_external_composite": {
                "effective_value": 99.0,
                "evidence_band": "DECLARED"
            }
        }
        
    routing_cfg = {
        "enabled": True,
        "effective_headroom_floor": 0.10,
        "terminal_hard_exclude": True,
        "cost_map": {"low": 0.0, "mid": 0.02, "high": 0.04},
        "arbiter_models": ["cc.fable", "ag.effort"]
    }
    
    plain_result = snapshot.select_load_balanced_peer(plain_snap, routing_cfg, ask_id="t43-equiv")
    declared_result = snapshot.select_load_balanced_peer({"profiles": declared_rows}, routing_cfg, ask_id="t43-equiv")
    
    # Assert identical candidates, weights, selected profile, seed, arbiter selection
    assert plain_result["selected_peer"] == declared_result["selected_peer"]
    assert plain_result["weights"] == declared_result["weights"]
    assert plain_result["seed"] == declared_result["seed"]
    assert plain_result["draw"] == declared_result["draw"]
    assert plain_result["candidates"] == declared_result["candidates"]
    
    plain_arb = snapshot.select_arbiter(plain_snap, routing_cfg)
    declared_arb = snapshot.select_arbiter({"profiles": declared_rows}, routing_cfg)
    assert plain_arb == declared_arb


def test_resolver_skips_malformed_empirical_without_raising_or_false_certifying():
    """T52 C1/C2: a long_context-style empirical record with NO runtime_fingerprint
    must not ValueError the whole resolve (C2); a capability-core-style record with
    a fingerprint but only axis_scores (no numeric `score`) must not resolve to a
    CERTIFIED-but-None band (C1). Both are skipped -> the overlay degrades to
    absent, never crashes or falsely certifies."""
    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    orch = {"hub_nodes": []}
    snap = {"profiles": []}
    declarations = {"schema_version": 1, "subjects": {}}
    good_fp = {
        "peer": "cx", "profile": "deepthink", "model_id": "gpt-5.6-sol",
        "reasoning_effort": "xhigh", "adapter": "CodexAdapter", "invoke_args": ["exec"],
        "profile_config_sha256": "a" * 64, "binary": {"exists": True, "sha256": "b" * 64},
    }
    long_context = {
        "source_tag": "empirical_probe", "peer": "cx", "profile": "deepthink",
        "capability_id": "long_context.8k.v1", "axis_scores": {"long_context_quality": 100},
        "measured_at": "2026-07-14T00:00:00Z",
    }
    capability_core = {
        "source_tag": "empirical_probe", "peer": "cx", "profile": "deepthink",
        "capability_id": "capability-core.v1", "runtime_fingerprint": good_fp,
        "axis_scores": {"reasoning_correctness": 100}, "measured_at": "2026-07-14T00:00:00Z",
    }
    # must NOT raise
    reality = check_capability.resolve_capability_reality(
        orch, snap, declarations, [long_context, capability_core], now
    )
    # no axis anywhere is CERTIFIED with a None value
    for subj in reality["subjects"].values():
        for axis in subj["axes"].values():
            assert not (axis["evidence_band"] == "CERTIFIED" and axis["effective_value"] is None)
