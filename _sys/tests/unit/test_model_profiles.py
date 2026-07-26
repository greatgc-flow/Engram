"""Contract tests for orchestration v2 nested model profiles."""
import json
import sys
from pathlib import Path

SYS = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SYS / "core"))
import hub_peer

ORCHESTRATION = SYS / "ai" / "orchestration.json"
REGISTRY = SYS / "ai" / "model-registry.json"
REQUIRED = {"standard", "effort", "deepthink"}
EXPECTED_PROFILE_POLICY = {
    "cc": {
        "standard": ("tier", ["C"]),
        "effort": ("tier", ["C"]),
        "deepthink": ("tier", ["C"]),
        "fable": ("specialty", ["F", "C"]),
    },
    "ag": {
        "standard": ("tier", ["G"]),
        "effort": ("tier", ["G"]),
        "deepthink": ("tier", ["G"]),
        "opus": ("specialty", ["3P"]),
        "gptoss": ("specialty", ["3P"]),
    },
    "cx": {
        "standard": ("tier", ["X"]),
        "effort": ("tier", ["X"]),
        "deepthink": ("tier", ["X"]),
    },
}

INTELLIGENCE_EVIDENCE = {
    "cc.effort": {"kind": "point", "value": 53.0},
    "cc.deepthink": {"kind": "point", "value": 56.0},
    "cc.fable": {"kind": "point", "value": 60.0},
    "ag.effort": {"kind": "point", "value": 50.0},
    "ag.deepthink": {"kind": "range", "min": 46.0, "max": 47.0},
    "cx.standard": {"kind": "point", "value": 51.0},
    "cx.effort": {"kind": "point", "value": 55.0},
    "cx.deepthink": {"kind": "point", "value": 59.0},
}


def _raw():
    return json.loads(ORCHESTRATION.read_text(encoding="utf-8"))


def test_only_root_peers_are_tracked():
    nodes = _raw()["hub_nodes"]
    assert nodes
    assert all(node["type"] == "peer" for node in nodes)
    assert all("." not in node["node_id"] for node in nodes)


def test_every_root_has_mece_profiles():
    for node in _raw()["hub_nodes"]:
        assert REQUIRED.issubset(set(node.get("profiles", {})))
        assert node.get("default_profile") in REQUIRED


def test_profile_nodes_are_generated_systematically():
    normalized = hub_peer.normalize_orchestration(_raw())
    profile_nodes = [n for n in normalized["hub_nodes"] if n.get("type") == "profile"]
    
    # Calculate expected number of profile nodes based on actual profiles defined in each root
    expected_count = sum(len(node.get("profiles", {})) for node in _raw()["hub_nodes"])
    
    assert len(profile_nodes) == expected_count
    assert all(n["node_id"] == f"{n['parent_node']}.{n['profile_name']}" for n in profile_nodes)


def test_profile_policy_migration_matrix_and_normalization():
    roots = {node["node_id"]: node for node in _raw()["hub_nodes"]}
    assert set(roots) == set(EXPECTED_PROFILE_POLICY)

    normalized = hub_peer.normalize_orchestration(_raw())
    profile_nodes = {
        node["profile_id"]: node
        for node in normalized["hub_nodes"]
        if node.get("type") == "profile"
    }
    for peer_id, expected_profiles in EXPECTED_PROFILE_POLICY.items():
        assert set(roots[peer_id]["profiles"]) == set(expected_profiles)
        for profile_name, (profile_class, quota_families) in expected_profiles.items():
            raw_profile = roots[peer_id]["profiles"][profile_name]
            assert raw_profile["profile_class"] == profile_class
            assert raw_profile.get("quota_families", []) == quota_families

            normalized_profile = profile_nodes[f"{peer_id}.{profile_name}"]
            assert normalized_profile["profile_class"] == profile_class
            assert normalized_profile.get("quota_families", []) == quota_families


