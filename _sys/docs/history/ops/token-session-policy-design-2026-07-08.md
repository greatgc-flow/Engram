# Token + Session Policy & Diag MECE — 끝장토론 Design Record (2026-07-08)

Status: RATIFIED design (ag.deepthink + cx.deepthink unanimous, no dissent).
Owner: this doc (archive) + living updates in `docs-v2/ops/diag-telemetry-architecture.md`,
`routing.md`, `telemetry-config.json`, `protocol.json.session`.
Trigger: user request — leverage ag's large context in session-reuse; unify with
token load balancing; remove/JSON-ize all hardcoded policy constants; make diag
MECE with a policy/constants panel; add flicker-free `--watch` double-buffering.

---

## 1. Session-Reuse + Context Affinity

**Problem.** `hub._session_reuse_enabled` is purely capability-based
(`node.session_mode == "reuse"`); it ignores each peer's context advantage.
ag's ~1M-token window (vs cc 200k/1M, cx 258k) sits mostly free and unused.

**Decision.** Introduce a single measured signal, **context_affinity =
`window_tokens * ctx_remaining`** — identical to the `abs_headroom` already
computed for routing bias (§ token-load-balancing). One signal feeds BOTH:

- **AUTO routing** (already shipped): `headroom_bias = sqrt(abs_headroom/mean)`
  already steers context share toward ag. Context-heavy asks additionally get a
  bounded affinity lift (see `context_affinity` config below).
- **Session-reuse tie-break** (new): when >1 eligible reuse-capable peer could
  serve a context-heavy / multi-turn accumulation task, prefer the peer with the
  largest **absolute free headroom**.

**Anti-pinning hysteresis (cx).** Keep an existing session unless a challenger
has `>= switch_ratio` (default **2.0**) times the incumbent's absolute free
headroom, OR the incumbent is stale / within `effective_headroom_floor`.
Prevents oscillation and permanent pinning of long chains to one peer
(staleness, cache, failover risk).

**Context-heavy detection.** A task is context-heavy when payload/query size or
multi-turn history exceeds `context_affinity.heavy_task_tokens` (config). Only
then does affinity override the cheap-peer default — shallow tasks stay on the
normal headroom+cost path.

Config (routing-config.json.token_load_balancing):
```
"context_affinity": {
  "enabled": true,
  "heavy_task_tokens": 32000,     // task size above which affinity applies
  "switch_ratio": 2.0,            // hysteresis: challenger must have 2x abs headroom
  "max_lift": 1.5                 // bounded affinity multiplier (safety rail)
}
```

---

## 2. Constants → JSON (MECE by ownership)

Rule: **only vendor facts and mathematical invariants stay in code**; every
operational knob moves to config with a default + schema + diag provenance.

| Constant (current) | Value | Home |
|---|---|---|
| `SNAPSHOT_TTL_SEC` | 60 | **telemetry-config.json** `ttl.snapshot_sec` |
| `EXPENSIVE_SOURCE_TTL_SEC` | 60 | telemetry-config `ttl.expensive_source_sec` |
| `_LOCAL_TTL_SEC` | 5 | telemetry-config `ttl.local_sec` |
| codex/claude probe `deadline_sec` | 12 | telemetry-config `probe.deadline_sec` |
| `QUOTA_WARN_FRAC` | 0.75 | telemetry-config `display.warn_frac` |
| `QUOTA_CRIT_FRAC` | 0.90 | telemetry-config `display.crit_frac` |
| watch `interval` default | 5 | telemetry-config `watch.default_interval_sec` |
| watch hard-min interval | 2 | telemetry-config `watch.min_interval_sec` |
| routing `eps` | 0.01 | routing-config `token_load_balancing.eps` |
| routing `floor` | 0.10 | routing-config `effective_headroom_floor` (already) |
| `headroom_bias.min/max` | 0.75/1.5 | routing-config (already) |
| session reuse/staleness knobs | — | **protocol.json.session** |
| `window_hours` 5 / 168 | — | **CODE** (vendor quota-window fact) |
| zero-division guards (`eps` math) | — | CODE |

**Enforcement (ag + cx).** Add a checks-framework guard **CHK-CONST**
(`check_policy_constants.py`): scans snapshot.py/diag.py/hub.py routing+telemetry
modules for raw magic numbers that should be config-sourced, and a **policy-drift**
assertion that every config default matches the documented table above. Fails the
pre-commit hook (like CHK-ENC). Every configurable value MUST load via a small
`telemetry_config()` loader with schema validation + defaults, so a missing/typo'd
key degrades to the documented default rather than crashing.

---

## 3. diag MECE Panels

Correct MECE decomposition — "what is happening" strictly separated from "why":

1. **HUB** — identity, room, active coordinator, mailbox.
2. **PROFILES & ROUTING** — topology + route eligibility (declared vs live).
3. **SESSIONS & HEADROOM** — session state + usable/absolute context per peer.
4. **SUMMARY** — quota / pacing / reset (nearest-prompt).
5. **ALERTS** — failures / drift / staleness.
6. **POLICY** *(new)* — effective operational knobs + their config source path,
   e.g. `crit_frac 0.90  <- telemetry-config.json:display.crit_frac`. Operational
   knobs ONLY (no full config dump). Makes every live threshold traceable and is
   the human-readable face of the CHK-CONST provenance map.

---

## 4. `--watch` Double-Buffering (flicker-free, no scroll)

Current: `\033[2J\033[H` full clear+home every frame → flicker.

**Decision (ag + cx).** No alt-screen (preserves scrollback). Per frame:
1. `\033[?2026h` — begin synchronized update (Bap; **feature-probed / opt-in**,
   never assumed — Windows conhost may not support it; safe no-op when ignored).
2. `\033[H` — cursor home (no clear).
3. write each line followed by `\033[K` (erase to end-of-line) — overwrites in place.
4. `\033[J` — erase from cursor to end-of-screen (handles a shorter new frame).
5. `\033[?2026l` — end synchronized update.

**Gating.** TTY only (`stdout.isatty()`); non-TTY / `--json` / dumb terminal →
plain frame output (existing behavior), no ANSI. Synchronized-output support is
probed once (env/terminfo) and cached; when absent, steps 2-4 alone already remove
the `\033[2J` flash. `Ctrl+C` restores cursor + exits 130 (existing contract).

Config: telemetry-config `watch.sync_output: "auto|on|off"` (auto = probe).

---

## 5. Rollout order

1. `telemetry-config.json` + loader + wire the 8 telemetry/display constants (§2).
2. `--watch` double-buffer (§4) — self-contained, immediate UX win.
3. diag POLICY panel (§3) + provenance map.
4. `context_affinity` routing + session-reuse hysteresis (§1).
5. CHK-CONST guard + policy-drift test (§2 enforcement).

Each increment: tests + pre-commit green + diag renders.
