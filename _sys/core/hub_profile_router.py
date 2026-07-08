"""Deterministic zero-token routing from root peers to runtime profiles."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import hub_peer
from snapshot import profile_health_gate_open


class ProfileRoutingError(RuntimeError):
    """Raised when a configured peer has no eligible profile."""


@dataclass(frozen=True)
class ProfileDecision:
    root_peer: str
    node_id: str
    profile: str
    requested_profile: str
    score: int
    signals: tuple[str, ...]
    confidence: float
    explicit: bool = False
    classifier_triggered: bool = True
    promoted: bool = False
    fallback_from: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["selected_profile"] = data.pop("profile")
        data["signals"] = list(self.signals)
        return data


def _config(routing_config: dict) -> dict:
    return routing_config.get("auto_profile_routing", {})


def _root_map(orchestration: dict) -> dict[str, dict]:
    return {
        node["node_id"]: node
        for node in orchestration.get("hub_nodes", [])
        if node.get("node_id") and node.get("type") == "peer"
    }


def _resolve_root(target: str, orchestration: dict) -> tuple[str | None, bool, str | None]:
    roots = _root_map(orchestration)
    if target in roots:
        return target, False, None
    for root_id, node in roots.items():
        if target in node.get("aliases", []) or target == node.get("invoke"):
            return root_id, False, None
    if "." in target:
        root_id, profile = target.split(".", 1)
        if root_id in roots and profile in roots[root_id].get("profiles", {}):
            return root_id, True, profile
    return None, False, None


def _explicit_tag(query: str, profile_order: list[str]) -> str | None:
    match = re.search(r"\[\s*profile\s*:\s*([a-z]+)\s*\]", query, re.IGNORECASE)
    if not match:
        return None
    profile = match.group(1).lower()
    return profile if profile in profile_order else None


def _risk_tag(query: str) -> int | None:
    match = re.search(r"\[\s*risk\s*:\s*(10|[0-9])\s*\]", query, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _marker_hits(query: str, markers: list[str]) -> list[str]:
    lowered = query.lower()
    return [marker for marker in markers if marker.lower() in lowered]


def _score_query(query: str, config: dict) -> tuple[int, list[str], bool]:
    signals_cfg = config.get("signals", {})
    thresholds = config.get("thresholds", {})
    score = 0
    signals: list[str] = []
    standard_evidence = False

    risk = _risk_tag(query)
    if risk is not None:
        if risk >= 8:
            score += int(signals_cfg.get("risk_high_weight", 10))
            signals.append("risk_high")
        elif risk >= 3:
            score += int(signals_cfg.get("risk_medium_weight", 4))
            signals.append("risk_medium")
        else:
            score -= int(signals_cfg.get("risk_low_weight", 4))
            signals.append("risk_low")
            standard_evidence = True

    for name, default_weight in (("deepthink", 5), ("effort", 3), ("standard", -4)):
        markers = list(signals_cfg.get(f"{name}_markers", []))
        hits = _marker_hits(query, markers)
        if not hits:
            continue
        weight = int(signals_cfg.get(f"{name}_marker_weight", default_weight))
        score += weight * min(len(hits), int(signals_cfg.get("marker_hit_cap", 2)))
        signals.extend(f"{name}_marker:{hit}" for hit in hits[:2])
        if name == "standard":
            standard_evidence = True

    char_count = len(query)
    if char_count >= int(thresholds.get("deepthink_min_chars", 4000)):
        score += int(signals_cfg.get("very_large_query_weight", 6))
        signals.append("very_large_query")
    elif char_count >= int(thresholds.get("effort_min_chars", 800)):
        score += int(signals_cfg.get("large_query_weight", 3))
        signals.append("large_query")

    structural_count = (
        query.count("\n-")
        + query.count("\n*")
        + query.count("```")
        + query.count(",")
        + query.count(";")
    )
    if structural_count >= int(thresholds.get("complex_structure_count", 4)):
        score += int(signals_cfg.get("complex_structure_weight", 3))
        signals.append("complex_structure")

    non_ascii = sum(1 for char in query if ord(char) > 127)
    non_ascii_ratio = non_ascii / max(1, char_count)
    token_count = len(query.split())
    if (
        non_ascii_ratio >= float(thresholds.get("multilingual_ratio", 0.3))
        and char_count <= int(thresholds.get("multilingual_simple_max_chars", 50))
        and structural_count == 0
    ):
        score -= int(signals_cfg.get("multilingual_simple_weight", 4))
        signals.append("multilingual_short")
        standard_evidence = True
    elif (
        non_ascii_ratio >= float(thresholds.get("multilingual_ratio", 0.3))
        and (
            char_count >= int(thresholds.get("multilingual_complex_min_chars", 80))
            or token_count >= int(
                thresholds.get("multilingual_complex_min_tokens", 8)
            )
        )
        and structural_count >= 2
    ):
        score += int(signals_cfg.get("multilingual_complex_weight", 8))
        signals.append("multilingual_complex")

    return score, signals, standard_evidence


def _profile_for_score(
    score: int,
    signals: list[str],
    standard_evidence: bool,
    config: dict,
) -> str:
    thresholds = config.get("thresholds", {})
    # If standard evidence is clearly met, use the cheapest option
    if standard_evidence and score < int(thresholds.get("effort_score", 3)):
        return "standard"
        
    # If it meets effort threshold but not deepthink, use effort (if explicitly configured to use effort as intermediate)
    # However, user requested default to deepthink unless "certain" (standard). 
    if score >= int(thresholds.get("deepthink_score", 8)):
        return "deepthink"
    if score >= int(thresholds.get("effort_score", 3)):
        # If config explicitly still wants effort, we can honor it, but let's change ambiguous default
        pass

    signals.append("ambiguous_default")
    return str(config.get("ambiguous_default", "deepthink"))


def _eligible_profile(
    root: dict,
    requested: str,
    profile_order: list[str],
    health: dict | None = None,
) -> tuple[str | None, str | None]:
    avail = health.get("availability", {}) if health else {}
    if not profile_health_gate_open(avail):
        return None, None
    health_profiles = avail.get("profiles", {})
    profiles = root.get("profiles", {})
    start = profile_order.index(requested)
    for index in range(start, -1, -1):
        candidate = profile_order[index]
        profile = profiles.get(candidate, {})
        h_prof = health_profiles.get(candidate, {})
        gate_open = profile_health_gate_open(h_prof)

        if (
            profile
            and profile.get("enabled") is not False
            and profile.get("routing_state") != "blocked"
            and gate_open
        ):
            return candidate, requested if candidate != requested else None
    raise ProfileRoutingError(
        f"all eligible profiles are blocked for peer '{root.get('node_id', '?')}'"
    )


def select_profile_node(
    target: str,
    query: str,
    *,
    orchestration: dict,
    routing_config: dict,
    consecutive_failures: int = 0,
    consecutive_failure_reason: str | None = None,
    health: dict | None = None,
) -> ProfileDecision:
    """Select a profile for a root target without invoking a model."""
    config = _config(routing_config)
    profile_order = list(config.get(
        "profile_order", ["standard", "effort", "deepthink"]
    ))
    root_id, explicit, explicit_profile = _resolve_root(target, orchestration)
    if root_id is None:
        raise ProfileRoutingError(f"unknown peer target '{target}'")
    root = _root_map(orchestration)[root_id]

    if explicit and explicit_profile:
        avail = health.get("availability", {}) if health else {}
        if not profile_health_gate_open(avail):
            raise ProfileRoutingError(f"peer '{root_id}' is completely unavailable")
        h_prof = avail.get("profiles", {}).get(explicit_profile, {})
        if not profile_health_gate_open(h_prof):
            raise ProfileRoutingError(f"explicit profile '{explicit_profile}' is currently unavailable")
        return ProfileDecision(
            root_peer=root_id,
            node_id=f"{root_id}.{explicit_profile}",
            profile=explicit_profile,
            requested_profile=explicit_profile,
            score=0,
            signals=("explicit_node",),
            confidence=1.0,
            explicit=True,
            classifier_triggered=False,
        )

    tagged = _explicit_tag(query, profile_order)
    if tagged:
        requested = tagged
        score = 0
        signals = ["explicit_tag"]
        confidence = 1.0
    else:
        score, signals, standard_evidence = _score_query(query, config)
        requested = _profile_for_score(score, signals, standard_evidence, config)
        distance = min(
            abs(score - int(config.get("thresholds", {}).get("effort_score", 3))),
            abs(score - int(config.get("thresholds", {}).get("deepthink_score", 8))),
        )
        confidence = min(1.0, 0.5 + (distance * 0.1) + (len(signals) * 0.05))

    promoted = False
    failure_cfg = config.get("failure_promotion", {})
    allowed_failure_reasons = set(failure_cfg.get("allowed_reasons", []))
    if (
        tagged is None
        and failure_cfg.get("enabled", True)
        and consecutive_failures >= int(failure_cfg.get("consecutive_threshold", 2))
        and consecutive_failure_reason in allowed_failure_reasons
    ):
        current_index = profile_order.index(requested)
        if current_index < len(profile_order) - 1:
            requested = profile_order[current_index + 1]
            promoted = True
            signals.append("failure_promotion")

    selected, fallback_from = _eligible_profile(root, requested, profile_order, health)
    if not selected:
        raise ProfileRoutingError(f"no eligible profile found for peer '{root_id}'")
    if fallback_from:
        signals.append(f"fallback_from:{fallback_from}")
    return ProfileDecision(
        root_peer=root_id,
        node_id=f"{root_id}.{selected}",
        profile=selected,
        requested_profile=requested,
        score=score,
        signals=tuple(signals),
        confidence=round(confidence, 3),
        promoted=promoted,
        fallback_from=fallback_from,
    )
