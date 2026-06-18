"""hub_health.py — Lightweight health state reader (Phase 4).

Provides a simple, typed API over the health.json files maintained by hub.py.
Does NOT duplicate hub.py's write logic — reads only.

Usage:
    from hub_health import HealthReader
    r = HealthReader()
    state = r.get_peer_state("gc")   # {"status": "GREEN", "gate": "open", ...}
    summary = r.summary()             # all peers

For writes, continue using hub.py health-update / health-check commands.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_LIFECYCLE_PATH = _AI_DIR / "lifecycle_policy.json"
_PROTOCOL_PATH = _AI_DIR / "protocol.json"

# Health state definitions (mirrors lifecycle_policy.json)
_GATE_OPEN_STATUSES = {"GREEN", "YELLOW"}
_GATE_CLOSED_STATUSES = {"RED", "UNKNOWN"}


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _peer_dirs() -> dict[str, Path]:
    """Return {peer_id: sys_subdir} from lifecycle_policy.json or defaults."""
    policy = _load_json(_LIFECYCLE_PATH)
    node_map = policy.get("identity", {}).get("node_to_peer", {})
    result: dict[str, Path] = {}
    for node_id, peer_id in node_map.items():
        candidate = _SYS_DIR / peer_id
        if candidate.is_dir():
            result[peer_id] = candidate
    # Fallback: scan _sys/ for known peer dirs
    for peer_id in ("claude", "gemini", "codex", "antigravity"):
        if peer_id not in result:
            p = _SYS_DIR / peer_id
            if p.is_dir():
                result[peer_id] = p
    return result


class PeerHealthState:
    """Typed view of a single peer's health.json."""

    def __init__(self, peer_id: str, data: dict[str, Any]) -> None:
        self.peer_id = peer_id
        self._data = data

    @property
    def context_status(self) -> str:
        return self._data.get("context_health", {}).get("status", "UNKNOWN").upper()

    @property
    def gate_open(self) -> bool:
        return self.context_status in _GATE_OPEN_STATUSES

    @property
    def consecutive_failures(self) -> int:
        return int(self._data.get("session_health", {}).get("consecutive_failures", 0))

    @property
    def jsonl_mb(self) -> float:
        return float(self._data.get("context_health", {}).get("jsonl_mb", 0.0))

    @property
    def checked_at(self) -> str:
        return self._data.get("context_health", {}).get("checked_at", "never")

    @property
    def availability(self) -> dict:
        return self._data.get("availability", {})

    @property
    def entrypoint_ok(self) -> bool:
        return bool(self.availability.get("entrypoint_ok", True))

    @property
    def authenticated(self) -> bool:
        return bool(self.availability.get("authenticated", True))

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "context_status": self.context_status,
            "gate": "open" if self.gate_open else "closed",
            "jsonl_mb": self.jsonl_mb,
            "consecutive_failures": self.consecutive_failures,
            "entrypoint_ok": self.entrypoint_ok,
            "authenticated": self.authenticated,
            "checked_at": self.checked_at,
        }

    def __repr__(self) -> str:
        gate = "OPEN" if self.gate_open else "CLOSED"
        return f"<PeerHealthState {self.peer_id} {self.context_status} gate={gate}>"


class HealthReader:
    """Read-only health state reader for all known peers."""

    def __init__(self) -> None:
        self._peer_dirs = _peer_dirs()

    def get_peer_state(self, peer_id: str) -> PeerHealthState | None:
        """Return typed health state for a peer, or None if health.json not found."""
        peer_dir = self._peer_dirs.get(peer_id)
        if not peer_dir:
            # try direct path
            candidate = _SYS_DIR / peer_id
            if candidate.is_dir():
                peer_dir = candidate
        if not peer_dir:
            return None

        health_path = peer_dir / "health.json"
        data = _load_json(health_path)
        if not data:
            return PeerHealthState(peer_id, {})
        return PeerHealthState(peer_id, data)

    def all_states(self) -> dict[str, PeerHealthState]:
        """Return {peer_id: PeerHealthState} for all known peers."""
        result: dict[str, PeerHealthState] = {}
        for peer_id in self._peer_dirs:
            state = self.get_peer_state(peer_id)
            if state is not None:
                result[peer_id] = state
        return result

    def eligible_peers(self, require_green: bool = False) -> list[str]:
        """Return peer IDs with gate open (GREEN or YELLOW, unless require_green)."""
        result = []
        for peer_id, state in self.all_states().items():
            if require_green:
                if state.context_status == "GREEN" and state.entrypoint_ok:
                    result.append(peer_id)
            else:
                if state.gate_open and state.entrypoint_ok:
                    result.append(peer_id)
        return result

    def summary(self) -> dict[str, Any]:
        """Return summary dict for all peers (for display or self_care)."""
        states = self.all_states()
        return {
            "peers": {pid: s.to_dict() for pid, s in states.items()},
            "eligible": self.eligible_peers(),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="hub_health — peer health reader")
    parser.add_argument("--peer", default=None, help="Show state for specific peer")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    parser.add_argument("--eligible", action="store_true", help="List eligible peers only")
    args = parser.parse_args()

    reader = HealthReader()

    if args.eligible:
        peers = reader.eligible_peers()
        if args.json_out:
            print(_json.dumps({"eligible": peers}))
        else:
            print("Eligible peers:", " ".join(peers) or "(none)")
        return

    if args.peer:
        state = reader.get_peer_state(args.peer)
        if state is None:
            print(f"[ERROR] peer not found: {args.peer}")
            return
        if args.json_out:
            print(_json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        else:
            d = state.to_dict()
            print(f"Peer  : {d['peer_id']}")
            print(f"Status: {d['context_status']} (gate {d['gate']})")
            print(f"Size  : {d['jsonl_mb']:.2f} MB | Failures: {d['consecutive_failures']}")
            print(f"Auth  : {d['authenticated']} | Entry: {d['entrypoint_ok']}")
            print(f"Last  : {d['checked_at']}")
        return

    summary = reader.summary()
    if args.json_out:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"{'PEER':<14} {'STATUS':<8} {'GATE':<8} {'MB':>6}  FAILURES  AUTH")
        print("─" * 60)
        for pid, d in summary["peers"].items():
            print(f"{pid:<14} {d['context_status']:<8} {d['gate']:<8} "
                  f"{d['jsonl_mb']:>5.2f}  {d['consecutive_failures']:>8}  {d['authenticated']}")
        print(f"\nEligible: {', '.join(summary['eligible']) or '(none)'}")


if __name__ == "__main__":
    _main()
