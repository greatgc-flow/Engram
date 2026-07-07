# Status Consolidation — Pending, Backlog, MECE, Freshness (2026-07-08)

Single reconciliation point for the 2026-07-07/08 work stream. Living companion
to the archived design record `_sys/docs/history/ops/token-session-policy-design-2026-07-08.md`.

## 1. Shipped this stream (main, ahead of origin — push pending)

| Commit | What |
|---|---|
| b1a3caf | terminal tier-floor + CHK-ENC mojibake guard + ag.opus profile bulk-exclusion |
| 714f776 | find_ai_root phantom-.ai fix (ag vote bug) |
| b18184b | cx quota pacing key + peer_weight_bias |
| 87daec0 | derived headroom bias (dropped magic 1.5) |
| 04f1300 | telemetry-config.json + --watch double-buffer + POLICY panel |
| a25b34a | context_affinity heavy-task steering + hysteresis helper |
| 81d3f18 | CHK-CONST no-hardcoding guard |
| fd40da3 | session-reuse hysteresis wired into --to auto |
| (this)  | diag freshness: quota-age transparency + `--fresh` |

## 2. Pending / backlog (reconciled)

- **PUSH BLOCKED**: main is ahead of origin; auto-mode denies default-branch push.
  Action: human runs `! git push origin main` or adds a push permission rule.
- **ag "use both quota families" (D3)** + **pacing→routing weights (D5)**:
  DEFERRED by prior consensus (diag-telemetry-architecture.md §14.1, §D-table).
  context_affinity/headroom_bias now cover the *routing* side by absolute headroom;
  the ag dynamic-model-arg enablement stays deferred.
- **should_switch_session_peer scope**: wired into `--to auto` peer *selection*;
  `_session_reuse_enabled` remains capability-based (reuse vs fresh) by design.
- **Master backlog SSOT** remains `_sys/docs/history/ops/` banked items; nothing
  from this stream regresses them. See memory [[backlog_reorg_2026_07_04]].

## 3. MECE review — docs ↔ source ↔ config ↔ guidance

Gap found: living `docs-v2/` did not reference the shipped artifacts (they lived
only in the archive design doc). Closed by adding pointers:

| Artifact | Config home | Living doc ref |
|---|---|---|
| headroom_bias, context_affinity, bulk_exclude_profiles, peer_weight_bias | routing-config.json:token_load_balancing | `general/routing.md` |
| telemetry constants (TTL/deadline/display/watch) | telemetry-config.json | `ops/diag-telemetry-architecture.md` §6.6 |
| POLICY panel, --watch double-buffer, --fresh, quota-age | (diag.py) | `ops/diag-telemetry-architecture.md` §6.3.1/§6.6 |
| CHK-ENC, CHK-CONST | _sys/checks + pre-commit | `10-invariants.md` (PRO-19 / DIR-004) |

Enforcement of "no magic numbers" is mechanical (CHK-CONST in pre-commit), so
config↔code stays MECE going forward.

## 4. diag/CLI E2E freshness (why it "doesn't update immediately")

Root cause (NOT a bug): `collect_snapshot(use_cache=False)` re-collects every diag
run, but the **expensive** sources (claude `/usage`, codex rate-limits) are
in-process cached for `EXPENSIVE_SOURCE_TTL_SEC` (60s) because probing them every
frame risks subprocess hang. So under `--watch` (5s redraw) quota/pacing only
change every ≤60s. Peer-owned telemetry (ag_stdin.log, cx sqlite) refreshes only
when that peer next renders/acts.

Decision (ag+cx unanimous): **transparency, not hammering.**
- diag POLICY panel shows `quota probe age: cached Ns ago (TTL 60s; --fresh to bypass)`.
- `diag --fresh` forces one cache bypass for manual verification.
- TTL stays 60s (config `telemetry-config.json:ttl.expensive_source_sec`).
- Existing `SOURCE_STALE` ALERTS still flag peer sources older than local TTL.
