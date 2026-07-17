"""TDD contracts for deterministic automatic profile routing."""
import json
import sys
from pathlib import Path

SYS = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SYS / "core"))

import hub_profile_router


def _orch():
    return json.loads((SYS / "ai" / "orchestration.json").read_text(encoding="utf-8"))


def _routing():
    return json.loads((SYS / "ai" / "routing-config.json").read_text(encoding="utf-8"))


def select(target: str, query: str, failures: int = 0):
    return hub_profile_router.select_profile_node(
        target,
        query,
        orchestration=_orch(),
        routing_config=_routing(),
        consecutive_failures=failures,
        consecutive_failure_reason="quality_failure" if failures else None,
    )


def test_simple_read_request_uses_standard():
    decision = select("cx", "Show repository status.")
    assert decision.node_id == "cx.standard"
    assert decision.profile == "standard"


def test_implementation_request_uses_effort():
    decision = select("cx", "Implement the parser change and add focused tests.")
    assert decision.node_id == "cx.effort"
    assert decision.profile == "effort"


def test_architecture_and_security_request_uses_deepthink():
    decision = select(
        "cc",
        "Redesign the architecture and protocol, then perform an exhaustive security review.",
    )
    assert decision.node_id == "cc.deepthink"
    assert decision.profile == "deepthink"


def test_ambiguous_request_defaults_to_effort():
    decision = select("cx", "Please handle this carefully.")
    assert decision.node_id == "cx.effort"
    assert "ambiguous_default" in decision.signals


def test_explicit_profile_is_immutable():
    decision = select("cx.deepthink", "Show repository status.")
    assert decision.node_id == "cx.deepthink"
    assert decision.explicit is True
    assert decision.classifier_triggered is False


def test_explicit_profile_tag_overrides_scoring():
    decision = select("cx", "[PROFILE:deepthink] Show repository status.")
    assert decision.node_id == "cx.deepthink"
    assert "explicit_tag" in decision.signals



def test_blocked_selected_profile_falls_down_within_same_peer():
    orch = _orch()
    ag = next(node for node in orch["hub_nodes"] if node["node_id"] == "ag")
    ag["profiles"]["deepthink"]["routing_state"] = "blocked"
    decision = hub_profile_router.select_profile_node(
        "ag",
        "Redesign the architecture and perform an exhaustive security review.",
        orchestration=orch,
        routing_config=_routing(),
    )
    assert decision.requested_profile == "deepthink"
    assert decision.node_id == "ag.effort"
    assert decision.fallback_from == "deepthink"


def test_all_profiles_blocked_fails_without_changing_peer():
    orch = _orch()
    ag = next(node for node in orch["hub_nodes"] if node["node_id"] == "ag")
    for profile in ag["profiles"].values():
        profile["routing_state"] = "blocked"

    try:
        hub_profile_router.select_profile_node(
            "ag",
            "Implement this change.",
            orchestration=orch,
            routing_config=_routing(),
        )
    except hub_profile_router.ProfileRoutingError as exc:
        assert "ag" in str(exc)
    else:
        raise AssertionError("all-blocked peer must fail closed")


def test_router_decision_is_auditable():
    decision = select("cx", "Implement the parser change and add tests.")
    payload = decision.as_dict()
    assert payload["selected_profile"] == "effort"
    assert isinstance(payload["score"], int)
    assert payload["signals"]
    assert 0.0 <= payload["confidence"] <= 1.0


def test_golden_query_set_accuracy_is_at_least_ninety_percent():
    cases = [
        ("Show repository status.", "standard"),
        ("List active peers.", "standard"),
        ("Read the configuration file.", "standard"),
        ("Summarize the latest report.", "standard"),
        ("Explain this setting.", "standard"),
        ("What is the current version?", "standard"),
        ("Run a health check.", "standard"),
        ("Show the selected profile.", "standard"),
        ("List files in the workspace.", "standard"),
        ("Read and summarize the handoff.", "standard"),
        ("Implement the parser change.", "effort"),
        ("Fix the failing unit test.", "effort"),
        ("Refactor the routing helper.", "effort"),
        ("Debug the timeout failure.", "effort"),
        ("Write focused tests.", "effort"),
        ("Migrate the configuration schema.", "effort"),
        ("Benchmark the routing function.", "effort"),
        ("Design the validation API.", "effort"),
        ("Update the implementation.", "effort"),
        ("Review the changed module.", "effort"),
        ("Review the architecture and security boundaries.", "deepthink"),
        ("Redesign the protocol and invariants.", "deepthink"),
        ("Perform an exhaustive cross-review.", "deepthink"),
        ("Build a threat model and security review.", "deepthink"),
        ("Find the root cause in the protocol architecture.", "deepthink"),
        ("Reach consensus on architecture tradeoffs.", "deepthink"),
        ("[RISK:10] Verify this change.", "deepthink"),
        ("Audit security invariants exhaustively.", "deepthink"),
        ("Cross-review the protocol threat model.", "deepthink"),
        ("Analyze architecture, consensus, and invariants.", "deepthink"),
    ]
    correct = sum(select("cx", query).profile == expected for query, expected in cases)
    assert correct / len(cases) >= 0.9


