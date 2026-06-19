#!/usr/bin/env python3
"""Cross-config validator for Engram peer configuration.

Validates that all enabled peers have consistent entries across:
  - orchestration.json (hub_nodes)
  - peers.json (peer registry)
  - model_profiles.json (profiles with routing_state)
  - protocol.json (voters)
  - docs-v2/specific/{peer}.md (documentation)
  - collaboration_loop_bindings.json (no disabled profiles in routes)

Exit 0 = valid. Exit 1 = violations found.

Usage:
  python validate_peer_config.py [--strict] [--quiet]

Options:
  --strict   Treat warnings as errors
  --quiet    Only print errors (suppress info)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SYS = Path(__file__).parent.parent


def _load(rel: str) -> Any:
    path = _SYS / rel
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _orchestration_nodes() -> list[dict]:
    orch = _load("ai/orchestration.json") or {}
    return orch.get("hub_nodes", [])


class Validator:
    def __init__(self, strict: bool = False, quiet: bool = False):
        self.strict = strict
        self.quiet = quiet
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(f"[ERROR] {msg}")

    def warn(self, msg: str) -> None:
        if self.strict:
            self.errors.append(f"[WARN→ERROR] {msg}")
        else:
            self.warnings.append(f"[WARN] {msg}")

    def info(self, msg: str) -> None:
        if not self.quiet:
            print(f"  ✓ {msg}")

    def run(self) -> int:
        nodes = _orchestration_nodes()
        if not nodes:
            self.error("orchestration.json hub_nodes is empty or file missing")
            self._report()
            return 1

        nodes_map = {n["node_id"]: n for n in nodes if "node_id" in n}
        enabled_peers = [n for n in nodes if n.get("type") == "peer" and n.get("enabled", True) is not False]
        disabled_peers = [n for n in nodes if n.get("type") == "peer" and n.get("enabled") is False]
        enabled_ids = {n["node_id"] for n in enabled_peers if "node_id" in n}
        disabled_ids = {n["node_id"] for n in disabled_peers if "node_id" in n}

        self._check_orchestration(nodes, nodes_map, enabled_peers, disabled_peers)
        self._check_peers_json(enabled_ids, disabled_ids)
        self._check_model_profiles(disabled_ids)
        self._check_protocol_voters(enabled_ids)
        self._check_docs(enabled_ids, disabled_ids)
        self._check_loop_bindings(disabled_ids)

        self._report()
        return 1 if self.errors else 0

    def _check_orchestration(self, nodes, nodes_map, enabled_peers, disabled_peers):
        label = "orchestration.json"
        # No duplicate node IDs
        ids = [n["node_id"] for n in nodes if "node_id" in n]
        dups = [x for x in ids if ids.count(x) > 1]
        if dups:
            self.error(f"{label}: duplicate node_ids: {list(set(dups))}")
        else:
            self.info(f"{label}: no duplicate node_ids ({len(ids)} total)")

        # Virtual nodes must reference a real parent
        for n in nodes:
            if n.get("type") == "virtual":
                parent_id = n.get("parent_node")
                if parent_id and parent_id not in nodes_map:
                    self.error(f"{label}: virtual node {n.get('node_id')!r} references missing parent {parent_id!r}")
                if parent_id is None:
                    # Virtual nodes may use 'peer' field instead of 'parent_node'
                    if n.get("peer"):
                        self.warn(f"{label}: virtual node {n.get('node_id')!r} uses legacy peer field; use parent_node")
                    else:
                        self.error(f"{label}: virtual node {n.get('node_id')!r} has no parent_node")

        # Disabled parent → virtual child should also have enabled:false
        for n in nodes:
            if n.get("type") == "virtual":
                parent_id = n.get("parent_node")
                if parent_id:
                    parent = nodes_map.get(parent_id)
                    if parent and parent.get("enabled") is False:
                        pass  # Effective disablement is inherited; do not copy local state.

        for node_id in ids:
            seen = set()
            current = node_id
            while current:
                if current in seen:
                    self.error(f"{label}: parent cycle detected at {current!r} from {node_id!r}")
                    break
                seen.add(current)
                current_node = nodes_map.get(current)
                if current_node is None:
                    break
                current = current_node.get("parent_node") or (
                    current_node.get("peer")
                    if current_node.get("type") == "virtual"
                    else None
                )

        self.info(f"{label}: {len(enabled_peers)} enabled peers, {len(disabled_peers)} disabled peers")

    def _check_peers_json(self, enabled_ids: set, disabled_ids: set):
        label = "peers.json"
        data = _load("ai/peers.json")
        if data is None:
            self.warn(f"{label}: file not found")
            return
        peer_entries = data.get("peers", {}) if isinstance(data, dict) else {}
        registered_ids = set(peer_entries.keys())
        self.info(f"{label}: {len(registered_ids)} peer entries ({', '.join(sorted(registered_ids))})")

        # Identity split check: every entry should declare node_ids mapping
        all_declared_node_ids: set[str] = set()
        for peer_key, peer_val in peer_entries.items():
            if not isinstance(peer_val, dict):
                continue
            if peer_val.get("enabled") is False:
                self.info(f"{label}: {peer_key} correctly marked enabled:false")
            nids = peer_val.get("node_ids")
            if nids is None:
                self.warn(f"{label}: {peer_key} missing node_ids field (identity split unresolved)")
            elif isinstance(nids, list):
                all_declared_node_ids.update(nids)

        # All enabled/disabled orchestration peer IDs should be declared in some node_ids list
        all_orch_peer_ids = enabled_ids | disabled_ids
        undeclared = all_orch_peer_ids - all_declared_node_ids
        if undeclared:
            self.warn(f"{label}: orchestration peer IDs not in any node_ids: {sorted(undeclared)}")
        else:
            self.info(f"{label}: identity split resolved — all orchestration peer IDs declared in node_ids")

    def _check_model_profiles(self, disabled_ids: set):
        label = "model_profiles.json"
        data = _load("ai/model_profiles.json")
        if data is None:
            self.warn(f"{label}: file not found")
            return
        profiles = data.get("profiles", {})
        blocked_violations = []
        for profile_key, profile_val in profiles.items():
            peer_prefix = profile_key.split(".")[0]
            if peer_prefix in disabled_ids:
                state = profile_val.get("routing_state")
                if state != "blocked":
                    blocked_violations.append(f"{profile_key} (routing_state={state!r})")
        if blocked_violations:
            for v in blocked_violations:
                self.error(f"{label}: disabled peer profile not blocked: {v}")
        else:
            disabled_profiles = [k for k in profiles if k.split(".")[0] in disabled_ids]
            self.info(f"{label}: all {len(disabled_profiles)} disabled-peer profiles correctly blocked")

    def _check_protocol_voters(self, enabled_ids: set):
        label = "protocol.json"
        data = _load("ai/protocol.json")
        if data is None:
            self.warn(f"{label}: file not found")
            return

        def find_voters(obj, path=""):
            found = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if "voter" in k and isinstance(v, list) and "inactive" not in k:
                        found.append((f"{path}.{k}", v))
                    else:
                        found.extend(find_voters(v, f"{path}.{k}"))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    found.extend(find_voters(item, f"{path}[{i}]"))
            return found

        voter_violations = []
        for path, voters in find_voters(data):
            for voter in voters:
                if voter not in enabled_ids:
                    voter_violations.append(f"{path}: {voter!r} not in enabled peers")
        if voter_violations:
            for v in voter_violations:
                self.error(f"{label}: disabled peer in voter list: {v}")
        else:
            self.info(f"{label}: all active voter lists reference enabled peers only")

    def _check_docs(self, enabled_ids: set, disabled_ids: set):
        label = "docs-v2/specific/"
        spec_dir = _SYS / "docs-v2" / "specific"
        if not spec_dir.exists():
            self.warn(f"{label}: directory not found")
            return

        for peer_id in enabled_ids:
            doc = spec_dir / f"{peer_id}.md"
            if not doc.exists():
                self.warn(f"{label}: enabled peer {peer_id!r} has no specific doc ({peer_id}.md)")
            else:
                content = doc.read_text(encoding="utf-8", errors="replace")
                if "SUSPENDED" in content.upper() and "ACTIVE" not in content.upper():
                    self.warn(f"{label}{peer_id}.md: enabled peer marked SUSPENDED in docs")
                self.info(f"{label}{peer_id}.md: exists")

        for peer_id in disabled_ids:
            doc = spec_dir / f"{peer_id}.md"
            if doc.exists():
                content = doc.read_text(encoding="utf-8", errors="replace")
                if "ACTIVE" in content and "SUSPENDED" not in content.upper():
                    self.warn(f"{label}{peer_id}.md: disabled peer says ACTIVE but not SUSPENDED")

    def _check_loop_bindings(self, disabled_ids: set):
        label = "collaboration_loop_bindings.json"
        data = _load("ai/collaboration_loop_bindings.json")
        if data is None:
            self.warn(f"{label}: file not found")
            return

        mp = _load("ai/model_profiles.json") or {}
        profiles = mp.get("profiles", {})

        violations = []
        for rule in data.get("routing_rules", []):
            task = rule.get("task_type", "?")
            for ref in rule.get("route", []) + [rule.get("final_reviewer", "")]:
                if not ref:
                    continue
                peer_prefix = ref.split(".")[0]
                if peer_prefix in disabled_ids:
                    violations.append(f"{task}: {ref} (disabled peer)")
                if ref in profiles and profiles[ref].get("routing_state") == "blocked":
                    violations.append(f"{task}: {ref} (routing_state=blocked)")

        if violations:
            for v in violations:
                self.error(f"{label}: disabled/blocked profile in route: {v}")
        else:
            self.info(f"{label}: no disabled profiles in routing_rules")

    def _report(self):
        print()
        if self.warnings:
            for w in self.warnings:
                print(w)
        if self.errors:
            for e in self.errors:
                print(e)
            print(f"\n{'='*60}")
            print(f"FAIL — {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        else:
            print(f"{'='*60}")
            print(f"PASS — 0 errors, {len(self.warnings)} warning(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--quiet", action="store_true", help="Only print errors")
    args = parser.parse_args()
    return Validator(strict=args.strict, quiet=args.quiet).run()


if __name__ == "__main__":
    sys.exit(main())
