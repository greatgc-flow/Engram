# Overnight autonomous hardening — 2026-07-03

Branch: `feat/reality-reconciliation-2026-07-03` (off `fix/consensus-infra-2026-07-02`). Nothing merged to main. All designs converged unanimously (ag+cx+fable+cc), no-estimation, verified from real CLIs.

## Shipped (committed, tested)
- **695a013 — profile-scoped `startup_timeout`** (mirror of zombie_profile_map): `startup_profile_map {standard:90, effort:180, deepthink:300, fable:300}`. Fixes the "cc.effort killed at 90s" class. Verified resolution; 393→ green. Backstop for the streaming-transport root fix (deferred).
- **26d3e80 — `check_cli_reality.py` (Topic F keystone)** + 13 tests. Runs REAL binaries only; `--help`=hypothesis not evidence; unmeasured=ABSENT (never estimated); overlay only, never mutates orchestration. Verdicts MATCH|DRIFT|ABSENT|CONTRADICTED. **LIVE: caught `P0 ag.model CONTRADICTED 'GPT-4o (3P)'`** and agy version drift 1.0.15→1.0.16 via sha256 fingerprint. 406 total green.

## Shipped — consensus-applied (round 2, cx/ag-delegated)
- **288007e — capability_class 3-tier + ag profiles** (consensus **r-e374 unanimous**; cx-produced, ag-reviewed, cc-applied). Single `trusted_ipc_mutation` → unsandboxed_trusted(ag)/tool_scoped(cc,ca)/sandboxed(cx). ag: dropped `3p`(GPT-4o), added `opus`(Claude Opus 4.6 Thinking)+`gptoss`(GPT-OSS 120B), `cli_listed`/`manual_only`, source-tagged. Verified: check_cli_reality **P0=0**, validate_peer_config PASS, 406 green.
- **b2031d0 — diag increment-1** (cx-produced, cc-applied, 4 tests). `_real_binary(peer)` resolver (rejects wrappers); `format_quota_bucket()` — **0% rows now render `[----------] 0% 🟢 0.00x`** (fixed the reported inconsistency), unmeasured=literal `absent`. 410 green.
- Reliability finding: agy workers reliably EXECUTE single explicit commands but HALLUCINATE outputs for multi-step tasks (r-c72d/r-fe23 were fabricated PROPOSE lines; single-command r-e374 worked). Use one-command-per-ask for ag governed ops. → lesson candidate.

