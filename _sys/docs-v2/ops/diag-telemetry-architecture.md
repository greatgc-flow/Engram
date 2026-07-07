# Ops - Diag Telemetry Architecture
> Status: implemented (slices 1-5 complete) | Created: 2026-06-30 | Updated: 2026-07-01 | Purpose: MECE telemetry source map and presentation contract for expanding `diag` into a project monitoring dashboard.
> Cross-ref: `ops/logging.md`, `general/lifecycle.md`, `ops/schemas.md`, `_sys/ai/common/statusline/statusline-schema.json`.

---

## 1. Decision

Use a three-layer telemetry architecture:

```text
Specific collectors
  -> Generic telemetry normalization
  -> diag summary / detail views
```

`diag` must not become the source of truth. It is the user-facing renderer and warning surface. Peer-specific collectors own provider/runtime quirks. The generic layer owns field names, units, freshness, confidence, and redaction rules.

This is valuable because context pressure, quota pressure, session risk, account status, token burn history, and routing safety all need the same normalized vocabulary while still preserving provider-specific truth.

---

## 1.1 Peer Review Summary

Review inputs gathered on 2026-06-30:

| Reviewer | Verdict | Key Points |
|----------|---------|------------|
| ag.deepthink | Support with cautions | The pattern enables unified routing, proactive context warnings, cost/quota visibility, and adapter decoupling. Main risks are PTY scraping brittleness, estimation drift, and losing provider-specific semantics in an overly generic schema. |
| cx.standard | Support with cautions | Worthwhile if `diag` becomes a stable summary over normalized telemetry. Main risks are false equivalence, stale cached numbers, and clutter from raw profile fields. Requires source/timestamp/TTL discipline. |
| cc synthesis | Proceed to TDD planning | Keep Specific collectors lossless and thin; make Generic telemetry explicit about freshness/confidence; keep `diag` compact by default with drill-down commands for raw/detail views. |

Consensus: implement the architecture only if the generic layer does not erase source semantics. `diag` should summarize, not reinterpret unknown or estimated values as exact values.

Final refresh/watch consensus gathered on 2026-06-30: `cc.deepthink`, `ag.deepthink`, and `cx.deepthink` all returned `AGREEMENT` for the watch contract in section 6.4.

---

## 2. Source Inventory

### 2.1 Runtime Status Sources

| Source | Layer | Current Probe Result | Data Class | Notes |
|--------|-------|----------------------|------------|-------|
| `_sys/claude/config/status_input.log` | Specific: cc live statusline | present | live | model, context window, current usage, rate limits, cost, session id |
| `_sys/cli/ag_stdin.log` | Specific: ag live statusline | present | live | model, context window, quotas, plan tier, product, email, agent state |
| `_sys/codex/config/state_5.sqlite` | Specific: cx local app state | present | live-ish / local snapshot | thread model, reasoning effort, cumulative tokens; not current context occupancy |
| Codex app-server `account/rateLimits/read` | Specific: cx app-server | callable by current `diag` | live | 5h/weekly rate limits; no local persistence |
| `_sys/{peer}/health.json` | Generic-ish health state | present for cc/ag/cx | cached / session state | gate, quarantine, auth, entrypoint, profile, session counters |
| `.ai/state.json` | Hub runtime state | present | live hub state | room, phase, mission, leader, members |
| `.ai/mailbox.json` | Hub runtime state | present | live hub state | unread count and messages |
| `.ai/leases.json` | Hub runtime state | present | live hub state | active lease records for root and generated profile nodes |

### 2.2 Configuration And Fact Sources

| Source | Layer | Data Class | Notes |
|--------|-------|------------|-------|
| `_sys/ai/orchestration.json` | Generic config | cached fact | peer tree, profile definitions, model ids, runtime context windows, routing state |
| `_sys/ai/model-registry.json` | Generic fact registry | cached fact | vendor documented model facts, context limits, output limits, pricing |
| `_sys/ai/routing-config.json` | Generic policy | cached fact | automatic profile routing signals and weights |
| `_sys/ai/governance_params.json` | Generic policy | cached fact | ContextGate thresholds and token budget knobs |
| `_sys/ai/logging-config.json` | Generic schema/config | cached fact | log taxonomy and expected fields |
| `_sys/ai/common/statusline/statusline-schema.json` | Generic display schema | cached fact | current statusline field contract |

