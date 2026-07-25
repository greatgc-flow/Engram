#!/usr/bin/env python3
"""Peer lifecycle management — add, suspend, resume, remove, validate.

Reduces the 11-file blast radius to a single command. All JSON edits are
atomic (write-to-unique-temp, fsync, then rename) and idempotent.

Cluster C10 Items 4+5:
  - Operation-level registry locking (_sys/ai/.lock/peer_mgr.lock)
  - Unique same-directory temp files + flush/fsync + retry-on-PermissionError
  - Multi-file transaction journal & CAS (Compare-And-Swap) commit & auto-recovery

Usage:
  peer_mgr.py add <peer_id> --invoke <cmd> [--provider <id>] [--model <model_id>] [--dry-run]
  peer_mgr.py suspend <peer_id> [--reason <text>] [--dry-run]
  peer_mgr.py resume <peer_id> [--dry-run]
  peer_mgr.py remove <peer_id> [--dry-run]
  peer_mgr.py validate [--strict]
  peer_mgr.py status
  peer_mgr.py recover

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
import hashlib
import json
import os
import random
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

_SYS = Path(__file__).parent.parent
_AI = _SYS / "ai"
_LOCK_DIR = _AI / ".lock"
_TXN_DIR = _AI / ".peer_mgr_txn"

_ORCH = _AI / "orchestration.json"
_PEERS = _AI / "peers.json"
_PROTOCOL = _AI / "protocol.json"
_STATUS = _AI / "status_checks.json"
_SPECIFIC = _SYS / "docs-v2" / "specific"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ─── Concurrency & Locking (C10 Item 4) ──────────────────────────────────────

def _get_lock(timeout: float = 10.0):
    """Operation-level registry lock covering load-mutate-validate-save sequences.
    
    Self-contained implementation (Option b) avoiding heavy hub.py imports, while
    replicating hub.py's bounded retry pattern for Windows permission races.
    """
    have_filelock = True
    try:
        from filelock import FileLock
    except ImportError:
        have_filelock = False
        # Fallback if filelock is unavailable (standard library emergency fallback).
        # Uses O_EXCL for mutual exclusion, so it requires the lock file to NOT
        # already exist when a peer_mgr.py invocation starts -- unlike the real
        # FileLock, it is NOT existence-tolerant.
        class BasicFileLock:
            def __init__(self, lock_file: str, timeout: float = 10.0):
                self.lock_file = Path(lock_file)
                self.timeout = timeout
                self._fd = None

            def __enter__(self):
                self.lock_file.parent.mkdir(parents=True, exist_ok=True)
                start = time.monotonic()
                while True:
                    try:
                        self._fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                        return self
                    except OSError:
                        if time.monotonic() - start > self.timeout:
                            raise TimeoutError(f"Could not acquire lock {self.lock_file}")
                        time.sleep(0.05)

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except OSError:
                        pass
                    try:
                        self.lock_file.unlink()
                    except OSError:
                        pass
        FileLock = BasicFileLock

    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _LOCK_DIR / "peer_mgr.lock"

    if have_filelock:
        # Pre-create the lock file so the real FileLock's own open() doesn't hit
        # a transient Windows permission race on first creation (same class of
        # bug found and fixed in hub.py's _get_lock()/_write_json_atomic()
        # earlier this session) -- safe here because the real FileLock doesn't
        # care whether the file already exists.
        max_retries = 5
        for i in range(max_retries):
            try:
                fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
                os.close(fd)
                break
            except PermissionError as exc:
                if i == max_retries - 1:
                    raise PermissionError(
                        f"Cannot create or open registry lock file '{lock_path}'."
                    ) from exc
                time.sleep((0.02 * (2**i)) + (random.random() * 0.01))
    # else: BasicFileLock's O_EXCL requires the file to NOT already exist --
    # pre-creating it here would make every acquisition attempt fail with
    # FileExistsError until the 10s timeout, unconditionally (confirmed via
    # cross-verification: this exact pre-creation step, when unconditional,
    # made the fallback path permanently unusable regardless of contention).
    # BasicFileLock.__enter__() creates the file itself and unlinks it on
    # release, so no pre-creation is needed or wanted on this path.

    return FileLock(str(lock_path), timeout=timeout)


def _cleanup_temp_files(max_age_seconds: float = 300.0) -> int:
    """Remove abandoned *.tmp files in _sys/ai/ directory."""
    if not _AI.exists():
        return 0
    cleaned = 0
    now = time.time()
    for tmp_file in _AI.glob("*.tmp"):
        try:
            if now - tmp_file.stat().st_mtime > max_age_seconds:
                tmp_file.unlink()
                cleaned += 1
        except OSError:
            pass
    return cleaned


def _write_json_atomic(path: Path, data: Any) -> None:
    """Atomic write with unique temp file, flush+fsync, and Windows PermissionError retries."""
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f"{path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        max_retries = 5
        for i in range(max_retries):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError as exc:
                if i == max_retries - 1:
                    raise PermissionError(
                        f"Failed to replace target file '{path}' after {max_retries} retries."
                    ) from exc
                delay = (0.02 * (2**i)) + (random.random() * 0.01)
                time.sleep(delay)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: Any, dry_run: bool = False) -> None:
    if dry_run:
        print(f"  [DRY-RUN] would write {path.relative_to(_SYS)}")
        return
    _write_json_atomic(path, data)
    print(f"  wrote {path.relative_to(_SYS)}")


# ─── Multi-File Transactions (C10 Item 5) ───────────────────────────────────

class TransactionError(RuntimeError):
    """Raised when a multi-file transaction CAS check or commit fails."""
    pass


class PeerMgrTransaction:
    """Multi-file transaction with pre-commit CAS check, durable journal, and recovery."""

    def __init__(self, cmd_name: str, peer_id: str, dry_run: bool = False):
        self.cmd_name = cmd_name
        self.peer_id = peer_id
        self.dry_run = dry_run
        self.txn_id = f"txn_{uuid.uuid4().hex[:10]}"
        self.staged_writes: dict[Path, Any] = {}
        self.baselines: dict[Path, str] = {}

    def stage(self, path: Path, data: Any) -> None:
        """Stage a file write and record current target file sha256 baseline."""
        self.staged_writes[path] = data
        if path.exists():
            content = path.read_text(encoding="utf-8")
            self.baselines[path] = _sha256(content)
        else:
            self.baselines[path] = "ABSENT"

    def commit(self) -> None:
        """Execute pre-commit CAS validation, write transaction journal, commit, and mark complete."""
        if self.dry_run:
            for path, data in self.staged_writes.items():
                _save(path, data, dry_run=True)
            return

        if not self.staged_writes:
            return

        _TXN_DIR.mkdir(parents=True, exist_ok=True)
        journal_path = _TXN_DIR / f"{self.txn_id}.json"

        # 1. Prepare journal payload
        targets_info = {}
        for path, data in self.staged_writes.items():
            rel_str = str(path.relative_to(_SYS))
            staged_content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            targets_info[rel_str] = {
                "baseline_sha256": self.baselines[path],
                "staged_sha256": _sha256(staged_content),
                "staged_data": data,
            }

        journal_data = {
            "txn_id": self.txn_id,
            "cmd": self.cmd_name,
            "peer_id": self.peer_id,
            "status": "staged",
            "created_at": _now_iso(),
            "targets": targets_info,
        }

        # 2. Write durable transaction journal
        _write_json_atomic(journal_path, journal_data)

        # 3. CAS Check: Verify all baseline sha256 digests before writing anything
        for path in self.staged_writes.keys():
            if path.exists():
                curr_sha = _sha256(path.read_text(encoding="utf-8"))
            else:
                curr_sha = "ABSENT"

            if curr_sha != self.baselines[path]:
                # CAS violation! Target file mutated externally during transaction staging.
                # Nothing was written -- there is no ambiguous on-disk state for a
                # future `recover` to resolve, so the journal is removed immediately
                # rather than left behind (a "rolled_back" status is never checked by
                # _check_and_recover_transactions(), which only handles "staged"/
                # "committing" -- leaving it would silently accumulate dead journal
                # files in _TXN_DIR forever).
                try:
                    journal_path.unlink()
                except OSError:
                    pass
                raise TransactionError(
                    f"CAS failure on target '{path.relative_to(_SYS)}': "
                    f"expected sha256 {self.baselines[path][:8]}, found {curr_sha[:8]}. "
                    "Transaction aborted without writing."
                )

        # 4. Update journal status to committing
        journal_data["status"] = "committing"
        _write_json_atomic(journal_path, journal_data)

        # 5. Commit all target files atomically
        for path, data in self.staged_writes.items():
            _save(path, data, dry_run=False)

        # 6. Mark journal committed and remove
        journal_data["status"] = "committed"
        _write_json_atomic(journal_path, journal_data)
        try:
            journal_path.unlink()
        except OSError:
            pass


def _check_and_recover_transactions() -> None:
    """Check for uncommitted transaction journals and attempt automatic deterministic recovery."""
    if not _TXN_DIR.exists():
        return
    journals = list(_TXN_DIR.glob("*.json"))
    if not journals:
        return

    for jpath in journals:
        try:
            jdata = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception:
            continue

        status = jdata.get("status")
        if status in ("staged", "committing"):
            txn_id = jdata.get("txn_id")
            cmd = jdata.get("cmd")
            peer_id = jdata.get("peer_id")
            targets = jdata.get("targets", {})
            print(f"[HUB:RECOVERY] Incomplete transaction found: {txn_id} (cmd={cmd}, peer={peer_id})")

            # Check if auto-recovery is possible (all baselines match current files)
            can_recover = True
            for rel_path_str, info in targets.items():
                target_path = _SYS / rel_path_str
                expected_sha = info.get("baseline_sha256")
                if target_path.exists():
                    curr_sha = _sha256(target_path.read_text(encoding="utf-8"))
                else:
                    curr_sha = "ABSENT"

                # If already matches staged content, file was already committed before crash
                staged_sha = info.get("staged_sha256")
                if curr_sha != expected_sha and curr_sha != staged_sha:
                    can_recover = False
                    break

            if can_recover:
                print(f"[HUB:RECOVERY] Completing interrupted transaction {txn_id}...")
                for rel_path_str, info in targets.items():
                    target_path = _SYS / rel_path_str
                    _write_json_atomic(target_path, info["staged_data"])
                    print(f"  [RECOVERY] wrote {rel_path_str}")
                jdata["status"] = "committed"
                _write_json_atomic(jpath, jdata)
                try:
                    jpath.unlink()
                except OSError:
                    pass
                print(f"[HUB:RECOVERY] Transaction {txn_id} auto-recovered successfully.")
            else:
                print(f"[HUB:ERROR] Interrupted transaction {txn_id} cannot auto-recover due to baseline drift.", file=sys.stderr)
                print(f"[HUB:ERROR] Please inspect {_TXN_DIR} or run 'peer_mgr.py recover --force'", file=sys.stderr)
                raise TransactionError(f"Incomplete transaction {txn_id} blocking execution.")


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


# ─── Commands (Transaction Protected) ─────────────────────────────────────────

def cmd_suspend(peer_id: str, reason: str, dry_run: bool) -> int:
    print(f"Suspending peer: {peer_id}")

    with _get_lock():
        _cleanup_temp_files()
        _check_and_recover_transactions()
        txn = PeerMgrTransaction("suspend", peer_id, dry_run=dry_run)

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

        changed = _orch_set_enabled(nodes, peer_id, False)
        if changed:
            print(f"  orchestration.json: {peer_id}.enabled = false")
        else:
            print(f"  orchestration.json: {peer_id} already disabled")
        _set_governance_membership(orch, peer_id, False)
        txn.stage(_ORCH, orch)

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
            txn.stage(_PEERS, peers_data)

        # protocol.json — remove from voters
        proto = _load(_PROTOCOL)
        if proto:
            _set_governance_membership(proto, peer_id, False)
            print(f"  protocol.json: {peer_id!r} moved to inactive voters")
            txn.stage(_PROTOCOL, proto)

        txn.commit()

    print(f"\nDone. {peer_id} suspended.")
    if reason:
        print(f"Reason: {reason}")
    return 0


def cmd_resume(peer_id: str, dry_run: bool) -> int:
    print(f"Resuming peer: {peer_id}")

    with _get_lock():
        _cleanup_temp_files()
        _check_and_recover_transactions()
        txn = PeerMgrTransaction("resume", peer_id, dry_run=dry_run)

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

        node.pop("enabled", None)  # remove enabled:false → defaults to true
        print(f"  orchestration.json: {peer_id}.enabled = true (flag removed)")
        _set_governance_membership(orch, peer_id, True)
        txn.stage(_ORCH, orch)

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
            txn.stage(_PEERS, peers_data)

        proto = _load(_PROTOCOL)
        if proto:
            _set_governance_membership(proto, peer_id, True)
            print(f"  protocol.json: {peer_id!r} restored to active voters")
            txn.stage(_PROTOCOL, proto)

        txn.commit()

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

    with _get_lock():
        _cleanup_temp_files()
        _check_and_recover_transactions()
        txn = PeerMgrTransaction("add", peer_id, dry_run=dry_run)

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
        txn.stage(_ORCH, orch)

        provider_cfg = peers_data["peers"][provider_id]
        provider_cfg["enabled"] = True
        _set_list_membership(provider_cfg.setdefault("node_ids", []), peer_id, True)
        txn.stage(_PEERS, peers_data)

        proto = _load(_PROTOCOL)
        if proto:
            _set_governance_membership(proto, peer_id, True)
            txn.stage(_PROTOCOL, proto)

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
        txn.stage(_STATUS, status)
        _write_specific_doc(peer_id, provider_id, invoke, dry_run)

        txn.commit()

    print(f"\nDone. {peer_id} added.")
    print("Next: run peer_mgr.py validate --strict")
    return 0


def cmd_remove(peer_id: str, dry_run: bool) -> int:
    """Remove a peer entirely. Peer must be suspended first."""
    print(f"Removing peer: {peer_id}")

    with _get_lock():
        _cleanup_temp_files()
        _check_and_recover_transactions()
        txn = PeerMgrTransaction("remove", peer_id, dry_run=dry_run)

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
        txn.stage(_ORCH, orch)

        peers_data = _load(_PEERS)
        if peers_data:
            for provider in peers_data.get("peers", {}).values():
                node_ids = provider.get("node_ids")
                if isinstance(node_ids, list):
                    _set_list_membership(node_ids, peer_id, False)
            txn.stage(_PEERS, peers_data)

        proto = _load(_PROTOCOL)
        if proto:
            _remove_governance_membership(proto, peer_id)
            txn.stage(_PROTOCOL, proto)

        status = _load(_STATUS)
        if status and peer_id in status.get("peers", {}):
            status["peers"].pop(peer_id, None)
            txn.stage(_STATUS, status)

        doc = _SPECIFIC / f"{peer_id}.md"
        if doc.exists():
            archive = _SYS / "docs" / "history" / f"specific-{peer_id}.md"
            if dry_run:
                print(f"  [DRY-RUN] would archive {doc.relative_to(_SYS)}")
            else:
                archive.parent.mkdir(parents=True, exist_ok=True)
                os.replace(doc, archive)
                print(f"  archived {doc.relative_to(_SYS)}")

        txn.commit()

    print(f"\nDone. {peer_id} removed from logical runtime configuration.")
    print("Run validator to locate domain-specific references, if any.")
    return 0


def cmd_recover(force: bool = False) -> int:
    """Explicit transaction recovery command."""
    with _get_lock():
        _cleanup_temp_files()
        if not _TXN_DIR.exists() or not list(_TXN_DIR.glob("*.json")):
            print("No pending or incomplete transaction journals found.")
            return 0
        try:
            _check_and_recover_transactions()
            print("Recovery check complete.")
            return 0
        except Exception as exc:
            if force:
                print(f"[HUB:RECOVERY] Force cleaning transaction journals due to: {exc}")
                for jfile in _TXN_DIR.glob("*.json"):
                    jfile.unlink()
                print("All transaction journals cleared.")
                return 0
            print(f"[ERROR] Recovery failed: {exc}", file=sys.stderr)
            return 1


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

    p_rec = sub.add_parser("recover", help="Recover or clean incomplete transactions")
    p_rec.add_argument("--force", action="store_true", help="Force clear blocking journals")

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
    if args.cmd == "recover":
        return cmd_recover(args.force)
    if args.cmd == "validate":
        return cmd_validate(args.strict)
    if args.cmd == "status":
        return cmd_status()
    return 1


if __name__ == "__main__":
    sys.exit(main())
