import json
import sys
from pathlib import Path

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
    
    # 2. Invalid peer/profile routing refs
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

    # 3. Voter-list consistency
    consensus = orch.get("consensus", {})
    r10_voters = set(consensus.get("r10_voters", []))
    inactive_voters = set(consensus.get("inactive_default_voters", []))
    overlap = r10_voters.intersection(inactive_voters)
    if overlap:
        log_error(f"orchestration.json: consensus.r10_voters and inactive_default_voters overlap: {overlap}")
        
    for v in r10_voters.union(inactive_voters):
        if v not in peers and v not in valid_peers:
            log_error(f"orchestration.json: Voter '{v}' references a non-existent peer")

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