### 2.3 History Sources

| Source | Layer | Current Probe Result | Data Class | Notes |
|--------|-------|----------------------|------------|-------|
| `_sys/data/logs/cost-log.jsonl` | Generic history | present | snapshot / append-only | currently latency/success rich; token fields often null |
| `_sys/data/logs/ipc-log.jsonl` | Generic history | present | snapshot / append-only | send/receive preview history; may contain prompt text |
| `_sys/data/logs/error-log.jsonl` | Generic history | present | snapshot / append-only | error and rate-limit events |
| `_sys/claude/session_state.json` | Specific session state | present | runtime state | active/history session metadata |
| `_sys/codex/session_state.json` | Specific session state | present | runtime state | active/history session metadata |

---

## 3. MECE Telemetry Domains

Do not collapse these domains into one number.

| Domain | Meaning | Example Fields | Common Mistake |
|--------|---------|----------------|----------------|
| Context | Current or estimated prompt/session context occupancy | used, window, remaining, utilization | confusing cumulative tokens with current occupancy |
| Quota | Provider rate-limit windows | 5h used, weekly used, reset time | treating quota remaining as context remaining |
| Cost | Monetary or token-burn history | cost_usd, input/output/reasoning tokens | displaying null token fields as zero |
| Session | Runtime continuity and resume risk | session id, age, reuse mode, fingerprint drift | equating process liveness with healthy resumability |
| Account | Provider account metadata | masked account, plan, expiry, entitlements | showing raw email/account id/token |
| Profile | Static or cached generated profile facts | peer.profile, model, effort, cost tier, routing state | showing all profile internals in the main summary |
| Health/Gate | Operational eligibility | gate_open, quarantined, auth, entrypoint | inferring health from model prose |
| Project | Workspace state | git dirty, docs check, broker queue, consensus, locks | mixing project checks with peer quota |

---

## 4. Generic Telemetry Record

All normalized records must carry source metadata.

```jsonc
{
  "schema_version": 1,
  "peer": "cx",
  "profile": "cx.deepthink",
  "domain": "context",
  "source": {
    "kind": "live|cached|snapshot|estimated|unknown",
    "adapter": "codex",
    "path_or_endpoint": "_sys/codex/config/state_5.sqlite",
    "observed_at": "2026-06-30T21:50:00+09:00",
    "ttl_sec": 5,
    "confidence": "exact|estimated|last_known|unknown"
  },
  "context": {
    "window_tokens": 272000,
    "used_tokens": null,
    "remaining_tokens": null,
    "utilization_pct": null,
    "safe_working_limit_tokens": 217600,
    "basis": "provider_reported|local_estimate|history_only|unavailable"
  },
  "quota": {
    "period": "5h",
    "used_pct": 1,
    "reset_at": "2026-07-01T01:40:00+09:00"
  },
  "session": {
    "state": "active|idle|stale|unknown",
    "reuse_mode": "reuse|fresh|none|unknown",
    "resume_risk": "low|medium|high|unknown"
  },
  "alerts": [
    {
      "severity": "warn",
      "code": "CONTEXT_HIGH",
      "message": "context utilization over warning threshold"
    }
  ]
}
```

Rules:

1. `null` means unknown, not zero.
2. `exact`, `estimated`, `last_known`, and `unknown` must render differently.
3. Every volatile value needs `observed_at` and `ttl_sec`.
4. Provider-specific raw payloads stay in the Specific layer or a drill-down view.
5. Account identifiers must be redacted before entering the Generic layer unless the value is already a human-approved alias.

---

## 5. Account Data Contract

Current probe results:

| Peer | Available Now | Missing Now | Display Rule |
|------|---------------|-------------|--------------|
| ag | `product`, `plan_tier`, email in live status | expiry | show product/plan; mask email |
| cc | no account/plan field found in live status | account, plan, expiry | show `not available` |
| cx | app-server rate limits; sqlite table for remote control enrollment exists but no rows | plan, expiry, account alias | show quota; do not infer plan/expiry |

Display account metadata only in an Account card or `diag --accounts`. Never show raw tokens, session cookies, raw billing identifiers, or unmasked account ids.

---

## 6. User Presentation Contract

### 6.1 Default `diag`

Default view should be compact and action-oriented.

