# B1 / H-3 — Per-Profile Health (DESIGN, deferred implementation)

> **Date:** 2026-06-25 · **Status:** DESIGN ONLY — banked for a future focused session. NOT implemented.
> **Roadmap (2026-06-26):** this design is the spec for slice **AT-3** of the Ask Transaction primitive — see `ops/backlog-5whys-consensus-2026-06-26.md`. It is IMPLEMENTED by AT-3, not replaced.
> **Authors:** ag.deepthink (design) + terminal (framing). cc review pending.
> **Why deferred:** a cohesive architectural change to the health core that was just hardened (E1 read-purity, keystone gate-OPEN snapshot). Implementing it at the tail of a very long session risks subtle regression in health/consensus. Implement with fresh focus + cc review.

## Problem (audit H-3 / B1)
Health is tracked PER-PEER only (`cc`/`ag`/`cx` in `health.json`), not per-profile. If `cc.deepthink` hits a rate-limit, the whole peer's gate closes (`gate_open=False`) and `cc.standard` / `cc.effort` are blocked too. `resource-governance.md` promises "same-peer downward fallback for blocked profiles", but `hub_profile_router._eligible_profile` only walks down on CONFIG state (orchestration `routing_state`/`enabled`), not runtime health — and the root health gate-close in `_ask_health_precheck` drops the whole peer before fallback can help.

## Design (implementable)

### 1. State model
Nest per-profile health under each peer's `availability` in `health.json`; keep root-level fields for peer-wide signals (auth, installed, CLI):
```json
"availability": {
  "gate_open": true,
  "profiles": {
    "deepthink": {"gate_open": false, "consecutive_failures": 3, "cooldown_until": "16:45", "rate_limit_state": {"limited": true}},
    "effort":    {"gate_open": true,  "consecutive_failures": 0},
    "standard":  {"gate_open": true,  "consecutive_failures": 0}
  }
}
```

### 2. Write path
`_record_ask_failure`/`_record_ask_success` gain a `profile_key` param (the ask knows the resolved profile/node_id). PROFILE-scoped failures update `availability.profiles[profile_key]` and may close only that profile's gate; PEER-WIDE failures update root and close `gate_open` (overrides all profiles). Success clears BOTH the profile and the root counters.

### 3. Read / gate path
`_eligible_profile(peer, requested_profile, health)` walks down `deepthink -> effort -> standard`, checking BOTH config (`routing_state==enabled`) AND runtime health (`profiles[candidate].gate_open != false`); returns the first eligible. `_ask_health_precheck` uses it: pass if a fallback profile is eligible, fail only if all exhausted. This makes config-blocked AND health-blocked both cascade down within the same peer.

### 4. Peer-wide vs profile-scoped
- **Peer-wide** (close root gate): auth/token errors, CLI missing/unreachable, fatal crash (exit 127), workspace/disk I/O errors.
- **Profile-scoped** (close only that profile): rate-limits (429), tier-specific quota exhaustion, model-specific 503/timeout.

### 5. Consensus impact
A voter is a PEER. A peer is available to vote iff `root.gate_open AND` at least one configured profile has `gate_open==true`. `_healthy_peer` aggregates this to a single boolean per peer — **no structural change to the keystone snapshot** (which votes peers `cc`/`ag`/`cx`).

### 6. Migration + safety
Backward-compat: missing `profiles` -> `{}` -> default to root health (a profile with no key is treated healthy, relying on root). No regression to keystone snapshot, E1 read-purity, or PRO-19. Deploy state + read + write together (avoid router/state desync) — but a phased "observe-only per-profile state, then wire fallback" split is possible.

### 7. Test plan
- `test_health_downward_fallback`: rate-limit `cc.deepthink` -> `ask cc.deepthink` auto-serves via `cc.effort`.
- `test_peer_wide_drops_all`: auth failure -> `_eligible_profile` returns None for all.
- `test_healthy_peer_aggregation`: `_healthy_peer("cc")` True when `deepthink` closed but `effort` open.

### Risk
**Silent degradation:** a `deepthink`->`effort` health fallback returns a lower-tier answer without the user realizing. Mitigation: `_eligible_profile`/the ask must SURFACE/log the fallback (e.g. `[HUB:FALLBACK] cc.deepthink rate-limited -> served by cc.effort`).

## Related deferred follow-ups (see also the consistency audit + memory)
- **Robust cleanup on ask termination** (the zombie/lock gap): a force-killed hung ask leaves (a) a stale `_sys/ai/.lock` mkdir-lock, (b) the peer marked RED (needs manual `peer-recover`), (c) orphan agy/node children. Lease-sweep should reclaim stale locks by owner-PID liveness; a terminal-initiated kill should not permanently RED the peer; the kill should reap the process tree.
- **Timeout reliability:** `--timeout` is in SECONDS; ms-scale values (e.g. 600000) become effectively infinite, and post-H-2 (ag unbounded) the only net is the 7200s zombie. Add unit validation / a sane cap, and fix the `CLAUDE.md` "timeout 180000" doc drift (PRO-12 — needs consensus).