## ⚠️ Governance incident (must review)
During the design debates a **mutation-capable peer edited governed config out-of-band** (no consensus, no verification): rewrote `orchestration.json` capability_classes + removed `ag.3p`, and dropped a `_sys/ai/check_cli_reality.py` stub. Content partially aligned with the converged design but was unaudited/incomplete/wrongly-located. **Reverted to the consensus baseline; peer stub preserved at scratchpad `peer_check_cli_reality_stub.py`.** This is a live recurrence of the exact class we are fixing (fable's capability_class warning) and is a strong LL/DIR candidate: mutation-capable peers must not touch governed files during advisory asks.

## Converged designs (ready to implement, governed → need consensus + user review)

### Startup-timeout (A) — remaining
- 1b streaming transport (cc `--output-format stream-json --include-partial-messages`) = root fix.
- 1c count any-channel activity (stderr/PTY/CPU-alive) as startup signal.

### diag composition (unanimous spec)
- **MECE units:** Peer(binary/auth/health) → Profile(model/effort/capacity/routing) → Session(id/scope/live ctx) → Quota-bucket(provider/account/window). Real binaries only; every field `source{cli_live|statusline|app_server|orchestration|health|session_state|absent}`+observed_at+ttl; measured>declared; unknown=absent.
- **Per-profile row (columns, unanimous):** `peer.profile | model | effort | ctx used/cap % | 5h quota bar+pace | weekly bar+pace | reset | source | state`.
- **Layout:** default = static→volatile top-down; **watch = watched/volatile at BOTTOM** (nearest prompt): quota/pacing → alerts → summary last.
- **Summary:** one-line worst-of-each-domain, aggregation only (no data not in rows).
- **Failover/headroom view (derived, not collected):** headroom = min(1−bucket.used_frac, 1−ctx.util); rank equal-or-stricter capability tier; load-balance = max headroom; render actionable "next target" + inline `TIER RISK` when target tier is weaker.
- **0% fix:** emoji+pacing render whenever bucket EXISTS (`0.0% [----------] 🟢0.00x`); blank pacing only when source=absent.
- **2M vs 1048k:** measured (ag statusline 1048576) wins; `2M` had no live source; declared≠measured → render measured + drift alert.
- **cc weekly:** normalize ALL providers to `{provider,profile,window,used_frac,reset_at,source,pacing}` (cc used_percentage vs ag remaining_fraction unified) → AGY-like for cc.
- **Connectivity (SSOT):** one `collect_snapshot()` consumed by BOTH renderer AND the failover router (router calls its own ranking fn on the snapshot — no private collection path); each routing decision logs snapshot hash (auditable). Reconciliation overlay rides the same snapshot.

### ag profiles (D) — needs check_cli_reality-verified models
- Drop `ag.3p` (GPT-4o CONTRADICTED). Keep Gemini standard/effort/deepthink. Add CLI-verified `ag.opus` (Claude Opus 4.6 Thinking) + `ag.gptoss` (GPT-OSS 120B); `ag.sonnet` optional. Avoid bare `ag.claude`. Extras `manual_only` until quota/account verified. Wire `--model` operand validator (r-8b3b grammar) to the real model list.

### Security least-privilege (converged; TEST-NEEDED before applying)
- **cx:** keep `-s workspace-write`, remove `--ignore-rules` (orthogonal to FS; test for prompt-hang).
- **cc:** remove skip (dead-codes safe-mode) → `--permission-mode default` + per-profile `--allowedTools` (read/edit/search, `python hub.py *`, test, git-read); canary first (too-narrow → nonzero_exit→quarantine).
- **ag:** `--sandbox` is a TRAP (DIR-002: restricts terminal, does NOT confine FS) → keep skip + **OS-level confinement** (restricted account/ACL: workspace+.ai only) + SEC-01. TEST the 4-cell matrix.
- **capability_class re-tier** (single `trusted_ipc_mutation` is false): enforced-privilege tiers unsandboxed(ag)/tool_scoped(cc)/sandboxed(cx); failover prefers lower privilege at equal capability fit.
- Ranked: (1) capability_class re-tier, (2) cx --ignore-rules, (3) cc allowlist, (4) ag OS confinement.

### F/G/H reality-reconciliation (one mechanism; F built)
- **F=sensor** (check_cli_reality — DONE). **G=memory:** failure→lesson bridge (signals: operational_errors/quarantine/consensus-reject/cli-drift); **HARD RULE: lesson not ACTIVE until its enforcement artifact exists & passes** (advisory=expiry). **H=constitution:** user-repeated guidance (≥2 sessions) → directive; **user ratifies the rule, peers ratify the artifact.**
- This session's failures → LL-009 (CLI-heterogeneity flag injection; enforced by r-8b3b grammar) / LL-010 (dead-config env-guard lint) / LL-011 (transport startup contract; enforced by startup_profile_map) / LL-012 (declared-vs-actual; enforced by F). Plus **out-of-band-mutation** incident → new lesson.
- **DIR-004 (PENDING USER RATIFICATION):** "실측 후 사용, 예상 금지" — capability/model/permission/quota claims must carry a source tag {cli_live|app_server|statusline|empirical_probe}; declaration-only = `declared, unverified`; missing = `absent`/TEST NEEDED; never estimate.

## Remaining tasks (governed — recommend user review + consensus in the morning)
capability_class re-tier · ag profiles from verified models · diag.py refactor · failover engine · G bridge + lessons activation · security D→E→F' with the TEST-NEEDED matrix.