```text
PEER  PROFILE       GATE  CTX              QUOTA          SESSION  ALERT
CC    cc.standard   OPEN  106k/1M 11% L    7D 98% WARN    active   quota
AG    ag.standard   OPEN  58k/1M 6% L      3P7D 75% L     active   ok
CX    cx.standard   OPEN  ?/128k unknown   7D 3% L        active   ctx?
```

Legend:

- `L`: live
- `C`: cached
- `S`: snapshot
- `E`: estimated
- `?`: unknown

### 6.2 Detail Commands

| Command | Purpose |
|---------|---------|
| `diag --json` | normalized telemetry JSON for automation |
| `diag --profiles` | all generated profile states as a matrix |
| `diag --accounts` | redacted account/plan/expiry capability view |
| `diag --tokens` | context/quota/cost/token history view |
| `diag --sessions` | session reuse, active ids, resume risk |
| `diag --project` | git/docs/tests/broker/consensus/locks status |
| `diag --watch [seconds]` | human dashboard refresh; default 5s, minimum 2s |
| `diag --interval <seconds>` | explicit refresh interval alias; same limits as `--watch` |
| `diag --json --watch` | NDJSON telemetry stream; no ANSI, no terminal clearing |

### 6.3 Profile Matrix

```text
PEER  standard                  effort                    deepthink
cc    OK haiku low 200k C       OK sonnet high 200k C      OK opus high 1M C
ag    OK flash low 1M L         OK flash high ? C          OK pro high ? C
cx    OK gpt-5.4-mini low 272k C OK gpt-5.5 high 272k C    OK gpt-5.5 xhigh 272k C
```

The default row shows only status, model, effort, context, and freshness. Full `profile_args`, validation method, and adapter flags belong in drill-down.

#### 6.3.1 Quota-family coverage & "why is there no quota row?" (2026-07-07)

A profile's SUMMARY quota rows are filtered by its quota family (`snapshot._quota_family_for_profile`): `cc.fable`→`F-`, other `cc`→`C-`, `ag.{opus,gptoss,sonnet}`→`3P-`, other `ag`→`G-`, `cx`→`X-`. A profile shows **no** quota row when no bucket of its family was captured. This is expected, not a bug, in two cases:

- **`cc.fable`** (claude-fable-5, arbiter-only): fable HAS a dedicated weekly bucket `F-7D`, sourced from `claude /usage` (section **"current week (fable)"** → `_CLAUDE_USAGE_SECTIONS`, `snapshot.py`), NOT from the statusline (which only emits `five_hour`/`seven_day`). The catch: `/usage` only lists "current week (fable)" **once the account has fable usage in the current week**. If fable has been idle all week the section is absent, so `F-7D` correctly does not render — it reappears after the next fable invocation (verified 2026-07-07). `F-5H` is not exposed (fable has no separate 5-hour pool; short-term fable calls draw on `C-5H`). Do not fabricate an `F-7D` row when absent — its absence means "no fable usage this week", which is real information.
- **`ag.opus` / `ag.gptoss`** (3P family) when ag is idle/quarantined: ag only emits a `context_window`-only init frame with no `quota` block, so `3P-*` rows are absent until ag processes a real turn (which makes antigravity render a full quota-bearing frame). See §11.2.

### 6.4 Watch / Refresh Contract

Final peer consensus (`cc.deepthink`, `ag.deepthink`, `cx.deepthink`) uses this contract:

- `diag --watch` defaults to 5 seconds.
- The hard minimum interval is 2 seconds; lower requested values are rejected with a non-zero exit code and a clear error message.
- Cheap local file reads may refresh every frame.
- Local health/config/sqlite reads use a 5 second TTL by default.
- Expensive subprocess/API checks, including Codex app-server rate-limit reads, use a 60 second TTL by default and are never polled faster than the active watch interval.
- Expensive refreshes run in the background; the renderer uses the last complete snapshot and marks stale values instead of blocking a frame.
- Human watch mode uses a TTY-gated alternate-screen/clear-screen renderer. Output to non-TTY pipes must not contain ANSI control sequences.
- `diag --json` emits one normalized JSON object and exits.
- `diag --json --watch` emits newline-delimited JSON snapshots and no ANSI control sequences.
- `Ctrl+C` restores the terminal and exits with code 130.

