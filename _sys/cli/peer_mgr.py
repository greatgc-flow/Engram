#!/usr/bin/env python3
"""Peer lifecycle management — add, suspend, resume, remove, validate.

Reduces the 11-file blast radius to a single command. All JSON edits are
atomic (write-to-temp then rename) and idempotent.

Usage:
  peer_mgr.py add <peer_id> --invoke <cmd> [--provider <id>] [--model <model_id>] [--dry-run]
  peer_mgr.py suspend <peer_id> [--reason <text>] [--dry-run]
  peer_mgr.py resume <peer_id> [--dry-run]
  peer_mgr.py remove <peer_id> [--dry-run]
  peer_mgr.py validate [--strict]
  peer_mgr.py status

  peer_id  : logical node ID (e.g. cx, ag, cc)
  --invoke : executable name (e.g. codex, agy)
  --provider: existing installation/provider key; inferred when unambiguous
  --model  : model ID used to seed the three nested profiles
  --dry-run: print changes without writing
  --strict : treat warnings as errors in validate

Files modified:
  _sys/ai/orchestration.json       — hub_nodes add/enable/disable
  _sys/ai/peers.json               — peers registry enabled flag
  _sys/ai/protocol.json            — default_voters / r10_voters lists
  _sys/ai/status_checks.json       — probe definitions (not lifecycle state)
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
_PROTOCOL = _SYS / "ai" / "protocol.json"
_STATUS = _SYS / "ai" / "status_checks.json"
_SPECIFIC = _SYS / "docs-v2" / "specific"


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


def _set_list_membership(values: list, peer_id: str, present: bool) -> None:
    values[:] = [value for value in values if value != peer_id]
    if present:
        values.append(peer_id)


def _set_governance_membership(config: dict, peer_id: str, active: bool) -> None:
    """Keep voter, inactive-voter, and role registries lifecycle-consistent."""
    consensus = config.get("consensus", {})
    for key in ("default_voters", "r10_voters"):
        values = consensus.get(key)
        if isinstance(values, list):
            _set_list_membership(values, peer_id, active)
    inactive = consensus.get("inactive_default_voters")
    if isinstance(inactive, list):
        _set_list_membership(inactive, peer_id, not active)
    for key, values in config.get("roles_registry", {}).items():
        if not key.startswith("_") and isinstance(values, list):
            _set_list_membership(values, peer_id, active)


def _remove_governance_membership(config: dict, peer_id: str) -> None:
    consensus = config.get("consensus", {})
    for key in ("default_voters", "r10_voters", "inactive_default_voters"):
        values = consensus.get(key)
        if isinstance(values, list):
            _set_list_membership(values, peer_id, False)
    for key, values in config.get("roles_registry", {}).items():
        if not key.startswith("_") and isinstance(values, list):
            _set_list_membership(values, peer_id, False)


def _resolve_provider(
    peers_data: dict, nodes: list[dict], invoke: str, requested: str | None
) -> str | None:
    providers = peers_data.get("peers", {})
    if requested:
        return requested if requested in providers else None
    node_map = {node.get("node_id"): node for node in nodes}
    candidates = []
    for provider_id, provider in providers.items():
        native = provider.get("native_binary", {})
        matching_node = any(
            node_map.get(node_id, {}).get("invoke") == invoke
            for node_id in provider.get("node_ids", [])
        )
        if provider_id == invoke or native.get("bin_name") == invoke or matching_node:
            candidates.append(provider_id)
    return candidates[0] if len(candidates) == 1 else None


def _write_specific_doc(
    peer_id: str, provider_id: str, invoke: str, dry_run: bool
) -> None:
    path = _SPECIFIC / f"{peer_id}.md"
    if path.exists():
        return
    content = (
        f"# Specific — {peer_id}\n"
        f"> Delta from general/*. Status: ACTIVE.\n\n"
        "## Permission Flags\n\n"
        f"Adapter-specific invocation is declared in `orchestration.json` (`{invoke}`).\n\n"
        "## Runtime Profiles\n\n"
        f"`{peer_id}.standard`, `{peer_id}.effort`, and `{peer_id}.deepthink` "
        "are generated from the nested profile map.\n\n"
        "## Context and Collaboration\n\n"
        "This peer uses the common versioned room references, promotion/ACK "
        "boundary, equal governance, and role protocol.\n\n"
        f"Installation provider: `{provider_id}`.\n"
    )
    if dry_run:
        print(f"  [DRY-RUN] would write {path.relative_to(_SYS)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(_SYS)}")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_suspend(peer_id: str, reason: str, dry_run: bool) -> int:
    print(f"Suspending peer: {peer_id}")

    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    if "hub_nodes" not in orch:
        print("[ERROR] orchestration.json missing 'hub_nodes'", file=sys.stderr)
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
    _set_governance_membership(orch, peer_id, False)
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

    # protocol.json — remove from voters
    proto = _load(_PROTOCOL)
    if proto:
        _set_governance_membership(proto, peer_id, False)
        print(f"  protocol.json: {peer_id!r} moved to inactive voters")
        _save(_PROTOCOL, proto, dry_run)

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
    if "hub_nodes" not in orch:
        print("[ERROR] orchestration.json missing 'hub_nodes'", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    node = _orch_find(nodes, peer_id)
    if not node:
        print(f"[ERROR] peer {peer_id!r} not found in orchestration.json", file=sys.stderr)
        return 1

    # Re-enable only the root. Profile-local state remains unchanged.
    node.pop("enabled", None)  # remove enabled:false → defaults to true
    print(f"  orchestration.json: {peer_id}.enabled = true (flag removed)")
    _set_governance_membership(orch, peer_id, True)
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

    proto = _load(_PROTOCOL)
    if proto:
        _set_governance_membership(proto, peer_id, True)
        print(f"  protocol.json: {peer_id!r} restored to active voters")
        _save(_PROTOCOL, proto, dry_run)

    print(f"\nDone. {peer_id} resumed.")
    return 0


def cmd_add(
    peer_id: str,
    invoke: str,
    model: str | None,
    dry_run: bool,
    provider: str | None = None,
) -> int:
    print(f"Adding peer: {peer_id} (invoke={invoke})")

    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    if "hub_nodes" not in orch:
        print("[ERROR] orchestration.json missing 'hub_nodes'", file=sys.stderr)
        return 1
    nodes = orch["hub_nodes"]
    peers_data = _load(_PEERS) or {"peers": {}}
    provider_id = _resolve_provider(peers_data, nodes, invoke, provider)
    if provider_id is None:
        print(
            "[ERROR] provider could not be inferred; register installation in "
            "peers.json and pass --provider",
            file=sys.stderr,
        )
        return 1

    if _orch_find(nodes, peer_id):
        print(f"  orchestration.json: {peer_id} already exists — skipping add")
    else:
        template = next((n for n in nodes if n.get("invoke") == invoke), None)
        if template is None:
            print(
                f"[ERROR] unknown provider/invoke {invoke!r}: "
                "no safe orchestration template",
                file=sys.stderr,
            )
            return 1
        new_node: dict = {
            "node_id": peer_id,
            "type": "peer",
            "invoke": invoke,
            "adapter_class": template.get("adapter_class"),
            "invoke_args": template.get("invoke_args", []),
            "memory": template.get("memory"),
            "timeout": template.get("timeout", 0),
            "default_profile": "effort",
            "capability_class": template.get("capability_class"),
            "profiles": {
                tier: {
                    "model_id": model,
                    "routing_state": "eligible",
                    "profile_args": ["--model", model] if model else []
                }
                for tier in ("standard", "effort", "deepthink")
            },
        }
        for key in ("requires_pty", "session_mode"):
            if key in template:
                new_node[key] = template[key]
        nodes.append(new_node)
        print(f"  orchestration.json: added {peer_id} node (invoke={invoke})")
    _set_governance_membership(orch, peer_id, True)
    _save(_ORCH, orch, dry_run)

    provider_cfg = peers_data["peers"][provider_id]
    provider_cfg["enabled"] = True
    _set_list_membership(provider_cfg.setdefault("node_ids", []), peer_id, True)
    _save(_PEERS, peers_data, dry_run)

    proto = _load(_PROTOCOL)
    if proto:
        _set_governance_membership(proto, peer_id, True)
        _save(_PROTOCOL, proto, dry_run)

    status = _load(_STATUS) or {"peers": {}}
    sibling_ids = [
        node_id for node_id in provider_cfg.get("node_ids", [])
        if node_id != peer_id
    ]
    status.setdefault("peers", {}).setdefault(
        peer_id,
        {"inherits": sibling_ids[0]} if sibling_ids else {
            "safe_checks": [{
                "id": f"{peer_id}.version",
                "class": "version_only",
                "command": f"{invoke} --version",
                "effect_class": "read_only",
            }]
        },
    )
    _save(_STATUS, status, dry_run)
    _write_specific_doc(peer_id, provider_id, invoke, dry_run)

    print(f"\nDone. {peer_id} added.")
    print("Next: run peer_mgr.py validate --strict")
    return 0


def cmd_remove(peer_id: str, dry_run: bool) -> int:
    """Remove a peer entirely. Peer must be suspended first."""
    orch = _load(_ORCH)
    if orch is None:
        print("[ERROR] orchestration.json not found", file=sys.stderr)
        return 1
    if "hub_nodes" not in orch:
        print("[ERROR] orchestration.json missing 'hub_nodes'", file=sys.stderr)
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
    _remove_governance_membership(orch, peer_id)
    removed = before - len(orch["hub_nodes"])
    print(f"  orchestration.json: removed {removed} node(s) for {peer_id}")
    _save(_ORCH, orch, dry_run)

    peers_data = _load(_PEERS)
    if peers_data:
        for provider in peers_data.get("peers", {}).values():
            node_ids = provider.get("node_ids")
            if isinstance(node_ids, list):
                _set_list_membership(node_ids, peer_id, False)
        _save(_PEERS, peers_data, dry_run)

    proto = _load(_PROTOCOL)
    if proto:
        _remove_governance_membership(proto, peer_id)
        _save(_PROTOCOL, proto, dry_run)

    status = _load(_STATUS)
    if status and peer_id in status.get("peers", {}):
        status["peers"].pop(peer_id, None)
        _save(_STATUS, status, dry_run)

    doc = _SPECIFIC / f"{peer_id}.md"
    if doc.exists():
        archive = _SYS / "docs" / "history" / f"specific-{peer_id}.md"
        if dry_run:
            print(f"  [DRY-RUN] would archive {doc.relative_to(_SYS)}")
        else:
            archive.parent.mkdir(parents=True, exist_ok=True)
            os.replace(doc, archive)
            print(f"  archived {doc.relative_to(_SYS)}")

    print(f"\nDone. {peer_id} removed from logical runtime configuration.")
    print("Run validator to locate domain-specific references, if any.")
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
    if "hub_nodes" not in orch:
        print("[ERROR] orchestration.json missing 'hub_nodes'", file=sys.stderr)
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
    p_add.add_argument("--provider", default=None)
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
        return cmd_add(
            args.peer_id, args.invoke, args.model, args.dry_run, args.provider
        )
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