def test_multilingual_short_and_complex_requests_are_separated():
    short_query = "\uc0c1\ud0dc \ubcf4\uc5ec\uc918"
    complex_query = (
        "\uc804\uccb4 \ud65c\uc131 \ud53c\uc5b4\uac00 \ud1a0\ub860\ud558\uace0, "
        "\uad6c\ud604\ud558\uace0, \ud14c\uc2a4\ud2b8\ud55c \ud6c4 "
        "\uc124\uacc4 \uacb0\uacfc\ub97c \ubb38\uc11c\ub85c \ub0a8\uaca8\uc918."
    )
    assert select("cx", short_query).profile == "standard"
    assert select("cx", complex_query).profile == "deepthink"


def test_explicit_profile_honors_expired_profile_cooldown():
    health = {
        "availability": {
            "gate_open": True,
            "profiles": {
                "fable": {
                    "gate_open": False,
                    "rate_limit_state": {
                        "limited": True,
                        "reset_at": "2000-01-01T00:00:00+00:00",
                    },
                },
            },
        },
    }

    decision = hub_profile_router.select_profile_node(
        "cc.fable",
        "Use the arbiter.",
        orchestration=_orch(),
        routing_config=_routing(),
        health=health,
    )

    assert decision.node_id == "cc.fable"


def test_explicit_profile_blocks_unexpired_profile_cooldown():
    health = {
        "availability": {
            "gate_open": True,
            "profiles": {
                "fable": {
                    "gate_open": False,
                    "rate_limit_state": {
                        "limited": True,
                        "reset_at": "2999-01-01T00:00:00+00:00",
                    },
                },
            },
        },
    }

    try:
        hub_profile_router.select_profile_node(
            "cc.fable",
            "Use the arbiter.",
            orchestration=_orch(),
            routing_config=_routing(),
            health=health,
        )
    except hub_profile_router.ProfileRoutingError as exc:
        assert "fable" in str(exc)
    else:
        raise AssertionError("unexpired explicit profile cooldown must stay blocked")


def test_profile_for_score_boundaries():
    """mega-mece-audit-2026-07-16 item C: the medium band is an intentional
    fallthrough to config['ambiguous_default'], not a distinct branch."""
    config = {"thresholds": {"effort_score": 3, "deepthink_score": 8}}

    # Standard: score < 3 AND standard_evidence = True
    assert hub_profile_router._profile_for_score(2, [], True, config) == "standard"
    assert hub_profile_router._profile_for_score(0, [], True, config) == "standard"

    # Ambiguous medium-band (3-7) with no ambiguous_default configured:
    # falls back to the function's own built-in default ("deepthink").
    assert hub_profile_router._profile_for_score(3, [], True, config) == "deepthink"
    assert hub_profile_router._profile_for_score(7, [], True, config) == "deepthink"

    # Deepthink: score >= 8, regardless of ambiguous_default
    assert hub_profile_router._profile_for_score(8, [], True, config) == "deepthink"

    # Ambiguous medium-band respects an explicitly configured default --
    # this is the real routing-config.json behavior (ambiguous_default:
    # "effort"), proving the fallthrough is config-driven, not hardcoded.
    effort_default_config = {**config, "ambiguous_default": "effort"}
    signals: list[str] = []
    assert hub_profile_router._profile_for_score(5, signals, True, effort_default_config) == "effort"
    assert "ambiguous_default" in signals
    assert hub_profile_router._profile_for_score(15, [], True, config) == "deepthink"