### 6.5 Reset Time And Instruction Sources

- Human quota rows show reset time as local absolute time with timezone plus a relative countdown, for example `resets 2026-07-01 01:40 KST (in 3h21m)`.
- JSON rows preserve machine fields separately: `reset_at` as ISO-8601 with offset, `reset_in_seconds`, `window`, `used_pct`, and `remaining_pct`.
- Relative countdown is recomputed from the raw reset timestamp every render; do not cache rendered text.
- If only relative reset text is available from a provider UI, mark the value as `estimated` and include the source timestamp.
- Peer initial instruction files are provenance, not main summary content. Show path, exists/missing, modified time, size, and optional hash in detail/profile views.
- Never inline instruction file contents or raw account identifiers in the default dashboard.

### 6.6 Constants, POLICY panel & freshness (2026-07-08)

- **Constants are config, not code** (design 2026-07-08 §2 / DIR-004): TTLs, probe
  deadline, `warn/crit` display thresholds and watch interval live in
  `_sys/ai/telemetry-config.json`, loaded via `snapshot.telemetry_config()` (defaults
  on missing/typo). Vendor facts (`window_hours` 5/168) stay in code. Enforced by
  `check_policy_constants.py` (CHK-CONST) in pre-commit.
- **POLICY panel**: the default dashboard ends with a POLICY panel mapping each live
  operational knob to its config source path — operational knobs only, not a full dump.
- **`--watch` double-buffering**: no alt-screen (scrollback preserved); frame built
  off-screen then blitted with synchronized-output (`?2026h/l`, TTY-gated) + cursor-home
  + per-line `\033[K` + final `\033[J`, replacing the flickering `\033[2J`.
- **Freshness**: expensive sources (claude `/usage`, codex rate-limits) are cached
  `ttl.expensive_source_sec` (60s) to avoid per-frame subprocess hang. POLICY shows
  `quota probe age: cached Ns ago`; `diag --fresh` forces one bypass. TTL stays 60s.

---

## 7. Alert Semantics

| Alert | Trigger | Action |
|-------|---------|--------|
| `CONTEXT_WARN` | context utilization >= `context_gate_warn_pct` or safe working limit | recommend prune / summarize |
| `CONTEXT_CRITICAL` | context utilization >= `context_gate_failover_pct` | recommend fresh session or failover |
| `CTX_UNKNOWN` | active peer lacks exact current occupancy | avoid precise remaining-token claims |
| `QUOTA_WARN` | any quota bucket >= 75% used | prefer other peer/profile |
| `QUOTA_CRITICAL` | any quota bucket >= 90% used | avoid routing unless necessary |
| `SESSION_STALE` | health/session timestamp exceeds policy | health-precheck or fresh session |
| `ACCOUNT_UNKNOWN` | account/plan/expiry source unavailable | show unknown, do not infer |

---

## 8. Actual Probe Summary

Read-only probes performed on 2026-06-30:

- `hub status`: room/handoff/active thread state available.
- `hub model-status`: active profile summary available for cc/ag/cx.
- `hub profile-validate`: 12 generated nodes checked, parity verified.
- `diag.py` source check: initial TDD implementation now exposes `--json`, `--watch [seconds]`, and `--interval <seconds>`; detail views remain reserved until their own TDD slice.
- JSON source probe:
  - cc live status has `context_window`, `rate_limits`, `model`, `cost`.
  - ag live status has `context_window`, `quota`, `model`, `plan_tier`, `product`, `email`.
  - health files have `availability`, `context_health`, `session_health`, and peer profiles.
  - `.ai/leases.json` includes root peers and generated profile nodes.
- SQLite source probe:
  - cx `threads` contains cumulative `tokens_used`, `model`, and `reasoning_effort`.
  - cx `remote_control_enrollments` exists but currently has zero rows.
- Log probe:
  - `cost-log.jsonl`, `ipc-log.jsonl`, and `error-log.jsonl` exist.
  - recent `cost-log` token fields are null for some peer calls; do not treat as zero.

---

## 9. TDD Pre-Stage Acceptance Criteria

Implementation should not start until these tests are written or explicitly stubbed:

1. Source collectors
   - cc collector reads status JSON and emits context/quota/model with source metadata.
   - ag collector masks email and emits plan/product/quota/context with source metadata.
   - cx collector distinguishes cumulative historical tokens from current context occupancy.
   - missing source files return `unknown` records, not exceptions.
