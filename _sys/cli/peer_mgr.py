#!/usr/bin/env python3
"""Peer lifecycle management — add, suspend, resume, remove, validate.

Reduces the 11-file blast radius to a single command. All JSON edits are
atomic (write-to-temp then rename) and idempotent.

Usage:
  peer_mgr.py add <peer_id> --invoke <cmd> [--model <model_id>] [--dry-run]
  peer_mgr.py suspend <peer_id> [--reason <text>] [--dry-run]
  peer_mgr.py resume <peer_id> [--dry-run]
  peer_mgr.py remove <peer_id> [--dry-run]
  peer_mgr.py validate [--strict]
  peer_mgr.py status

  peer_id  : logical node ID (e.g. cx, ag, cc)
  --invoke : executable name (e.g. codex, agy)
  --model  : default model ID (optional; added to model_profiles.json)
  --dry-run: print changes without writing
  --strict : treat warnings as errors in validate

Files modified:
  _sys/ai/orchestration.json       — hub_nodes add/enable/disable
  _sys/ai/peers.json               — peers registry enabled flag
  _sys/ai/model_profiles.json      — routing_state eligible/blocked
  _sys/ai/protocol.json            — default_voters / r10_voters lists
  _sys/ai/status_checks.json       — peer status eligible/blocked
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

_SYS = Path(__file__).parent.parent
_ORCH = _SYS / "ai" / "orchestration.json"
_PEERS = _SYS / "ai" / "peers.json"
_PROFILES = _SYS / "ai" / "model_profiles.json"
_PROTOCOL = _SYS / "ai" / "protocol.json"
_STATUS = _SYS / "ai" / "status_checks.json"


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: Any, dry_run: bool = False) -> None:
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"  [DRY-RUN] would write {path.relative_to(_SYS)}")
        return
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    print(f"  wrote {path.relative_to(_SYS)}")


# ─── Orchestration helpers ────────────────────────────────────────────────────

def _orch_set_enabled(nodes: list[dict], peer_id: str, enabled: bool | None) -> bool:
    for node in nodes:
        if node.get("node_id") == peer_id:
            if enabled is None:
                node.pop("enabled", None)
            else:
                node["enabled"] = enabled
            return True
    return False


def _orch_find(nodes: list[dict], peer_id: str) -> dict | None:
    return next((n for n in nodes if n.get("node_id") == peer_id), None)


# ─── Protocol helpers ─────────────────────────────────────────────────────────

def _find_voter_lists(obj: Any, path: str = "") -> list[tuple[str, list, Any, str]]:
    """Return [(path, list_ref, parent_dict, key)] for all voter lists (excluding inactive)."""
    result = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "voter" in k and isinstance(v, list) and "inactive" not in k:
                result.append((f"{path}.{k}", v, obj, k))
            else:
                result.extend(_find_voter_lists(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            result.extend(_find_voter_lists(item, f"{path}[{i}]"))
    return result


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_suspend(peer_id: str, reason: str, dry_run: bool) -> int:
    print(f"Suspending peer: {peer_id}")

    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    if not _orch_find(nodes, peer_id):
        print(f"[ERROR] peer {peer_id!r} not found in orchestration.json", file=sys.stderr)
        return 1

    # Disable only local peer state. Descendants inherit effective disablement
    # through parent_node and retain their independent local enabled setting.
    changed = _orch_set_enabled(nodes, peer_id, False)
    if changed:
        print(f"  orchestration.json: {peer_id}.enabled = false")

    if not changed:
        print(f"  orchestration.json: {peer_id} already disabled")
    _save(_ORCH, orch, dry_run)

    # peers.json
    peers_data = _load(_PEERS)
    if peers_data:
        for pk, pv in peers_data.get("peers", {}).items():
            if isinstance(pv, dict) and (
                peer_id in pv.get("node_ids", [])
                or pv.get("node_id") == peer_id
                or pk == peer_id
            ):
                pv["enabled"] = False
                print(f"  peers.json: {pk}.enabled = false")
        _save(_PEERS, peers_data, dry_run)

    # model_profiles.json — block all profiles for this peer
    mp = _load(_PROFILES)
    if mp:
        for pkey, pval in mp.get("profiles", {}).items():
            if pkey.startswith(f"{peer_id}."):
                pval["routing_state"] = "blocked"
                print(f"  model_profiles.json: {pkey}.routing_state = blocked")
        _save(_PROFILES, mp, dry_run)

    # protocol.json — remove from voters
    proto = _load(_PROTOCOL)
    if proto:
        voter_lists = _find_voter_lists(proto)
        for path, lst, parent, key in voter_lists:
            if peer_id in lst:
                parent[key] = [v for v in lst if v != peer_id]
                print(f"  protocol.json: removed {peer_id!r} from {path}")
        _save(_PROTOCOL, proto, dry_run)

    # status_checks.json
    sc = _load(_STATUS)
    if sc and peer_id in sc:
        sc[peer_id]["status"] = "blocked"
        sc[peer_id].setdefault("_note", f"suspended: {reason}")
        print(f"  status_checks.json: {peer_id}.status = blocked")
        _save(_STATUS, sc, dry_run)

    print(f"\nDone. {peer_id} suspended.")
    if reason:
        print(f"Reason: {reason}")
    return 0


def cmd_resume(peer_id: str, dry_run: bool) -> int:
    print(f"Resuming peer: {peer_id}")

    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    node = _orch_find(nodes, peer_id)
    if not node:
        print(f"[ERROR] peer {peer_id!r} not found in orchestration.json", file=sys.stderr)
        return 1

    # Re-enable peer node; leave virtual children alone (they may have own rules)
    node.pop("enabled", None)  # remove enabled:false → defaults to true
    print(f"  orchestration.json: {peer_id}.enabled = true (flag removed)")
    _save(_ORCH, orch, dry_run)

    peers_data = _load(_PEERS)
    if peers_data:
        for pk, pv in peers_data.get("peers", {}).items():
            if isinstance(pv, dict) and (
                peer_id in pv.get("node_ids", [])
                or pv.get("node_id") == peer_id
                or pk == peer_id
            ):
                pv["enabled"] = True
                print(f"  peers.json: {pk}.enabled = true")
        _save(_PEERS, peers_data, dry_run)

    # model_profiles.json — unblock profiles
    mp = _load(_PROFILES)
    if mp:
        for pkey, pval in mp.get("profiles", {}).items():
            if pkey.startswith(f"{peer_id}."):
                pval["routing_state"] = "eligible"
                print(f"  model_profiles.json: {pkey}.routing_state = eligible")
        _save(_PROFILES, mp, dry_run)

    # status_checks.json
    sc = _load(_STATUS)
    if sc and peer_id in sc:
        sc[peer_id]["status"] = "eligible"
        sc[peer_id].pop("_note", None)
        print(f"  status_checks.json: {peer_id}.status = eligible")
        _save(_STATUS, sc, dry_run)

    print(f"\nDone. {peer_id} resumed.")
    print("NOTE: You must manually add the peer back to protocol.json voters if desired.")
    return 0


def cmd_add(peer_id: str, invoke: str, model: str | None, dry_run: bool) -> int:
    print(f"Adding peer: {peer_id} (invoke={invoke})")

    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]

    if _orch_find(nodes, peer_id):
        print(f"  orchestration.json: {peer_id} already exists — skipping add")
    else:
        new_node: dict = {
            "node_id": peer_id,
            "type": "peer",
            "invoke": invoke,
            "invoke_args": ["-p", "{query}"],
            "memory": "persistent",
            "timeout": 0,
        }
        nodes.append(new_node)
        print(f"  orchestration.json: added {peer_id} node (invoke={invoke})")
    _save(_ORCH, orch, dry_run)

    # model_profiles.json — add default profile if model given
    if model:
        mp = _load(_PROFILES)
        if mp and f"{peer_id}.default" not in mp.get("profiles", {}):
            mp.setdefault("profiles", {})[f"{peer_id}.default"] = {
                "model_id": model,
                "routing_state": "eligible",
                "effort": "medium",
                "_note": "auto-generated by peer_mgr.py add",
            }
            print(f"  model_profiles.json: added {peer_id}.default (model={model})")
            _save(_PROFILES, mp, dry_run)

    print(f"\nDone. {peer_id} added.")
    print("Next steps:")
    print(f"  1. Add {peer_id} to protocol.json default_voters / r10_voters")
    print(f"  2. Create docs-v2/specific/{peer_id}.md")
    print(f"  3. Run: python checks/validate_peer_config.py")
    return 0


def cmd_remove(peer_id: str, dry_run: bool) -> int:
    """Remove a peer entirely. Peer must be suspended first."""
    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    node = _orch_find(nodes, peer_id)
    if node and node.get("enabled") is not False:
        print(f"[ERROR] peer {peer_id!r} is still enabled. Run 'suspend' first.", file=sys.stderr)
        return 1

    before = len(nodes)
    orch["hub_nodes"] = [n for n in nodes if n.get("node_id") != peer_id
                         and n.get("peer") != peer_id
                         and n.get("parent_node") != peer_id]
    removed = before - len(orch["hub_nodes"])
    print(f"  orchestration.json: removed {removed} node(s) for {peer_id}")
    _save(_ORCH, orch, dry_run)

    # model_profiles.json — remove profiles
    mp = _load(_PROFILES)
    if mp:
        profiles = mp.get("profiles", {})
        to_remove = [k for k in profiles if k.startswith(f"{peer_id}.")]
        for k in to_remove:
            del profiles[k]
            print(f"  model_profiles.json: removed {k}")
        if to_remove:
            _save(_PROFILES, mp, dry_run)

    print(f"\nDone. {peer_id} removed from orchestration and profiles.")
    print("Manual cleanup still needed:")
    print(f"  - peers.json entry for {peer_id}")
    print(f"  - docs-v2/specific/{peer_id}.md (archive or delete)")
    print(f"  - Any remaining references in agent/*.json, tool-registry.json")
    return 0


def cmd_validate(strict: bool) -> int:
    validator_path = _SYS / "checks" / "validate_peer_config.py"
    if not validator_path.exists():
        print("[ERROR] checks/validate_peer_config.py not found", file=sys.stderr)
        return 1
    import subprocess
    cmd = [sys.executable, str(validator_path)]
    if strict:
        cmd.append("--strict")
    result = subprocess.run(cmd)
    return result.returncode


def cmd_status() -> int:
    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    print(f"\n{'NODE':12} {'TYPE':10} {'ENABLED':8} {'INVOKE':12}")
    print("-" * 50)
    for n in nodes:
        nid = n.get("node_id", "?")
        ntype = n.get("type", "?")
        enabled = "yes" if n.get("enabled", True) is not False else "NO"
        invoke = n.get("invoke", "?")
        print(f"{nid:12} {ntype:10} {enabled:8} {invoke:12}")
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a new peer")
    p_add.add_argument("peer_id")
    p_add.add_argument("--invoke", required=True)
    p_add.add_argument("--model", default=None)
    p_add.add_argument("--dry-run", action="store_true")

    p_suspend = sub.add_parser("suspend", help="Suspend (disable) a peer")
    p_suspend.add_argument("peer_id")
    p_suspend.add_argument("--reason", default="manually suspended")
    p_suspend.add_argument("--dry-run", action="store_true")

    p_resume = sub.add_parser("resume", help="Resume (re-enable) a peer")
    p_resume.add_argument("peer_id")
    p_resume.add_argument("--dry-run", action="store_true")

    p_remove = sub.add_parser("remove", help="Remove a suspended peer permanently")
    p_remove.add_argument("peer_id")
    p_remove.add_argument("--dry-run", action="store_true")

    p_val = sub.add_parser("validate", help="Run cross-config validator")
    p_val.add_argument("--strict", action="store_true")

    sub.add_parser("status", help="Show node table")

    args = parser.parse_args()

    if args.cmd == "add":
        return cmd_add(args.peer_id, args.invoke, args.model, args.dry_run)
    if args.cmd == "suspend":
        return cmd_suspend(args.peer_id, args.reason, args.dry_run)
    if args.cmd == "resume":
        return cmd_resume(args.peer_id, args.dry_run)
    if args.cmd == "remove":
        return cmd_remove(args.peer_id, args.dry_run)
    if args.cmd == "validate":
        return cmd_validate(args.strict)
    if args.cmd == "status":
        return cmd_status()
    return 1


if __name__ == "__main__":
    sys.exit(main())
