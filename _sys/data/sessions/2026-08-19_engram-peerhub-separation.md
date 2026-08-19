# Session Checkpoint — Engram/peerhub separation + diag audit (2026-08-19)

Terminal switched to Opus mid-session; the separation was then executed
directly rather than delegated (all peers were quota-exhausted, and two
separate infra bugs blocked cc delegation entirely).

## SHIPPED — both repos pushed

**Engram** `github.com/greatgc-flow/Engram` → `main` at `6b50945`
(merge of `separation/engram-peerhub`, commit `482ab76`):
**207 files changed, -57,403 lines.**

- Removed the legacy coordination cluster: `hub.py` (12,351 lines),
  `hub_peer/hub_context/hub_error/hub_health/hub_logging/hub_interceptor/
  hub_profile_router`, `operational_guard_matrix`, `snapshot`, `quota`,
  `quota_capabilities`, `pathlayout`; `diag.py`, `msg.bat`, `hub.bat`,
  `peer_mgr`, `batch_review`, `ag_statusline`, `git_draft`,
  collab-rate scripts; 17 peer/governance checks; 4 hooks; ~115 tests.
- Kept-but-decoupled: `console_runner.py` rewritten as a pure interactive
  process wrapper; `provisioner.py`'s install interlock now observes real
  OS process ownership instead of parsing `.ai/leases.json`;
  `ctx_save`/`ctx_end` kept as local checkpointing minus the peer calls;
  `agy-status`/`codex-status` repointed to vendor-native version checks.
- `protocol.json` reduced to environment scope (removed `collab_rate`,
  `consensus`, `leader_election`, session/health policy, +11 more keys).
- 14 governance docs archived to `_sys/docs/history/engram-peer-governance/`
  with a README naming every intentionally-dropped feature.
- **The contract gate was replaced, not disabled**:
  `_sys/tests/unit/l1_core/test_contracts.py` used to pin hub.py's API
  signatures; it now asserts the *product boundary* (no removed module may
  return, no source may import one or shell out to hub.py/msg.bat,
  console_runner must stay pure, lifecycle core must stay intact). 7/7.
- Verified: unit suite **494 passed / 4 failed** vs a **9-failed baseline**
  before the work. 3 of the 4 are unchanged pre-existing provisioner
  npm-canary failures; the 4th passes in isolation (order-dependent).
  Live: dispatcher HEALTHY, doctor exit 0, `claude.bat --version` 2.1.215,
  `peerhub.bat --version`, `diag.bat`.

**peerhub** `github.com/greatgc-flow/peerhub` → `main` at `7a5f939`
(5 commits): telemetry Engram-path decoupling (`974754e`), `room-efde`
removal + v0.1.8 (`259512b`), backlog records (`1368817`, `7a5f939`),
and the E2E quota-wiring reproduction tests (`a87507c`, intentionally
red — 5 failing tests that define the pending fix).

## DIAG E2E AUDIT — component-by-component (2026-08-19 11:48 KST)

Every displayed element traced to its real source. **The dashboard has no
staleness indicator anywhere**, which is the root of the reported bug.

| Element | Real source | State |
|---|---|---|
| AG 3P-pool, G-pool, context | `_sys/data/temp/ag_statusline_stdin.log` | live-ish, **3h07m old** |
| CC C-pool, context, cost | `_sys/claude/config/status_input.log` | **37h18m old (1d13h)** |
| CX context (only) | `_sys/codex/config/state_5.sqlite` | 10h05m old |
| CX X-pool quota | **nothing** — was hardcoded until `974754e` | now honestly absent |
| Room / leader | **nothing** — was hardcoded `room-efde` | removed in `259512b` |

### Reset times: displayed vs. reality

CC's `resets_at` is a **Unix epoch (1787011200)**, not ISO — the presenter's
`fromisoformat` path cannot parse it, so the countdown comes from the
`source_msg` string parser instead ("resets 10pm (Asia/Seoul)").

