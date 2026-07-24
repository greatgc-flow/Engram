# Ops — hub.py/hub_peer.py Architecture Conformance Audit (2026-07-24)

> Method: 10 rounds of mutual adversarial code audit (ag.deepthink + cx.deepthink),
> cross-reviewed until unanimous agreement, several claims independently
> spot-verified by the terminal (cc) directly against live source. Several
> bugs were reproduced with real probes (not just static analysis) —
> tagged `[live-repro]` below.
>
> **Why this exists / relation to packaging:** `ops/phase2-arch-general-specific-2026-07-22.md`
> §14.2 explicitly names `orchestration.json`'s `hub_nodes` adapter pattern as
> the architectural precedent for the eventual packaged Engram Core's
> `PeerAdapter` contract (§13.12 `adapter-conformance/v1`). This audit
> hardens that reference implementation — it is on the packaging critical
> path, not a tangent. The target architecture used as the conformance
> baseline (converged separately, same session, 3 rounds each):
>
> 1. **Hub Orchestration** (peer-neutral): routing, admission, task envelope,
>    session scope, fingerprint gate, persistence, audit, health, retry policy.
> 2. **Transport Infrastructure**: general process supervisor (deadlines,
>    leases, process-tree kill, telemetry) + platform I/O backends (`Pipe`,
>    `InheritTerminal`, `Pty` with a persistent `PtySession` handle) — no
>    vendor method names, prompt grammars, or silence heuristics here.
> 3. **Peer Adapter**: invocation plan, transport selection, protocol codec,
>    session control, peer-error classification, capability probing,
>    peer-specific idle/progress policy.
>
> **Meta-note (2026-07-24):** the first attempt to save this exact file was
> itself reverted, live, by the governed-mutation guard bug documented in
> §4/§5 below (Top-5 #2) — the terminal wrote this file while an unrelated
> `ag.deepthink` ask was in flight, and the guard's no-causal-attribution
> flaw treated the terminal's own legitimate concurrent write as an
> unauthorized mutation during that ask and reverted it. Real-time,
> unplanned confirmation of the bug it describes.
>
> Cross-ref: `ops/peer-cli-reference.md`, `ops/cli-update-checkpoints-{cc,agy,codex}.md`.

---

## Top 5 priority (P0/P1, updated after Round 9 findings)

| Rank | Bug | Where | Fix status |
|---|---|---|---|
| 1 | Mutation broker has no real transactional guarantees | `hub.py` broker (§2) | Fully designed, unanimous convergence (§6) |
| 2 | Governed-mutation guard has no causal attribution across concurrent asks; can blame an innocent ask, let the real culprit escape, or destroy authorized output. **No global dispatch lock exists — confirmed practically triggerable, not theoretical (and self-demonstrated while writing this very document — see meta-note above).** | `hub.py:5023-5081`, `4325-4351` | Not yet designed — highest-severity unfixed item |
| 3 | Final Arbiter override has zero effect on canonical consensus state (DIR-005 non-functional as implemented; `routing-config.json:221`'s "SHIPPED and ACTIVATED" claim is false) | `hub.py:6498-6536`, `4829-4863` | Fully designed, unanimous convergence (§6) |
| 4 | Lockless read-modify-write race in `action_append_handoff` | `hub.py:9765-9790` | Fully designed, unanimous convergence (§6) |
| 5 | `_classify_ask_failure` needle-matching order misclassifies transient failures as permanent (e.g. "rate limit: token quota exceeded" → `auth_error`) | `hub.py:1714-1774` | Fully designed, unanimous convergence (§6) |

---

## 1. Hub Core (Round 1-2, Track A)

1. **Session lifecycle** — mostly conforms (reuse is capability-driven via `session_mode`, scope/fingerprint/extraction are adapter-delegated). Violations: `_classify_resume_failure`/`_classify_ask_failure` do peer-error interpretation in core, not the adapter (see #5 above); `new-topic`/`clear-room` only retire sessions for `_routable_root_peer_ids()`, excluding disabled roots — ag confirmed this has zero runtime impact (disabled nodes are blocked by `is_routable()` at dispatch, so an un-retired session for a disabled node can never load) — downgraded to disk-hygiene debt, not a functional bug.
2. **Quota/routing** — the routing decision layer (`select_load_balanced_peer`, pacing, EXH math) is genuinely peer-neutral. The telemetry PRODUCER (`snapshot.py`) is not: hardcodes real peer binaries/paths (156-175), implements Codex app-server RPC directly (210-260), parses Claude `/usage` directly (413-482), and `gather_peer()` branches explicitly on `ag`/`cc`/`cx` identity (819-1080). `hub.py:7190-7192` hardcodes `peer != "cx"` for credit-consume (functionally single-peer today since only cx has a resettable-credit concept, but should be a capability flag, not a string compare). `diag.py`'s credit display, by contrast, IS already data-driven (`_has_credit_concept`) — not a violation.
3. **Consensus/Final Arbiter** — see Top-5 #3. Also: `_decide_consensus()` re-reads voter health LIVE at check-time rather than a round-start snapshot — a voter who validly agreed while healthy can retroactively force `escalated`/`human_gate` if it goes RED afterward, breaking "a previously cast agree remains valid."
4. **Governed mutation guard (base mechanism)** — correctly hub-orchestration-owned in principle (policy manifest-driven, independent hashing, single `try/finally` transaction boundary). Its CONCURRENCY correctness is a separate, serious problem — see Top-5 #2 and §4 below.
5. **IPC/room/quarantine** — mostly peer-neutral. `context-fill --frame` (`hub.py:7611-7658`) embeds prompt-neutralization logic specifically motivated by agy's persistent-session behavior while defaulting differently per peer — cx later found its actual behavioral effect is unverified (it only prints text; `agy_entry.py` doesn't pass that text through argv/stdin to agy — `[TEST NEEDED]`, not confirmed to matter). `action_init_session`/`action_send` have no validation that a peer identity is registered/routable before use — an admission gap.

## 2. Peer Adapter layer (Round 1-2, Track B)

1. **Invocation construction** — adapters do build their own base argv, but `hub.py` leaks two things into core: oversized-PTY-prompt staging directly mutates `cmd` in the core dispatch loop (`hub.py:5724-5738`; cx later refined the right fix as a `prepare_input()`-style adapter hook, not folding it into `build_cmd()`), and peer environment construction from `peers.json` happens entirely in core (`hub.py:5604-5673`) — cx notes this isn't inherently wrong; only vendor-specific derivation and runtime-home prep need adapter ownership.
2. **Session ID/resume** — CONFORMS cleanly, all three adapters (cited file:line ranges verified independently by both auditors).
3. **Error classification** — 100% lives in `hub.py` globally; zero adapter ownership (`PeerAdapter` protocol has no failure-classification hook).
4. **Capability probing** — 100% lives in `check_cli_reality.py`, disconnected from the adapter layer entirely. cx's later refinement: the target architecture doesn't strictly require a `probe_capabilities()` method on every adapter — a probe-definition-in-bundle-manifest model also satisfies it; the current disconnect is real either way.
5. **Profile/flag translation** — `profile_args` is passed through verbatim by every adapter; cx's correction: this is legitimate data-driven translation, not evidence of a bug — "AMBIGUOUS/THIN" was overstated as a violation.

## 3. Ask Transaction, process supervision, RuntimeContext/broker (Round 3, Track C — cx, `[live-repro]` throughout)

1. **ContextGate rejection is swallowed** `[live-repro]` — `ContextGate.check()` raises `ContextGateError` (`hub_context.py:156-163`), but `action_ask`'s exception handling catches it generically and proceeds (`hub.py:5464-5533`); the documented reject branch is unreachable. Probed: injected error, child still executed.
2. **Prune path is always a no-op** `[live-repro]` — the ask passes the ENTIRE query as one removable block (`hub.py:5472-5482`); pruning a single all-encompassing block returns empty, so nothing is ever actually pruned despite the code logging "prune applied." Probed: `pruned_blocks=0`, `query_unchanged=true`.
3. **Pipe transient failures report `sys.exit(0)`** `[live-repro]`, indistinguishable from real success — `hub.py:6145,6161,6177`. The PTY path uses a distinct `SOFT_SKIP_EXIT=7` (`hub.py:5815`) for the identical case, but that exit code is confirmed **completely unconsumed** by any caller anywhere (`action_ask_all`, `_real_arbiter_invoker`, `ctx_save.py`, `ctx_end.py` all ignore return codes). Fully designed fix in §6.
4. **PTY runtime escalation leaves a stale lease "open"** `[live-repro]` — the completed lower-tier lease never gets marked closed before returning during tier escalation (`hub.py:5890-5917`), so it's later treated as expired and its PID killed by the lease-expiry sweep. Probed directly.
5. **Pipe supervision misses small flushed chunks before a long gap on Windows** `[live-repro]` — blocking `stream.read(65536)` plus buffer-growth-only zombie tracking (`hub.py:4057-4111`) killed a real child that had genuinely flushed output moments before going quiet. Existing `test_stream_drain.py` only exercises processes that finish before the zombie window — structurally cannot catch this class.
6. **Broker fallback acknowledges an uncommitted mutation as complete** `[live-repro]` — `_try_broker_fallback()` (`hub.py:692-741`) queues and returns `True`; `_write_json_atomic()` treats that as success (766) though the target is untouched. Probed: queue returned `True`, `leases.json` stayed `{}`, subsequent `_lease_close()` raised `LeaseOwnershipError`.
7. **Broker full-file commits can overwrite newer state** `[live-repro]` — no `expected_revision`/CAS (`hub.py:928-935`); broker-drain and direct writers use DIFFERENT lock names (`broker_{filename}` vs the plain resource name, `hub.py:801` vs `9380`). Probed: state at revision 2 got committed back down to a stale queued revision 1. Root cause synthesis (ag): bugs #6 and #7 are ONE underlying failure — "the broker is an asynchronous, un-isolated file queue pretending to be synchronous transactional storage."

## 4. Health/routing gates, Leadership/locks/handoff, Governance (Round 3, Track D — ag; upgraded by cx in Round 4)

1. **`_peer_effective_health()` ignores profile-level `gate_open`** — root status can read `GREEN` while every profile is closed. Initially rated AMBIGUOUS by ag (since `_healthy_peer()` has a workaround); **upgraded to VIOLATES by cx with a probe**: leader matching, proposal-voter selection, leadership challenges, and governance prechecks call `_peer_effective_health()` DIRECTLY without that workaround, so this can produce real wrong eligibility decisions in consensus/leadership contexts. Fully designed fix in §6.
2. **Lockless read-modify-write race in `action_append_handoff`** — see Top-5 #4. Independently verified directly by the terminal (confirmed `_get_lock` is used pervasively elsewhere — broker/state/mailbox/log — but genuinely absent here).
3. **Governance systems mostly conform** (good news) — proposals/directives/lessons/alerts ARE actually consumed, not write-only: `proposal-vote` auto-writes `INV-xx` invariants on unanimous consensus; `directive-add` entries get injected into every relay frame; lessons get compiled and injected; alerts set global blocked state and broadcast. Only `action_thread_react` is write-only telemetry with no reader. cx's caveat: this "only 1 write-only stub" framing undersells the pattern system-wide — the arbiter's `final_opinions.jsonl` (§1.3) is another instance of the exact same class.

## 5. `check_cli_reality.py`, governed-mutation guard concurrency, test-suite self-audit (Round 8, Track F — cx, `[live-repro]` throughout)

1. **Partial canary successes treated as a complete catalog** `[live-repro]` — `build_observed_capture()` only records `PASS` models; the loader discards source/provenance; any other declared-but-unprobed model becomes false `CONTRADICTED`. **Confirmed live in production data on 2026-07-24**: a real, non-synthetic run against current `orchestration.json` produced 5 false P0 CONTRADICTED verdicts for `ag` models that are all genuinely present in the real live catalog (verified via a real `agy.exe models` call in the same session).
2. **Stale/binary-incompatible captures trusted as fresh** — no `captured_at`/fingerprint/provenance validation before use. Probed with a synthetic cache.
3. **Missing bare-command binaries crash** instead of the documented `ABSENT` verdict (`FileNotFoundError` uncaught). Probed directly.
4. **Failed version probes become observations** — `probe_version()` never checks `returncode`; exit 1 with `"fatal: protocol 9.8.7 unsupported"` returned observed version `9.8.7`. Probed directly.
5. **Governed-mutation guard: no causal attribution across overlapping asks** — see Top-5 #2. Reproduced with two live interleaved helper windows: innocent ask B gets blamed and reverts the change; culprit A's own post-check then sees the (now-reverted) original hash and escapes unflagged. **Independently confirmed practically triggerable by ag**: no global dispatch lock exists anywhere in `action_ask()`/`_action_ask_inner()`. **Self-demonstrated a third time while this document was being written — see meta-note at the top.**
6. **Authorized concurrent output can be wrongly reverted** — an authorized ask skips its own guard snapshot, but an overlapping ORDINARY ask still sees the authorized ask's legitimate output as a violation and reverts it. Probed: `authorized_output_survived=false`.
7. **TOCTOU window even in the "race guard"** — rehash then separate `git checkout` (`hub.py:4325-4351`); a write in between survives undetected.
8. **Guard failures fail OPEN** — pre-ask snapshot or post-check exceptions let `action_ask()` return success with zero protection. An EXISTING TEST (`test_guard_post_check_error_never_breaks_ask`) explicitly requires this — institutionalized, not accidental.
9. **6 test-suite blind spots** where tests assert "was called"/"did not raise" without verifying the claimed effect: `test_denied_write_queues_to_broker` codifies the broker bug (asserts "must NOT raise", never checks the target changed); `test_stream_drain.py` never invokes `_action_ask_inner()` so it structurally cannot catch the exit-code bug; `test_clean_at_dispatch_tracked_auto_reverted` mocks `git checkout`, never verifies file contents were restored; `test_concurrent_race_aborts_revert` tests the wrong race (a write during HEAD lookup, not overlapping ask windows); `test_at1_health_written_before_exit` mocks `_record_ask_failure` and checks it was called, never inspects `health.json`; `test_arbiter_autowire.py` only calls `_maybe_run_arbiter_on_finalize()` directly, never through the real production call sites (`action_consensus_vote()`/broker-drain) — breaking both real integration points would stay green.

## 6. Round 8 — peer_mgr.py, provisioner.py, quota.py, ctx_save/ctx_end.py (Track E — ag)

1. **`peer_mgr.py:_save()` fixed `.tmp` path, no lock** (52-60) — concurrent admin invocations can collide.
2. **`peer_mgr.py` multi-file mutations are non-atomic** — `cmd_suspend()` (3 files) / `cmd_add()` (4 files + peer doc) sequentially save separate registries with no cross-file transaction; a crash mid-sequence leaves `orchestration.json`/`peers.json`/`protocol.json` disagreeing about a peer's state.
3. **`provisioner.py`** — checksum enforcement, same-host redirect guarding, and atomic canary-then-swap installation all LOOK CORRECT. Minor: `_install_extra()` doesn't guard `_extract()` against running on a download interrupted before checksum validation.
4. **`quota.py:get_remaining_seconds()` naive-ISO timezone bug** — `.replace("Z", "+00:00")` only handles Zulu-suffixed strings; a naive ISO string (no offset) gets parsed by `datetime.fromisoformat().timestamp()` as LOCAL system time, not UTC — up to a full timezone-offset skew in quota pacing math. **Downgraded to latent/defensive** after cx checked real observed formats this session: ag uses `Z`-suffixed timestamps + `reset_in_seconds`, cc uses Unix epochs — no naive timestamp has actually been observed in practice. Real risk only if a vendor ever changes format.
5. **`ctx_end.py:228-231` hangs indefinitely on failure** — calls `input("Press Enter to continue...")` when `claude -p` returns nonzero; hangs any non-interactive/automated/headless invocation. **Elevated priority**: this is a script the user runs directly (CLAUDE.md: "Run ctx-end when done for the day"), not just an internal hub.py mechanism.
6. **`ctx_save.py:114-118` doesn't check subprocess returncode** before unconditionally overwriting `summary_session.md` with the subprocess's stdout — a failed call can destroy an existing session summary with error text or an empty file.

## 7. Round 10 — final action-handler sweep (ag)

1. **`context-ack` lockless read-modify-write + 100% unconsumed** (`hub.py:8143-8155`) — same write-only-stub pattern as the arbiter bug (§1.3); `context_ack.json` is never read anywhere in the codebase, so it provides no actual integrity gating despite the name.
2. **`_lease_sweep` silently swallows timezone comparison exceptions** (`hub.py:9502-9523`) — a naive-vs-aware `datetime` comparison raises `TypeError`, caught by a bare `except Exception: pass`, so any lease with a naive-ISO expiry timestamp is NEVER marked expired — a zombie lease that never gets cleaned up.
3. `artifact-claim`/`status`/`finalize`, `discover`, `update-signatures`, `transient-scan` — all LOOKS CORRECT (proper locking, read-only where appropriate, no un-isolated mutation found).

**Round 10 returning mostly-clean results (4 of 6 areas correct) is itself a signal that action-handler coverage across `hub.py`'s surface is approaching complete.**

---

## Fully-designed fixes (unanimous convergence, ag + cx, 3 rounds of mutual adversarial revision each)

These 3 bugs (Top-5 #1, #3, #4, #5 — the broker, arbiter, handoff, and classification bugs) have committable-quality fix designs, including edge-case handling, regression test tables, and honest risk assessment. Full designs with code are preserved in this session's transcript; summary:

- **Broker (Top-5 #1)**: delete `_try_broker_fallback()` entirely (a synchronous write must commit or raise, never silently queue); explicit `broker-submit` becomes a real CAS operation (SHA-256 `expected_revision` of raw file bytes, `.ready` marker for crash-safe publication); broker-drain uses the SAME lock name as direct writers via a new `_mutation_lock_resource()` mapping table. Flagged "High" fix risk — deliberately makes previously-hidden sandbox failures visible. Also found `_normalize_runtime_files()` and `action_thread_promote()` need the same lock-unification fix.
- **Arbiter override (Top-5 #3)**: `_apply_arbiter_override_to_round()` under a per-round lock, refusing to touch `finalized`/`unanimous` rounds, validating `round_id` match and `authority == "override"`, requiring a strict first-line `VERDICT: APPROVE|REJECT` parse (loosened prefix-matching was rejected after cx found it could misparse). Requires an ATOMIC companion fix to `_real_arbiter_invoker()` (currently ignores the arbiter subprocess's own return code — a failed/rate-limited arbiter invocation could otherwise produce misparseable partial stdout) and a new explicit output-contract instruction in `condense_arbiter_input()` (the arbiter is currently never told to emit a parseable verdict marker at all).
- **Handoff race (Top-5 #4)**: acquire the existing `"handoff"` lock (already used elsewhere) BEFORE the file-existence check, not just around the read/write — otherwise the check-then-read isn't in the same critical section.
- **Error classification (Top-5 #5)**: reorder to check sandbox/spawn and cli-not-found FIRST, add dedicated `model_error`/`session_invalid` categories (critical: do NOT fold "model/session not found" into the transient `rate_or_session_limit` bucket — cx caught that this would cause unbounded auto-retry churn against permanently-missing models/sessions since transient failures get cooldown-based auto-reopening), narrow all needles to word-boundary regexes with proper context requirements (preserve the `index 503` negative-lookbehind guard; require EPERM/denial context for the spawn needle).
- **Health-gate fix**: centralize the profile-gate check inside `_peer_effective_health()` itself using the EXISTING `profile_health_gate_open()` SSOT helper from `snapshot.py:1282` (NOT a raw `gate_open is False` read — cx found that bypassing the SSOT helper reintroduces a cooldown-expiry race where the first post-reset ask is still wrongly rejected).

**Not yet designed**: Top-5 #2 (governed-mutation guard concurrency) has no fix proposal yet — it is the highest-severity CONFIRMED-unfixed item as of this document, and demonstrated itself against this very file (see meta-note).

---

## Methodology notes worth preserving

- Every "final" claim from a single peer in this audit was cross-reviewed at least once; several were caught overstating (ag idealizing target architecture as current behavior, twice; a too-narrow `ProcessIOMode` enum; a too-loose arbiter verdict parser; folding not-found errors into the wrong category) and corrected before being accepted.
- The terminal (cc) independently spot-verified 5+ claims directly against live source rather than trusting peer reports at face value — all confirmed accurate. One adjacent lesson from this session: a peer (ag) fabricated 6 plausible-looking external GitHub issue citations when asked to web-search for known bugs in a DIFFERENT task earlier this session — caught by direct `WebFetch` verification. That incident does not appear to apply to this audit (no external citations were used here, only live source/probes), but it's the reason several claims above were independently re-verified rather than taken on trust.
- **Operational lesson from writing this document itself**: never write to a governed path while a peer `ask` is in flight — even an unrelated peer working on an unrelated task can trigger the guard's misattribution bug against the terminal's own concurrent edit. Verify no `ask` is in-flight (or accept the file may need re-writing) before saving governed docs going forward, until Top-5 #2 is actually fixed.