2. Normalization
   - all volatile fields include `observed_at`, `ttl_sec`, and `confidence`.
   - null numeric fields render as unknown, never zero.
   - account identifiers are redacted before generic records are returned.
3. Presentation
   - default summary includes only peer, profile, gate, context, quota, session, alert.
   - profile matrix does not inline raw `profile_args`.
   - stale values are visibly marked.
4. Alerts
   - context warn/critical thresholds follow `governance_params.json`.
   - quota warn/critical thresholds are deterministic and tested.
   - `CTX_UNKNOWN` suppresses precise remaining-token claims.
5. CLI
   - `diag --json` returns valid JSON.
   - `diag --profiles`, `--accounts`, `--tokens`, `--sessions`, and `--project` are read-only.
   - `diag --watch` throttles refresh and does not poll expensive sources faster than TTL.
   - cheap local file sources may be refreshed every rendered frame.
   - local health/config/sqlite sources use a 5 second TTL.
   - expensive subprocess/API sources, including Codex app-server rate-limit reads, use a 60 second TTL.
   - expensive refreshes are non-blocking; watch rendering uses the last complete snapshot and marks stale values.
   - `diag --json` emits exactly one normalized JSON object and exits.
   - `diag --watch` defaults to 5 seconds and enforces a 2 second minimum interval.
   - `diag --watch <seconds>` with a value below 2 exits non-zero and emits a clear error message.
   - `diag --interval <seconds>` is an alias for `diag --watch <seconds>` and enforces the same 2 second minimum.
   - `diag --json --watch` emits NDJSON without ANSI control sequences.
   - non-TTY output never includes terminal clearing or alternate-screen control sequences.
   - `Ctrl+C` restores terminal state and exits with code 130.
   - quota reset display includes local absolute time, timezone, and relative countdown.
   - instruction-source detail shows path, existence, modified time, size, and optional hash without file contents.

---

## 10. Open Questions Before TDD

1. Should normalized telemetry be computed on demand only, or cached on disk (telemetry cache path TBD) for reuse across runs?
2. Should `diag --project` include git diff counts by default, or only dirty/clean status?
3. Should token history rollups read `cost-log.jsonl` directly or use a compact daily aggregate?
4. What is the safe working limit per model/profile when provider context limit is much larger than practical reasoning quality?
5. Should account expiry be stored manually when provider APIs do not expose it, or should it remain `unknown`?

> **Resolved 2026-07-01 (§12).** Answers to Q1-Q5 are recorded in §12 so TDD is not blocked on them.

---

## 11. Consolidated Review — Peer State & cx/ag Findings (2026-07-01)

Exhaustive review taking over the in-flight cx/ag work. The prior doc-review debate
(`tmp/diag-doc-review*.txt`, ipc-log 2026-06-30) raised three blockers that are now
**all resolved** in the current tree:

| Blocker (reviewer) | Status |
|---|---|
| §4 record `ttl_sec: 30` vs §6.4 "sqlite = 5s TTL" contradiction (cc.effort) | RESOLVED — §4 example now `ttl_sec: 5`. |
| Reset display missing timezone (ag.effort) | RESOLVED — `diag._fmt_reset` emits `%z`; `test_reset_formatter_*` asserts tz. |
| `--interval` in §6.2 had no §9 acceptance criterion (cc.effort) | RESOLVED — §9 criterion added; `test_interval_alias_*` covers it. |

### 11.1 cx "hang" phenomenon — root causes (not a model fault)

