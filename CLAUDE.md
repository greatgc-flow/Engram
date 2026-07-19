# Claude Code — Project Instructions

> This file is a **pointer only**. All normative content and live state live in _sys/.
> As an AI peer, you MUST read the SSOT immediately upon startup to understand your operating rules.

## 1. Startup Requirements
> **NOTE FOR IPC / SUBAGENT TASKS**: If you are responding to an automated IPC ask or continuing a session, **SKIP THIS ENTIRE SECTION**. Do NOT read these documents. Proceed directly to the user query.

1. **CONDITIONAL**: Read _sys/docs-v2/MOC.md to locate the rules for your current task ONLY if you are starting a fresh interactive session.
2. **CONDITIONAL**: Read _sys/docs-v2/10-invariants.md ONLY if you need to recall the non-negotiable hard rules.
3. **CONDITIONAL**: Read _sys/docs-v2/specific/cc.md for your specific peer configuration ONLY if you encounter configuration issues.
4. **CONDITIONAL**: Read .ai/sessions/room-{uuid}/handoff.md ONLY if instructed to synchronize with the current session state.

## 2. Directory Mappings
- Your local settings and memory are located in _sys/claude/config/.

---

# Current Project State
> This project's live state lives in _sys/docs-v2/ and _sys/ai/backlog.json.
> Do not rely on stale summaries.

- **SSOT Backlog**: _sys/ai/backlog.json
- **Most recent comprehensive audit**: _sys/docs-v2/ops/mega-mece-audit-2026-07-16.md

Always consult the above SSOTs for the authoritative remaining-work list and system state.

---

## Session Handoff (2026-07-19)
> Snapshot only — SSOTs above remain authoritative for anything longer-lived than this handoff.

### Current State
- Branch `main`, up to date with `origin/main`.
- `_sys/runtimes.json`'s auto-discovery version bump is reviewed and fixed: `claude` 2.1.206→2.1.215, `codex` 0.144.1→0.144.6, `fzf` 0.73.1→0.74.1, `gh` 2.93.0→2.96.0, `jq` 1.8.1→1.8.2, `oh-my-posh` 29.14.0→29.33.0 (its `extras.themes.zip` URL bumped to match, was still pointing at the old tag), `ripgrep` 15.1.0→15.2.0, `sqlite` 3.53.1→3.53.3 (+new `sha3_256`). The ripgrep `aarch64` URL bug (was pointing at ARM64 on this AMD64/x86_64 machine, confirmed via `Get-CimInstance Win32_Processor`) is fixed to `x86_64-pc-windows-msvc`; all URLs live-verified reachable (curl HEAD).
- `_sys/ai/backlog.json` is current: `updated_at: 2026-07-19T10:47:59Z`, 109 items. Only non-done items are intentionally inactive: `D4` (diag inc-4 failover engine, deferred), `T70` (diag off-machine snapshot design, deferred), plus a handful of `dropped`/`superseded` entries — no live open work item outstanding.
- Last commits: AT1 tests hardened against the real `pacing_hard_gate` too (`f58e261`) → permission-rule fix `Write()`→`Edit()` (`e911040`) → `cx.deepthink` added to DIR-005 `arbiter_models`, user-authorized (`ab3af8f`) → `ag.deepthink` tier-inversion §4.1 resolved via live empirical probe (`0f753d9`) → T73 closed with evidence (`08b11f9`) → T73 real fix, infinite-loop/memory-explosion root cause (`828f2da`).
- A long-running orphaned session (`cdd137d8...`, alive since 2026-07-15, ~2h accumulated CPU) was found still active and was the source of the runtimes.json WIP and various peer pings; user confirmed it wasn't intentional. Investigate whether it should be terminated.

### Decisions Made
- IPC query files are single-use by design; reusing one that already zombied/failed used to fail silently (regex bug, ~4 weeks unnoticed) and now loudly warns instead — `c2f88e4` + `0feb3f3`.
- The mystery paired-zombie incident is resolved for its *origin*: `cx.deepthink` was self-orchestrating (dispatching further asks on its own) rather than a hub defect — confirmed via literal command logs (`7477d20`). Per `[[feedback_multipeer_prompt_scoping]]` memory, dispatched peers must be explicitly told they're one voice among N and must not self-orchestrate further asks.
- `ag`'s own baseline stall/output-batching mechanism is explicitly **not** resolved by the above — two independent forensic passes still haven't nailed the mechanism. Do not report it as fixed.
- T71 (hub peer-invoke cwd-dependent `shutil.which()` latching peers RED) shipped `521b22c`; T72 (consensus tests leaking real global peer health) shipped `52e292c`; T73 ("AT1 hangs" were a genuine infinite-loop/memory explosion from `patch("...Popen")` poisoning `snapshot.py`'s unrelated subprocess use, not a flaky timeout) shipped `828f2da` — full suite reconciled to 1185/1185 green.
- diag gained a `--usage` view (recent per-profile ask count/success/fail) wired into the main dashboard (`f24176a`, `5dc1c14`).
- `.bat` terminal launches now default to the `effort` tier via new `interactive_default_profile` (was silently defaulting to `deepthink`); dormant `ca` node retired (`e712862`).
- External server-ization of Engram for a 3rd-party integration was reviewed and rejected 3/3 unanimous (`bc3a314`) — see `[[project_external_server_ization_review_2026_07_19]]`.
- `ag.deepthink` tier-inversion (§4.1) resolved: Gemini 3.5 Pro confirmed unavailable via a live empirical canary probe; Option B was already applied, this just closes the open question with evidence (`0f753d9`).
- `cx.deepthink` added to DIR-005 `arbiter_models` — user explicitly authorized (Sol ~59 is effectively co-top with Fable ~60 on the external composite, was the only top-tier reasoner excluded). Required a companion fix: added a `shared_quota_reserve` entry for cx's X-family (mirroring cc's C-family protection), caught by `test_config_validator` — cx.deepthink would otherwise have shared its quota family with cx's bulk-routable profiles with no reserve floor (`ab3af8f`).
- Permission config: `Write(path)` allow-rules are non-functional (only `Edit(path)` rules are matched by file-permission checks); corrected in `settings.json` after the harness repeatedly surfaced the warning this session (`e911040`).

### Next Steps
1. Decide whether to terminate the orphaned long-running session `cdd137d8-e483-40cf-b9a8-0c0275ec5a20` (PID 28036/53008 as of this handoff) — user did not intend it to be running.
2. If another zombie/stall incident occurs, resume the `ag` baseline-mechanism investigation — root cause still open after 2 forensic passes.
3. No active backlog items need attention right now (only `D4` and `T70` remain, both intentionally deferred) — next session should pull from `_sys/ai/backlog.json` fresh rather than assuming carryover.

### Last updated
2026-07-19
