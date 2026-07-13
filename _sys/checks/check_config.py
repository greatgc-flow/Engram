import json
import sys
from pathlib import Path


REQUIRED_PROFILE_NAMES = {"standard", "effort", "deepthink"}
VALID_PROFILE_CLASSES = {"tier", "specialty"}
VALID_QUOTA_FAMILIES = {"C", "F", "G", "3P", "X"}
VALID_INTELLIGENCE_ESTIMATE_KINDS = {"point", "range"}
VALID_PROFILE_INTENT_SELECTION_BASES = {"resilience_over_external_composite"}
VALID_PROFILE_INTENT_WORKLOADS = {
    "long_context", "tool_use", "multi_turn_instruction_following",
}
VALID_TIER_SCORE_EXCEPTION_KINDS = {"external_composite_inversion"}
VALID_TIER_SCORE_EXCEPTION_STATUSES = {"accepted_policy_exception"}

def dict_raise_on_duplicates(ordered_pairs):
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise ValueError(f"Duplicate key found: {k}")
        else:
            d[k] = v
    return d

def validate_config(ai_dir: Path | str) -> bool:
    ai_dir = Path(ai_dir)
    success = True
    
    def log_error(msg):
        nonlocal success
        success = False
        print(f"ERROR: {msg}", file=sys.stderr)
        
    def log_warn(msg):
        print(f"WARN: {msg}", file=sys.stderr)
    
    # 1. Parse JSON files with duplicate key detection
    parsed_configs = {}
    for file_name in ["protocol.json", "orchestration.json", "peers.json", "routing-config.json", "lifecycle_policy.json"]:
        p = ai_dir / file_name
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    parsed_configs[file_name] = json.load(f, object_pairs_hook=dict_raise_on_duplicates)
            except ValueError as e:
                log_error(f"{file_name}: {e}")
                parsed_configs[file_name] = {}
            except Exception as e:
                log_error(f"{file_name}: Failed to parse - {e}")
                parsed_configs[file_name] = {}
        else:
            parsed_configs[file_name] = {}
            
    orch = parsed_configs.get("orchestration.json", {})
    peers = parsed_configs.get("peers.json", {}).get("peers", {})
    routing = parsed_configs.get("routing-config.json", {})
    
    hub_nodes = orch.get("hub_nodes", [])
    valid_peers = {node.get("node_id"): node for node in hub_nodes if "node_id" in node}

    # 2a. D2/D4 profile-policy contract. Taxonomy is descriptive only: routing
    # authority remains routing_state/arbiter_models/bulk_exclude_profiles.
    profile_entries = []
    for node in hub_nodes:
        if node.get("type") != "peer":
            continue
        peer_id = node.get("node_id", "<missing>")
        enabled = node.get("enabled", True) is not False
        profiles = node.get("profiles", {})
        if not isinstance(profiles, dict):
            log_error(f"orchestration.json: peer '{peer_id}' profiles must be a dictionary")
            continue

        if enabled:
            missing = REQUIRED_PROFILE_NAMES - set(profiles)
            if missing:
                log_error(
                    f"orchestration.json: enabled peer '{peer_id}' missing tier profiles "
                    f"{sorted(missing)}"
                )

        for profile_name, profile in profiles.items():
            profile_id = f"{peer_id}.{profile_name}"
            if not isinstance(profile, dict):
                log_error(f"orchestration.json: profile '{profile_id}' must be a dictionary")
                continue

            profile_class = profile.get("profile_class")
            if profile_class not in VALID_PROFILE_CLASSES:
                log_error(
                    f"orchestration.json: profile '{profile_id}' profile_class must be "
                    "'tier' or 'specialty'"
                )
            elif profile_name in REQUIRED_PROFILE_NAMES and profile_class != "tier":
                log_error(f"orchestration.json: required profile '{profile_id}' must be class 'tier'")
            elif profile_name not in REQUIRED_PROFILE_NAMES and profile_class != "specialty":
                log_error(f"orchestration.json: non-tier profile '{profile_id}' must be class 'specialty'")

            quota_families = profile.get("quota_families")
            if enabled and (not isinstance(quota_families, list) or not quota_families):
                log_error(
                    f"orchestration.json: enabled profile '{profile_id}' must declare "
                    "a non-empty quota_families list"
                )
                normalized_families = []
            elif quota_families is None and not enabled:
                normalized_families = []
            elif not isinstance(quota_families, list):
                log_error(f"orchestration.json: profile '{profile_id}' quota_families must be a list")
                normalized_families = []
            else:
                normalized_families = quota_families
                invalid = [family for family in quota_families if family not in VALID_QUOTA_FAMILIES]
                if invalid:
                    log_error(
                        f"orchestration.json: profile '{profile_id}' has invalid quota families "
                        f"{invalid}"
                    )
                if len(quota_families) != len(set(quota_families)):
                    log_error(f"orchestration.json: profile '{profile_id}' has duplicate quota families")

            # D3: declared intelligence evidence is optional metadata only. It
            # is deliberately validated here, but never becomes routing input.
            evidence = profile.get("intelligence_evidence")
            if evidence is not None:
                if not isinstance(evidence, dict):
                    log_error(f"orchestration.json: profile '{profile_id}' intelligence_evidence must be an object")
                else:
                    required = {"estimate", "scale", "source_kind", "verification", "source_ref", "as_of"}
                    missing_evidence = sorted(required - set(evidence))
                    if missing_evidence:
                        log_error(
                            f"orchestration.json: profile '{profile_id}' intelligence_evidence missing "
                            f"{missing_evidence}"
                        )
                    estimate = evidence.get("estimate")
                    if not isinstance(estimate, dict):
                        log_error(f"orchestration.json: profile '{profile_id}' intelligence_evidence.estimate must be an object")
                    else:
                        kind = estimate.get("kind")
                        if kind not in VALID_INTELLIGENCE_ESTIMATE_KINDS:
                            log_error(
                                f"orchestration.json: profile '{profile_id}' intelligence_evidence.estimate.kind "
                                "must be 'point' or 'range'"
                            )
                        if estimate.get("approximate") is not True:
                            log_error(
                                f"orchestration.json: profile '{profile_id}' intelligence_evidence.estimate "
                                "must set approximate=true"
                            )
                        if kind == "point":
                            value = estimate.get("value")
                            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                                    or "min" in estimate or "max" in estimate):
                                log_error(
                                    f"orchestration.json: profile '{profile_id}' intelligence_evidence point "
                                    "needs numeric value only"
                                )
                        elif kind == "range":
                            minimum, maximum = estimate.get("min"), estimate.get("max")
                            valid_range = (
                                isinstance(minimum, (int, float)) and not isinstance(minimum, bool)
                                and isinstance(maximum, (int, float)) and not isinstance(maximum, bool)
                                and minimum <= maximum and "value" not in estimate
                            )
                            if not valid_range:
                                log_error(
                                    f"orchestration.json: profile '{profile_id}' intelligence_evidence range "
                                    "needs numeric min <= max only"
                                )
                    for field in ("scale", "source_kind", "verification", "source_ref", "as_of"):
                        if not isinstance(evidence.get(field), str) or not evidence.get(field).strip():
                            log_error(
                                f"orchestration.json: profile '{profile_id}' intelligence_evidence.{field} "
                                "must be a non-empty string"
                            )
                    if evidence.get("source_kind") == "declared" and evidence.get("verification") != "unverified":
                        log_error(
                            f"orchestration.json: profile '{profile_id}' declared intelligence_evidence "
                            "must be verification='unverified'"
                        )

            # D6: an explicit same-peer exception documents an intentional
            # external-composite inversion; it does not alter routing policy.
            intent = profile.get("profile_intent")
            if intent is not None:
                if not isinstance(intent, dict):
                    log_error(f"orchestration.json: profile '{profile_id}' profile_intent must be an object")
                else:
                    if intent.get("selection_basis") not in VALID_PROFILE_INTENT_SELECTION_BASES:
                        log_error(
                            f"orchestration.json: profile '{profile_id}' profile_intent.selection_basis is invalid"
                        )
                    workloads = intent.get("workloads")
                    if (not isinstance(workloads, list) or not workloads
                            or any(item not in VALID_PROFILE_INTENT_WORKLOADS for item in workloads)):
                        log_error(
                            f"orchestration.json: profile '{profile_id}' profile_intent.workloads is invalid"
                        )
                    exception = intent.get("tier_score_exception")
                    if not isinstance(exception, dict):
                        log_error(
                            f"orchestration.json: profile '{profile_id}' profile_intent.tier_score_exception "
                            "must be an object"
                        )
                    else:
                        relative_to = exception.get("relative_to")
                        same_peer_prefix = f"{peer_id}."
                        relative_name = (
                            relative_to[len(same_peer_prefix):]
                            if isinstance(relative_to, str) and relative_to.startswith(same_peer_prefix)
                            else None
                        )
                        if relative_name not in profiles or relative_name == profile_name:
                            log_error(
                                f"orchestration.json: profile '{profile_id}' profile_intent relative_to "
                                "must resolve to another profile on the same peer"
                            )
                        if exception.get("kind") not in VALID_TIER_SCORE_EXCEPTION_KINDS:
                            log_error(
                                f"orchestration.json: profile '{profile_id}' profile_intent "
                                "tier_score_exception.kind is invalid"
                            )
                        if exception.get("status") not in VALID_TIER_SCORE_EXCEPTION_STATUSES:
                            log_error(
                                f"orchestration.json: profile '{profile_id}' profile_intent "
                                "tier_score_exception.status is invalid"
                            )
                    if intent.get("evidence_status") != "declared_unverified":
                        log_error(
                            f"orchestration.json: profile '{profile_id}' profile_intent.evidence_status "
                            "must be 'declared_unverified'"
                        )
                    if not isinstance(intent.get("source_ref"), str) or not intent.get("source_ref").strip():
                        log_error(
                            f"orchestration.json: profile '{profile_id}' profile_intent.source_ref "
                            "must be a non-empty string"
                        )

            profile_entries.append({
                "peer": peer_id,
                "profile": profile_id,
                "enabled": enabled,
                "routing_state": profile.get("routing_state"),
                "quota_families": set(normalized_families),
            })

    # A protected profile sharing a quota family with an eligible bulk profile
    # needs an explicit reserve. Specialty class alone never grants protection.
    tlb = routing.get("token_load_balancing", {}) or {}
    arbiter_models = set(tlb.get("arbiter_models", []) or [])
    bulk_excluded = set(tlb.get("bulk_exclude_profiles", []) or [])
    protected_entries = []
    bulk_entries = []
    for entry in profile_entries:
        if not entry["enabled"]:
            continue
        protected = (
            entry["profile"] in arbiter_models
            or entry["peer"] in arbiter_models
            or entry["profile"] in bulk_excluded
            or entry["peer"] in bulk_excluded
            or entry["routing_state"] == "manual_only"
        )
        if protected:
            protected_entries.append(entry)
        elif entry["routing_state"] == "eligible":
            bulk_entries.append(entry)

    reserve_cfg = tlb.get("shared_quota_reserve", {}) or {}
    reserve_families = reserve_cfg.get("families", {}) or {}
    for protected in protected_entries:
        for family in protected["quota_families"]:
            shared_with_bulk = any(
                family in bulk["quota_families"] and bulk["profile"] != protected["profile"]
                for bulk in bulk_entries
            )
            if not shared_with_bulk:
                continue
            family_cfg = reserve_families.get(family, {}) or {}
            reserve_for = set(family_cfg.get("reserve_for", []) or [])
            if not reserve_cfg.get("enabled") or protected["profile"] not in reserve_for:
                log_error(
                    f"routing-config.json: protected profile '{protected['profile']}' shares "
                    f"quota family '{family}' with bulk but is not protected by "
                    "shared_quota_reserve"
                )
    
    # 2b. Invalid peer/profile routing refs
    routing_weights = routing.get("routing_weights", {})
    for r_key, r_val in routing_weights.items():
        if not isinstance(r_val, dict):
            continue
        for target in (r_val.get("primary"), r_val.get("fallback")):
            if isinstance(target, str) and "::" in target:
                parts = target.split("::")
                if len(parts) >= 2:
                    peer, ref = parts[0], parts[1]
                    if peer not in valid_peers:
                        log_error(f"routing-config.json: Invalid peer '{peer}' in target '{target}'")
                    else:
                        peer_node = valid_peers[peer]
                        profiles = peer_node.get("profiles", {})
                        valid_refs = set(profiles.keys())
                        for p_data in profiles.values():
                            if isinstance(p_data, dict):
                                if "model_id" in p_data:
                                    valid_refs.add(p_data["model_id"])
                                if "runtime_model" in p_data:
                                    valid_refs.add(p_data["runtime_model"])
                        if ref not in valid_refs:
                            log_error(f"routing-config.json: Invalid profile/ref '{ref}' for peer '{peer}' in target '{target}'")

    # 3. Voter-list consistency — check BOTH surfaces: orchestration.json AND protocol.json
    #    (runtime consensus reads protocol.json["consensus"]["r10_voters"], so it must be
    #    validated too — orchestration alone misses an injected protocol.json overlap).
    protocol = parsed_configs.get("protocol.json", {})
    for src_name, src in (("orchestration.json", orch), ("protocol.json", protocol)):
        consensus = src.get("consensus", {})
        r10_voters = set(consensus.get("r10_voters", []))
        inactive_voters = set(consensus.get("inactive_default_voters", []))
        overlap = r10_voters.intersection(inactive_voters)
        if overlap:
            log_error(f"{src_name}: consensus.r10_voters and inactive_default_voters overlap: {overlap}")
        for v in r10_voters.union(inactive_voters):
            if v not in peers and v not in valid_peers:
                log_error(f"{src_name}: Voter '{v}' references a non-existent peer")

    # 5. malformed peers.json node_ids/sys_subdir shape
    for peer_id, p_cfg in peers.items():
        if not isinstance(p_cfg, dict):
            log_error(f"peers.json: peer '{peer_id}' config is not a dictionary")
            continue
        if "node_ids" in p_cfg and not isinstance(p_cfg["node_ids"], list):
            log_error(f"peers.json: peer '{peer_id}' node_ids must be a list")
        if "sys_subdir" in p_cfg and not isinstance(p_cfg["sys_subdir"], str):
            log_error(f"peers.json: peer '{peer_id}' sys_subdir must be a string")
            
    return success

if __name__ == "__main__":
    sys_dir = Path(__file__).parent.parent
    ai_dir = sys_dir / "ai"
    if validate_config(ai_dir):
        print("PASS")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(1)