| Window | Recorded reset | Reality vs. now |
|---|---|---|
| CC 5-hour (used 0%) | 2026-08-18 09:00 KST | **AGO 1d 2h** |
| CC 7-day (used 100%) | 2026-08-18 09:00 KST | **AGO 1d 2h — already reset** |
| AG 3p-5h (used 93%) | 2026-08-18 23:34 KST | **AGO 12h 14m — already reset** |
| AG 3p-weekly (used 54%) | 2026-08-24 14:44 KST | in 5d 2h 55m ✅ only valid one |
| AG gemini-5h (used 0%) | 2026-08-19 03:47 KST | **AGO 8h 01m — already reset** |
| AG gemini-weekly (100%) | 2026-08-19 04:37 KST | **AGO 7h 11m — already reset** |

**4 of 6 quota windows had already reset** but are still displayed as
consumed. This confirms and *extends* the original complaint: it is not
only CC's 7-day — AG's G-pool and 3P-pool 5H are stale the same way. The
displayed "100% used" is simply the last value ever written to a file that
nothing re-polls.

### Additional e2e findings

1. **`--fresh` is a dead flag** — defined in argparse, never read by
   `_run_diag()` or `collect_live_snapshot()`. Every `--fresh` run this
   session was a no-op.
2. **The real polling pipeline has zero callers.** `poll_claude_usage()`,
   `poll_codex_usage()`, `poll_agy_usage()`, `record_usage_observations()`
   exist, are tested, and are wired to migration `0024`'s
   `usage_projections` — but nothing in the package ever calls them.
   `TelemetryPresenter` is constructed without `usage_projections`.
3. **AG's data only looks live by accident** — `agy`'s own statusline hook
   calls `peerhub statusline`, which rewrites the log during real use.
   CC/CX have no equivalent trigger, so their files only change when the
   vendor CLI happens to write them.
4. **`peerhub diag` silently shows nothing when run outside the Engram
   root** (workspace defaults to `.`; `_find_sys_dir()` finds no `_sys`).
   Post-decoupling this should be an honest "no data source configured"
   message rather than an empty table.
5. `_sys/antigravity/config/status_input.log` (AG's fallback source) is
   **1332h / 55 days old** — effectively dead.

## PENDING

- **3P-pool recovery monitor running** (background, 10-min interval, 4h
  cap). On recovery: re-dispatch the quota-wiring fix that makes
  `test_quota_wiring_e2e.py`'s 5 red tests pass — wire `--fresh`/`diag`/
  `status` to actually call the pollers, and pick a `--live` re-poll
  cadence (not the 2s render tick; `claude.cmd /usage` alone measured
  ~9.4s).
- Add a staleness indicator to the dashboard — with `[stale]`/age shown,
  the original bug would have been self-evident instead of silently wrong.
- `P:\_sys\claude\config\CLAUDE.md` still documents the collab_rate /
  R:6-R:10 / Final Call protocol that no longer exists anywhere. It is the
  user's own global config (outside both repos) and needs a rewrite to
  "use peerhub for peer communication; no collab-rate/consensus gating".

## Infra bugs found (saved to memory)

- `hub.py ask --to cc.*` failed **100%** on this portable root: the path
  `D:\Engram&Peerhub\PortableDev (v2.1)` contains both `&` and a space, and
  the cc invocation built an unquoted cmd string — cmd.exe split it.
  (`reference_hub_cc_dispatch_path_quoting_bug.md`)
- `peerhub ask cc --capability-tier WORKTREE_WRITE|GIT_MUTATE` fails with
  `CapabilityLeaseViolation` on a fresh clone — fail-closed by design, no
  measured enforcement evidence exists. Only `READ_ONLY` works.
  (`reference_peerhub_ask_no_mutation_evidence_fresh_workspace.md`)
- Together these meant **no working channel existed to delegate
  file-writing work to cc**, which is why the separation was done directly.
