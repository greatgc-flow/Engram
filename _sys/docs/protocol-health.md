# Protocol: Health Management (v4.1)
> Source: `_sys/ai/protocol.json["health"]` | Part of composable PROTOCOL.md

## 1. Zero-Token Principle

All health data is stored in local files. No API calls for status checks.
Read `_sys/{peer_sys_subdir}/health.json` directly — no tokens consumed.

## 2. Health File Location

`P:\_sys\{sys_subdir}\health.json` (sys_subdir from `peers.json`)

| Peer | Path |
|------|------|
| cc/ca | `_sys\claude\health.json` |
| gc | `_sys\gemini\health.json` |
| ag | `_sys\antigravity\health.json` |
| cx | `_sys\codex\health.json` |

## 3. Health Status Thresholds

Thresholds from `protocol.json["health"]["thresholds"]`:

| Status | Condition |
|--------|-----------|
| GREEN | jsonl_mb < 0.6 AND consecutive_failures < 3 |
| YELLOW | 0.6 <= jsonl_mb < 1.2 OR failures >= 3 |
| RED | jsonl_mb >= 1.2 OR failures >= 5 OR gate_open=false |

## 4. Self-Report Contract

Entry points MUST call at session start and end:
```
hub.py health-update --peer {peer_id} --status GREEN --jsonl-mb {mb} --failures {n}
```

Peer-specific extra metrics written directly to health.json:
- **ag**: `model_latency_ms`, `session_token_count`, `quota_limit_remaining`, `active_background_tasks_count`
- **cc/ca**: `context_window_usage_percent`
- **cx**: `cli_version`, `entrypoint_ok`, `last_invocation_exit_code`, `rate_limit_state`, `workspace_access`

## 5. Hub Commands

```
hub.py health-check [--peer {id}]    # one or all peers health summary
hub.py peer-status                   # gate + health unified table
```

## 6. Routing Gate Rule

Coordinator MUST NOT assign tasks to peer with `status: RED`.
If all peers are RED → escalate to Human (Tier 0).
Check before delegation: `context_health.status != "RED"` AND `availability.gate_open == true`

## §HISTORY
- v4.1 (2026-06-12): Standardized zero-token health check thresholds.
- v4.0 (2026-06-11): New file; health management system designed with all peers (cc,gc,ag,cx)
