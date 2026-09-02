# Seventh-round, final ratification-decision critique (cx.deepthink, 2026-09-02)

**Final verdict: NOT RATIFY.** V7 resolves the earlier architectural
choices; two of the three round-6 fixes remain mechanically incomplete,
and the source pass found a direct runtime break the plan didn't catch:
it orders `_load_peers()` deleted while retained production functions
still call it.

Terminal verification: both of the round's most decisive new citations
confirmed exact — `virtualizer.py` really does call `_load_peers` at 4
call sites (lines 262, 304, 387, 405), not just the one fallback path v7
addressed; `scrubber.py:109-121` really does contain a substantial `.ai`
governance-vs-ephemeral classification subsystem (explicit preserved-list:
`consensus/`, `quarantine/`, `state.json`, `leases.json`, `sessions/`,
`nodes.json`, `mailbox*`, `knowledge/`, `lessons/`, `broker/`, etc.) —
confirms scrubber.py is a genuine AI-governance owner beyond what v7's
plan accounted for.

## Closure table

| V7 correction | Result |
|---|---|
| Externalized uninstall | **FAIL** — correct direction, incomplete identity/handoff/journal protocol |
| Increment-D tests + Gemini stripping | **FAIL** — named deletions accurate but insufficient |
| Delete `check_contracts.py` + replace it | **PARTIAL** — deletion correct, replacement test underspecified |

## 1. Externalized uninstall — right direction, 3 concrete gaps

No administrator-privilege dependency evident (registry under `HKCU`,
drive cleanup via ordinary `subst /D`, junction cleanup via ordinary
unlink/rmdir — all confirmed real). But:

1. **Helper and journal aren't installation-scoped** — v7 uses fixed
   machine-wide paths (`%TEMP%\EngramUninstallHelper.bat`,
   `%LOCALAPPDATA%\Engram\uninstall_journal.json`) with no
   `installation_id`/`base_dir` in the schema, so two installations would
   share one receipt and helper path — contradicts the plan's own
   retained multi-instance behavior (`test_dual_instance_different_subst_drives`,
   `test_system_lifecycle.py:255-288`) and the sixth critique's explicit
   installation-identity requirement.
2. **Handoff protocol underspecified** — no parent PID, timeout,
   readiness handshake, helper arguments, or collision-resistant staging
   location; a fixed helper filename can't safely represent concurrent or
   stale uninstall attempts.
3. **Wrong process writes the final state** — v7 has the in-tree process
   write the "final" journal state before handing off, but
   `directory_purge` hasn't happened yet at that point; only the external
   helper can truthfully mark that step and the overall operation
   `COMPLETED`.

**Fix**: installation-scoped paths
(`%LOCALAPPDATA%\Engram\uninstall\<installation-id>\journal.json`,
`%TEMP%\EngramUninstall\<installation-id>\<nonce>\`), explicit
`base_dir`/journal-path/parent-PID handoff arguments, explicit
timeout/failure behavior, and the helper (not the exiting in-tree
process) records `directory_purge` and terminal status.

## 2. Test-gate fix — real progress, still can't pass

The two cited function names are confirmed real
(`test_tier1_preserves_ai_governance_state_deletes_only_ephemeral:157`,
`test_tier4_zerobase_clears_ai_governance_state:220`); rewriting
`test_no_stray_health_files.py` is sound; stripping `GEMINI_DIR`/the
status write from `run-tests.bat` addresses the exact real recreation
(`run-tests.bat:18,42-43`).

**But it's still not enough**:
- v7 deletes `virtualizer._load_peers()` in Increment B, but **6 more
  patches of that same attribute remain in
  `test_system_lifecycle.py`** (lines 72, 85, 98, 108, 235, 246) that v7's
  rewrite instruction never mentions.
- **More importantly: retained production code still calls the function
  being deleted** — confirmed, `virtualizer.mount()` (lines 258-275) and
  `virtualizer.unmount()` (lines 300-328) both call `_load_peers`. Deleting
  only the function and its one fallback path leaves the retained
  register/unregister code path broken. `mount()`/`unmount()` need
  explicit rewriting into generic SUBST/managed-link operations without
  any provider loop.
- The lifecycle test also has more AI-only cases v7 doesn't address:
  `test_cleanup_blocked_when_active_session_present` creates `.ai/.lock`
  (lines 185-204); the dual-instance fixture creates `_sys/ai` (255-261);
  the runtime-reset test creates `_sys/claude` (290-303).
- **`scrubber.py` is a genuine AI-governance owner** (confirmed above) —
  v7 only removed `_load_peers()` and one per-peer cleanup loop, but the
  real module still owns `.ai` governance/ephemeral classification
  (109-121), session-lock/lease parsing (124-150), `.ai` cleanup
  (195-210, 224-226), active-session cleanup blocking (430-441), and full
  `.ai` governance deletion at Tier 4 (350-360) — directly contradicting
  the final invariant that Engram owns no session/governance behavior.
  This is production logic, not stale test prose.
- `local-test.bat`'s AI-specific content extends beyond "mock setup" — real
  Gemini/session files and commands (73-87), Gemini status execution
  (159-169), Claude/Gemini context tooling (174-236), Gemini usage/package
  checks (246-265) all need deletion, not just the mock-setup subset v7
  named. (`host-test.ps1`'s wording was judged adequate as-is.)

## 3. `check_contracts.py` — deletion correct, replacement underspecified

The deletion itself fully resolves the prior contradiction (confirmed:
the real file is Claude-hook/AI-governance-specific throughout). But
`test_boundary_imports.py`'s spec ("no file under `_sys/` imports any
module from a deleted AI path") is missing: the exact forbidden module/
path set; whether it does AST parsing or unreliable text matching; how it
handles `importlib.import_module()`/relative imports; whether deleted
standalone modules (`relocator`, `agy_entry`, `console_runner`,
`peer_console`) are included; whether it separately asserts the deleted
directories themselves are absent. A sufficient contract: define the
forbidden roots from the ratified deletion inventory (`_sys/ai`,
`_sys/claude`, `_sys/codex`, `_sys/antigravity`, `_sys/hooks`, deleted
checks/entrypoints, `relocator.py`), AST-scan `Import`/`ImportFrom`,
handle constant-string dynamic imports, and assert every forbidden path
is absent from disk.

## Exact remaining blockers for round 8

1. Make uninstall state/helper paths installation-specific; define PID
   handoff + helper-owned terminal journal update.
2. Rewrite `virtualizer.mount()`/`unmount()` before deleting
   `_load_peers` — they currently call it.
3. Remove all `.ai` session/lease/governance behavior from `scrubber.py`,
   with matching lifecycle-test dispositions.
4. Remove the remaining 6 `_load_peers` patches and the 3 more AI-only
   lifecycle-test cases named above; complete `local-test.bat`'s AI-group
   deletion list.
5. Give `test_boundary_imports.py` an explicit forbidden-path set and a
   concrete checking algorithm (AST-based).

These are bounded, mechanical corrections — they affect runtime
executability and the final ownership invariant, not the architecture.
Verdict: **NOT RATIFY**, needs one more round.
