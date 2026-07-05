# Terminal Command Contract (Canonical Reads)

Terminal reads raw `_sys/` state files ONLY when the task is explicitly "audit raw state" or the canonical command is missing/broken, and must say so.

- **Peer status**: `hub.py peer-status`
- **Room/session**: `hub.py status`
- **Routability**: `hub.py health-precheck --peer <id>`
- **Models**: `hub.py model-status`
- **Parity**: `hub.py profile-validate`
- **Leases/locks/tasks/roles**: `hub.py lease-status`, `hub.py lock-status`, `hub.py task-status`, `hub.py role-status`

---

# Shared Peer Invariants

These apply to every peer (cc, ag, cx). Peer-specific deltas live in `_sys/docs-v2/specific/{peer}.md`; full policy is in `_sys/docs-v2/` (SSOT).

- **Peer equality:** all peers are governance-equal; any peer may communicate directly with the human. No fixed coordinator (`protocol.json["workload"]["user_communication"]`).
- **IPC is English-only.** Query files: `_sys/ai/ipc/{peer_id}-{YYYYMMDDHHMMSS}-{rand4}.txt`; invoke via `hub.py ask --to {peer} --query-file ...`.
- **Session start:** read SSOT pointers only on a fresh interactive session. **IPC/sub-agent asks SKIP startup** — answer the USER QUERY directly, do not re-orient to the repo mission.
- **Health self-report:** `hub.py health-update --peer {id} --status GREEN|YELLOW|RED` at start/end. Never edit `health.json` directly.

## Hub Ask Timeout

- **Do NOT pass a hard `--timeout` to `hub.py ask` for normal collaboration.** Every peer is configured `timeout: 0` (orchestration.json); the hub's heartbeat + zombie guard governs liveness (`protocol.json["communication_policy"]`).
- `--timeout N` is a **hard wall-clock cap** that kills the peer *even while it is actively producing output* — it is NOT a silence/idle timeout. Use it only for a deliberately bounded probe.
- If you must cap, set `N >= runtime.ask_default_timeout_sec` (180) and **never below the target profile's `zombie_timeout_sec`**: `standard`/`effort` = 600s, `deepthink` = 900s (SSOT: `protocol.json` zombie_profile_map; was 7200s, which let a stalled deepthink hang ~2h). A 120s cap prematurely kills deepthink replies (observed ~115s latency).