1. **Codex skills-context bloat (primary).** `_sys/codex/config/.tmp/plugins` carries
   **605 `SKILL.md`** (3119 skill-related files). Every `codex exec` emits
   `Exceeded skills context budget of 2%. All skill descriptions were removed and
   1363 additional skills were not included` — large per-call overhead that makes cx
   feel slow/stuck before real work starts.
   - **Clearing the cache is NOT durable:** codex re-syncs all 605 on the next
     restart (confirmed 2026-07-01). Durable mitigation belongs in codex startup, not
     a one-off delete.
   - **VERIFIED ROOT CAUSE + FIX (2026-07-01, R:10 ag+cx+cc consensus).** Empirical
     tests corrected the first hypothesis:
     - `codex exec --disable plugins --disable apps --disable workspace_dependencies`
       still logs "skills budget 2% exceeded" and returns fast — the `--disable`
       flags do NOT stop skill loading (dropped from the plan).
     - Real cause: `peers.json` `codex.env_vars` was `{}`, so hub IPC never set
       `CODEX_HOME`. `codex.cmd` then fell back to the host home
       `C:\Users\GREAT\.codex` (present, 621 skills) instead of portable
       `_sys/codex/config` — a divergent/cold cache whose first-use re-sync sat
       silent until the 600s zombie kill.
     - **Fix applied:** `peers.json codex.env_vars = {"CODEX_HOME": "config"}` (parity
       with cc `CLAUDE_CONFIG_DIR` / ag `AGY_CONFIG_HOME`); hub resolves it to
       `_sys/codex/config`. Verified: hub `ask --to cx` now replies in ~8s. Tests:
       `test_contracts.py::TestPeersJsonContract` (CODEX_HOME + portable-resolve).
     - Transitional: old host-home sessions won't resume after the pin; hub logs
       "session resume failed → retrying fresh" (expected, self-heals).
   - **DONE (defense-in-depth, 2026-07-01, R:10 ag+cx+cc):** staged silence guard
     in both ask loops — before first output, silence is bounded by
     `min(startup_timeout_sec=90, zombie)` → `timeout_kind="startup"`; after first
     output the zombie window applies. Turns any future silent stall (any cause)
     into a ~90s fast-fail instead of a 600s zombie wait. See `general/lifecycle.md`
     §17; tests in `test_hub_pty.py`/`test_pty_timeout_h2.py`/`test_contracts.py`.
   - **Live validation (2026-07-01):** a real `hub ask --to cx` that stalled at
     startup was fast-failed at exactly **90s** by this guard (not 600s).
   - **Skill reduction DEFERRED as accepted-benign (ag+cc; cx prior).** No
     config.toml/env lever selectively disables the marketplace skill sync
     (`--disable plugins/apps` does not stop it); delete-cache re-syncs and
     registry edits are fragile — high risk, zero functional gain now that the
     hang is fixed. The "skills budget 2% exceeded" line is an accepted benign log.
2. **Sandbox `spawn EPERM` / `지정된 경로를 찾을 수 없습니다` (path not found).** Codex
   child spawns intermittently fail under the workspace-write sandbox (error-log
   `sandbox_spawn_eperm`, `nonzero_exit`).
3. **Session-resume "permanent" failures.** `cx.deepthink session resume failed
   (permanent), retrying fresh` — resume path breaks, forcing fresh sessions (loses
   continuity but recovers).
4. **sqlite `tokens_used` mis-read as occupancy** — cumulative thread total, not
   current context; already corrected in `diag.py` (surfaced as total_tokens).

### 11.2 ag findings & fragility

1. **Atomic-rename residue.** `os.replace` on `.ai/*.json` fails under sandbox
   (`WinError 5` / `SANDBOX_RENAME_DENIED`) leaving **85 orphan `.ai/*.tmp`** files;
   surfaces as ag/cx `unexpected crash: PermissionError`.
2. **PTY scraping brittleness & estimation drift** (ag.deepthink review caution) — the
   Specific collector for ag must tolerate missing/partial `ag_stdin.log`.
3. Reset-display timezone gap (now fixed) and `manual.md:111` `??` comment typo (cosmetic, open).

### 11.3 Diagnostics pollution (why peers "look" broken)

- **error-log is ~25% synthetic:** 494 / 1942 lines are test fixtures
  (`testpeer`, `no cli`, `HTTP 401`, `fatal crash`, `some context window error`).
- Test runs write to the **real** `_sys/data/logs/*.jsonl` and real `.ai/` (ledger
  item E2), and a pytest temp path (`test_ask_eperm_marks_peer_red`) leaked into a
  live cx relay frame in ipc-log. Live `peer-status` is actually GREEN for cc/ag/cx.
- **Implication for diag:** collectors MUST treat logs as untrusted (filter synthetic
  peers, mark freshness) and MUST NOT crash on EPERM/missing paths — this is now an
  explicit TDD requirement (§13).

## 12. Open Questions — Resolved (2026-07-01)

