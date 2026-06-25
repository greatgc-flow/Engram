# Terminal Health-Misread — Root Cause + Fix Consensus (2026-06-25)

> **Status:** CONSENSUS reached + SIGNED (cx + ag deepthink, 2-round converge; cc.deepthink token-constrained, sat out). Phase A pending user approval (deletions); Phases B/C deferred to focused TDD. Terminal (Haiku) relayed only.
> **Trigger:** a gpt-5.4-low terminal asked "peer status", did NOT run `hub.py peer-status`, manually crawled raw `health.json` files, hit a STALE MIRROR (the gemini health file = GREEN), and wrongly reported the suspended gc peer as alive — then spent many turns reconciling the contradiction.

## Root cause (agreed) — an ARCH-01 instance
Terminal models do ad-hoc filesystem analysis instead of routing to the SSOT tool, and the filesystem actively misleads them:
1. **Doc framing:** `health.md:20,96` present raw `health.json` as the health primitive ("Health checks = local health.json reads ONLY") — models read it as "I should open the file."
2. **Tool-affordance gap:** docs list `health-check` and `peer-status` side by side, but `health-check` is UNSAFE as a status view — it iterates `peers.json` (includes disabled gemini) and calls `_peer_effective_health(..., recover=True)` (`hub.py:3373`) which MUTATES stale status on read (it actually changed gemini health during cx's verification). `peer-status` iterates orchestration roots, filters disabled, and is non-mutating (`hub.py:3479-3497`).
3. **Mirror duplication:** the same peer has multiple contradictory `health.json` files (canonical `_sys/{claude,antigravity,codex}/` vs legacy `_sys/{ag,gc,ag.deepthink}/`, a root-level `health.json`, `_sys/gemini/`).
4. **Naming split:** `lifecycle_policy.json identity.node_to_peer` OMITS gc → `hub.py health-update --peer gc` resolves to a stray `gc` health file; `diag.py` uses `aliases[0]` as a dir (convention, not schema). `peers.json.node_ids/sys_subdir` already has the correct map (`_common.py:45-66`).

## CONSENSUS (signed by cx + ag)

**1. Resolver SSOT:** `peers.json` is the single SSOT for `peer_id -> sys_subdir`. Create ONE shared resolver `resolve_peer_sys_dir(peer_id, sys_dir=None)` (cx: in `hub_peer.py`; ag had said `_common.py` — pick at impl) reading `peers.json.node_ids/sys_subdir`. Update `hub.py::_peer_sys_dir`, `diag.py`, `_common.py`, `hub_health.py`, `ai_check.py` to call it. REMOVE the duplicate `lifecycle_policy.json identity.node_to_peer`.

**2. gc/Gemini retirement (suspended-but-registered, NOT deleted):** gc stays disabled in `peers.json` (install/history, prevents ID reuse), absent from active orchestration routing, with NO live health file. Ordered: (1) `ai_check.py` reads orchestration lifecycle only — if no enabled gc node, return OFF without reading gemini health; (2) `_common.py` uses the resolver + enabled roots only, delete hardcoded `{"gc":"gemini"}` (`:167-175`); (3) `health-check` excludes disabled gemini by default; (4) THEN delete the gemini health file; (5) keep `_sys/gemini/` install dir + a docs tombstone.

**3. health-check fate (PRO-12 behavior change + doc-demote):** default becomes read-only, non-recovering, orchestration-filtered (no disabled gemini, no `recover=True`). Recovery only via an explicit maintenance flag. Doc-demote to diagnostic/audit; `peer-status` is THE canonical terminal status view.

**4. Enforcement (no poison-pill):** the JSON `_warning` poison-pill is REJECTED as runtime noise. Instead: (a) terminal command contract lives in the **terminal-frame / system-prompt** — NOT `user-directives.md` (**PRO-09 forbids auto-generated rules there**); (b) `peer-status` warns when stray legacy `*/health.json` exist outside canonical sys_subdirs; (c) a validation TEST fails if a live peer has a competing `_sys/<peer_id>/health.json` when `peer_id != sys_subdir`; (d) a docs lint bans routine "read health.json" outside audit/impl contexts.

**Terminal command contract (canonical reads):** peer status -> `hub.py peer-status`; room/session -> `hub.py status`; routability -> `hub.py health-precheck --peer <id>`; models -> `hub.py model-status`; parity -> `hub.py profile-validate`; leases/locks/tasks/roles -> `lease-status`/`lock-status`/`task-status`/`role-status`. Terminal reads raw files ONLY when the task is explicitly "audit raw state/config" or the canonical command is missing/broken — and must say so.

## Phased plan (signed)
- **Phase A — mechanical safe-now (needs user OK; per-file re-verify):** delete gitignored legacy `_sys/{ag,gc,ag.deepthink,mock_peer}/health.json` + the root-level `health.json` (no code refs — cx verified). KEEP the gemini health file until Phase B removes its readers/writers. Add the `test_no_stray_health_files` validation test to lock the state.
- **Phase B — PRO-12 hub/code via TDD (tests first):** resolver + refactor callers; remove `lifecycle_policy.node_to_peer`; strip hardcoded gemini from `ai_check.py`/`_common.py`; delete the gemini health file; `health-check` non-recovering/orchestration-filtered default; update `test_contracts.py` (DIR-003) + dispatch-coverage per the standard-capability consensus.
- **Phase C — docs/directives:** update `health.md`, `user/manual.md`, skills docs (terminal status = `peer-status`; raw = audit-only); restore/remove `specific/gc.md` (missing, referenced at `health.md:126`); add the terminal command contract to terminal-frame/system-prompt docs (NOT user-directives.md).

**CONSENSUS one-liner:** peers.json `node_ids/sys_subdir` via one shared resolver; retire duplicate/legacy health files; `health-check` read-only + orchestration-filtered by default; enforce terminal status through `peer-status` + a stray-file validation test + a terminal-frame command contract (not user-directives.md, per PRO-09).