def test_d3_declared_intelligence_evidence_is_limited_and_normalized():
    roots = {node["node_id"]: node for node in _raw()["hub_nodes"]}
    normalized = hub_peer.normalize_orchestration(_raw())
    profile_nodes = {
        node["profile_id"]: node
        for node in normalized["hub_nodes"]
        if node.get("type") == "profile"
    }
    seen = {}
    for peer_id, root in roots.items():
        for profile_name, profile in root["profiles"].items():
            profile_id = f"{peer_id}.{profile_name}"
            evidence = profile.get("intelligence_evidence")
            if evidence is not None:
                seen[profile_id] = evidence
                assert evidence["scale"] == "external_composite"
                assert evidence["source_kind"] == "declared"
                assert evidence["verification"] == "unverified"
                assert evidence["estimate"]["approximate"] is True
                assert profile_nodes[profile_id]["intelligence_evidence"] == evidence
    assert seen == {
        profile_id: {
            **{
                "estimate": {**estimate, "approximate": True},
                "scale": "external_composite",
                "source_kind": "declared",
                "verification": "unverified",
                "source_ref": "_sys/docs-v2/ops/intelligence-scores.md#1-source-data-dir-004-declared-unverified",
                "as_of": "2026-07-13",
            }
        }
        for profile_id, estimate in INTELLIGENCE_EVIDENCE.items()
    }
    assert "intelligence_evidence" not in roots["cc"]["profiles"]["standard"]
    assert "intelligence_evidence" not in roots["ag"]["profiles"]["opus"]


def test_d6_ag_deepthink_intent_is_declared_and_normalized():
    roots = {node["node_id"]: node for node in _raw()["hub_nodes"]}
    intent = roots["ag"]["profiles"]["deepthink"]["profile_intent"]
    assert intent == {
        "selection_basis": "resilience_over_external_composite",
        "workloads": ["long_context", "tool_use", "multi_turn_instruction_following"],
        "tier_score_exception": {
            "relative_to": "ag.effort",
            "kind": "external_composite_inversion",
            "status": "accepted_policy_exception",
        },
        "evidence_status": "declared_unverified",
        "source_ref": "_sys/docs-v2/ops/profile-policy.md#2-capability-tiering",
    }
    normalized = hub_peer.normalize_orchestration(_raw())
    deepthink = next(node for node in normalized["hub_nodes"] if node.get("profile_id") == "ag.deepthink")
    ag_root = next(node for node in normalized["hub_nodes"] if node.get("node_id") == "ag" and node.get("type") == "peer")
    assert deepthink["profile_intent"] == intent
    assert ag_root["profile_intent"] == intent
    # Canonical runtime_model form (not the display-name form) since
    # 2026-07-23 (see orchestration.json's _model_id_fix_note on this node).
    assert deepthink["runtime_model"] == "gemini-3.1-pro-high"
    assert deepthink["routing_state"] == "eligible"


def test_sibling_profiles_do_not_inherit_default_profile_options():
    raw = {
        "hub_nodes": [{
            "node_id": "p",
            "type": "peer",
            "invoke": "peer-cli",
            "default_profile": "effort",
            "profiles": {
                "standard": {"model_id": "small"},
                "effort": {"model_id": "medium", "profile_args": ["--effort", "high"]},
                "deepthink": {"model_id": "large"},
            },
        }]
    }
    nodes = {
        n["node_id"]: n
        for n in hub_peer.normalize_orchestration(raw)["hub_nodes"]
    }
    assert nodes["p"]["profile_args"] == ["--effort", "high"]
    assert "profile_args" not in nodes["p.standard"]
    assert "profile_args" not in nodes["p.deepthink"]


def test_cached_normalization_reuses_same_normalized_object():
    first = hub_peer.normalize_orchestration()
    second = hub_peer.normalize_orchestration()
    assert first is second


def test_removed_legacy_virtual_nodes_do_not_exist():
    text = ORCHESTRATION.read_text(encoding="utf-8")
    assert '"cc-deep"' not in text
    assert '"gc-plan"' not in text


def test_documented_model_ids_exist_in_registry():
    models = json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]
    missing = []
    for node in _raw()["hub_nodes"]:
        for name, profile in node["profiles"].items():
            model_id = profile.get("model_id")
            if model_id and model_id not in models:
                missing.append(f"{node['node_id']}.{name}={model_id}")
    assert not missing, f"Profiles reference unknown models: {missing}"


def test_disabled_roots_have_blocked_profiles():
    for node in _raw()["hub_nodes"]:
        if node.get("enabled") is False:
            assert all(p["routing_state"] == "blocked" for p in node["profiles"].values())


def test_ag_runtime_models_are_locally_verified_and_routable():
    ag = next(n for n in _raw()["hub_nodes"] if n["node_id"] == "ag")
    # Canonical runtime_model form (not the display-name form) since
    # 2026-07-23 (see orchestration.json's _model_id_fix_note on these nodes).
    expected = {
        "standard": "gemini-3.5-flash-low",
        "effort": "gemini-3.5-flash-high",
        "deepthink": "gemini-3.1-pro-high",
    }
    for profile_name, runtime_model in expected.items():
        profile = ag["profiles"][profile_name]
        assert profile["runtime_model"] == runtime_model
        assert profile["model_availability"] == "verified_local"
        assert profile["routing_state"] == "eligible"
        assert profile["profile_args"] == ["--model", runtime_model]