1. **On-demand, in-process TTL cache only.** No on-disk telemetry cache for the first
   implementation (avoids added staleness and the very rename/permission failures in
   §11.2). Reuse the existing `_cached_codex_rate_limits` pattern.
2. **`--project`: dirty/clean + counts via `git status --porcelain`.** Diff line counts
   only inside `--project`, never in the default summary.
3. **Token history: read `cost-log.jsonl` directly** for now; add a daily aggregate only
   if the file grows costly. Null token fields render `unknown`, never zero.
4. **Safe working limit = ContextGate policy, not per-model constants.** Derive from
   `governance_params.json` (`context_gate_warn_pct` / `failover_pct`) × runtime window.
5. **Account expiry stays `unknown`.** Do not store manually; providers do not expose it.

## 13. TDD Entry Checklist (pre-TDD complete)

**Done — ALL slices complete (tests green — `_sys/tests/unit/test_diag_cli.py`, 26 tests):**
- **CLI skeleton**: `parse_args`, `--json` one-shot, `--json --watch` NDJSON,
  `--watch`/`--interval` 2s floor, expensive-source TTL cache, tz-aware reset formatter.
- **Normalization (§4)**: `normalize_peer` emits per-domain `source.kind/observed_at/
  ttl_sec/confidence` with `null`≠zero; `collect_snapshot` returns normalized peers;
  renderers consume the preserved `raw`; cx app-server quota 60s TTL vs 5s local.
- **Redaction (§5)**: `_mask_email` (first local char + domain); account exposes only
  the masked email; embedded `raw` sanitized so no unmasked address reaches JSON/NDJSON.
- **Resilience (§11)**: `collect_snapshot` never raises — a throwing collector degrades
  to an `unknown` record with the error surfaced (not silent); sqlite failures captured
  as `sqlite_read`; `_is_synthetic_peer` filters `testpeer`/non-orchestration peers.
- **Alerts (§7)**: `_compute_alerts` → `CONTEXT_WARN/CRITICAL` (from `governance_params`
  0.8/0.95), `CTX_UNKNOWN` (suppresses context thresholds, keeps numbers None),
  `QUOTA_WARN/CRITICAL` (0.75/0.90), `ACCOUNT_UNKNOWN`, `SESSION_UNVERIFIABLE`,
  `DIAG_INTERNAL_ERROR` (surfaces trapped collector errors — ag's anti-silent-mask). Each
  record carries `alerts[]`. (`SESSION_STALE` renamed `SESSION_UNVERIFIABLE` per ag — no
  timestamp source yet; a real staleness check remains future work.)
- **Detail views (§6.2)**: `--profiles` (matrix from orchestration.json; never inlines
  `profile_args`), `--accounts` (redacted), `--tokens` (null-safe), `--sessions`,
  `--project` (`git status --porcelain`, `GIT_OPTIONAL_LOCKS=0`, bounded, no shell,
  failures → `unknown`). All read-only.

R:10 design consensus: ag+cx ACK (slices 3-5, 2026-07-01). 990 unit green.

**Environment prerequisites — DONE 2026-07-01:** codex `.tmp/plugins` skill bloat
cleared (605 SKILL.md); 85 `.ai/*.tmp` rename-residue swept; 494 synthetic lines purged
from `error-log.jsonl`; test log isolation added (`HUB_LOG_DIR` env override in
`hub_logging.py` + autouse `isolate_hub_logs` fixture in `_sys/tests/unit/conftest.py`),
so production logs no longer accumulate test-fixture entries.

---

## 14. Pacing / Telemetry Follow-up — Debate Consensus (2026-07-01)

R:10 exhaustive debate. Participants: **ag.deepthink** (full), **cx** (expert confirms,
short-query path), **cc** (synthesis). **No top-level disagreement.** cx note: long
deepthink asks still stall on the codex skill re-sync; short focused asks answer fast on
`cx.standard`.

| ID | Item | Consensus | Priority |
|----|------|-----------|----------|
| **D0** | `diag --json` ~32min hang | **DONE.** `_codex_rate_limits(deadline_sec=12)` now uses a background reader thread + hard deadline + `proc.kill()` so the deadline holds even when `readline()` blocks (app-server spawn-EPERM under sandbox). `diag --json` now ~2s. cx: also treat timeout as terminal / drain pipes. | 1 (done) |
| **D1** | Stale usage ("Claude 100% after reset") | `observed_at` must be the **source-file mtime**, not diag's collection time. Add staleness `age` + `SOURCE_STALE` alert when age > ttl. (cc quota actually reset — 5h 0% / 7d 14% now; the 100% was a stale snapshot because status logs only refresh when that peer's statusline renders.) | 2 |
| **D2** | cx context wrong | Source from the **newest thread `rollout_path` JSONL** `event_msg/token_count`: occupancy = `last_token_usage.total_tokens` over `model_context_window` (capacity). sqlite `tokens_used` is cumulative — never occupancy. Parse resiliently (tolerate a truncated final line). | 3 |
| **D6** | Sandbox EPERM (cx, also ag/cc) | Centralize into a **shared core spawn helper** that traps `PermissionError`/`WinError 5`, retries **exactly once**, then degrades with a clear error. Generalizes the existing `SandboxRenameDeniedError` (rename) to spawn. | 4 |
| **D4** | Pacing UX | Show **numeric value + emoji** (e.g. `🟢 45%`), not emoji only. | 5 |
| **D3** | ag dual gemini+claude | Surface both pools: **DONE** (diag shows G/3P buckets). Mechanism for *using* both: **Option C (dynamic model arg)** — see §14.1; static-profile routing DEFERRED behind ag model-string enumeration. | 5 |
| **D7** | Refactor diag.py (~900 lines) | **ATTEMPTED then REVERTED (2026-07-01).** A `diagpkg/` split was delegated to ag; tests passed but only via a net-negative hack — production code coupled to the test's internal module name (`diag_under_test`) + `gc.get_referrers`/`sys.modules` registration — because the 33 tests monkeypatch names on the diag module and submodules can't see those patches without indirection. A clean split needs the tests to patch submodules (larger churn). Not worth it for a cosmetic, last-priority item: **kept the single-file diag.py** (clear section headers). Revisit only if the test-patch pattern is refactored first. | 6 (closed) |
| **D5** | Pacing → traffic routing | **Advisory only; dynamic routing weights DEFERRED.** Feeding live quota into `routing-config.json` weights risks thundering-herd/nondeterminism. diag surfaces headroom; coordinator/human chooses fallback. | deferred |

Invariant guards agreed: JSONL parsing resilient to truncated tail (D2); `null`≠zero
preserved; alerts stay deterministic & multi-valued; core spawn helper must not change
`_lease_cfg`/public contracts without updating `test_contracts.py`; D7 refactor gated on
D0-D6 stability.

### 14.1 D3 mechanism decision (2026-07-01)

Feasibility investigation refined the high-level "do both" into a concrete mechanism
choice. Three options were weighed:

- **A** — new static `ag.claude-*` profiles in orchestration.json. **Rejected**: breaks
  the `profile_contract.required_profiles = {standard, effort, deepthink}` invariant.
- **B** — a second antigravity-backed peer node (e.g. `ax`) whose 3 profiles map to
  Claude. Viable but heavy topology (new voter/routing/parity surface).
- **C — dynamic model arg (SELECTED).** `protocol.json model_profiles.dynamic_model_arg_supported`
  is already true; the hub can pass `--model "<claude>"` to `ag` at ask time to draw on
  the 3p/Claude pool, with **no governed profile/topology churn** and **no unverified
  model strings baked into config**.

Status:
- **"Surface both pools" — DONE.** `diag` already renders ag's `G-5H/G-7D/3P-5H/3P-7D`
  buckets (`_AG_QUOTA_LABELS`); the 3p/Claude pool is visible and currently ~100% free.
- **"Use both families" — mechanism decided (C); routing enablement DEFERRED** behind a
  feasibility gate: it requires ag to enumerate the exact non-interactive Claude model
  strings (`agy --model "<X>"`) and a concrete routing need before adding a hub `--model`
  passthrough for ag IPC. No governed change made now (that is precisely why C is safe to
  record without full peer ratification).
- Ratification: cc-selected; **ag's full design reply was pending** (deepthink,
  long-running) and **cx** was unavailable (deepthink skill-resync stall) at record time —
  to be folded in when ag responds. Since C mutates no governed config, recording it is a
  design note, not a governed edit.
- Rationale echoes D5: prefer advisory/explicit over baking dynamic model routing into
  governed config prematurely.