def test_cc_and_cx_profiles_are_locally_verified():
    roots = {n["node_id"]: n for n in _raw()["hub_nodes"]}
    expected = {
        "cc": {
            "standard": {"model_id": "claude-haiku-4-5-20251001", "context": 200000, "validated_at": "2026-06-20"},
            "effort": {"model_id": "claude-sonnet-5", "context": 1000000, "validated_at": "2026-07-19"},
            "deepthink": {"model_id": "claude-opus-4-8", "context": 1000000, "validated_at": "2026-06-20"},
        },
        # context re-verified 372000 -> 272000 on 2026-07-24 (real measurement,
        # see orchestration.json's cx profile entries); validated_at bumped
        # to match.
        "cx": {
            "standard": {"model_id": "gpt-5.6-luna", "context": 272000, "validated_at": "2026-07-24"},
            "effort": {"model_id": "gpt-5.6-terra", "context": 272000, "validated_at": "2026-07-24"},
            "deepthink": {"model_id": "gpt-5.6-sol", "context": 272000, "validated_at": "2026-07-24"},
        },
    }
    for peer_id, profiles in expected.items():
        for profile_name, expected_profile in profiles.items():
            profile = roots[peer_id]["profiles"][profile_name]
            assert profile["model_id"] == expected_profile["model_id"]
            assert profile["model_availability"] == "verified_local"
            assert profile["runtime_context_window"] == expected_profile["context"]
            assert profile["validated_at"] == expected_profile["validated_at"]
            assert profile["validation_method"]


def test_fable_is_documented_and_available():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]
    assert registry["claude-fable-5"]["status"] == "GA"
    cc = next(n for n in _raw()["hub_nodes"] if n["node_id"] == "cc")
    fable_profile = cc["profiles"].get("fable")
    assert fable_profile is not None
    assert fable_profile["model_id"] == "claude-fable-5"


# ── W2 (consensus 2026-07-03): r-8b3b model-operand grammar / LL-009 ──────────

def test_extract_model_operand_forms():
    assert hub_peer.extract_model_operand(["--model", "gpt-5.5"]) == "gpt-5.5"
    assert hub_peer.extract_model_operand(["--model=claude-opus-4-8"]) == "claude-opus-4-8"
    assert hub_peer.extract_model_operand(["-m", "x"]) == "x"
    assert hub_peer.extract_model_operand(["--effort", "high"]) is None
    assert hub_peer.extract_model_operand([]) is None
    assert hub_peer.extract_model_operand(["--model"]) == ""  # dangling flag


def test_validate_model_operand_match_passes():
    node = {"node_id": "cc.deepthink", "model_id": "claude-opus-4-8",
            "profile_args": ["--model", "claude-opus-4-8", "--effort", "high"]}
    assert hub_peer.validate_model_operand(node) is None


def test_validate_model_operand_drift_fails():
    node = {"node_id": "cc.deepthink", "model_id": "claude-opus-4-8",
            "profile_args": ["--model", "claude-opus-4-7"]}
    error = hub_peer.validate_model_operand(node)
    assert error and "drift" in error


def test_validate_model_operand_rejects_invoke_args_model():
    node = {"node_id": "cx", "invoke_args": ["exec", "{query}", "--model", "gpt-5.6-terra"],
            "profile_args": []}
    error = hub_peer.validate_model_operand(node)
    assert error and "invoke_args" in error


def test_validate_model_operand_descriptor_style_ag():
    node = {"node_id": "ag.deepthink", "model_id": None,
            "profile_args": ["--model", "Gemini 3.1 Pro (High)"]}
    assert hub_peer.validate_model_operand(node) is None
    empty = {"node_id": "ag.x", "profile_args": ["--model", "  "]}
    error = hub_peer.validate_model_operand(empty)
    assert error and "empty" in error


def test_model_operand_report_passes_on_live_orchestration():
    """The live config must satisfy the r-8b3b grammar (LL-009 artifact source)."""
    report = hub_peer.model_operand_report()
    assert report["status"] == "pass", report["findings"]
    assert report["checked_nodes"] > 0
    assert report["lesson"] == "LL-009"
