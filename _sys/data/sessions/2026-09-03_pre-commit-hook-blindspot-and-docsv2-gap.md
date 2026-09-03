# 2026-09-03 — Pre-commit hook P:\ blindspot + docs-v2 disposition gap

## Finding 1: pre-commit hook was validating the frozen P:\ tree, not this worktree

The shared git pre-commit hook (`D:\Engram&Peerhub\PortableDev (v2.1)\.git\hooks\pre-commit`
— lives in the common `.git` dir, shared by every worktree off this repo, including
`engram-main-worktree`) hardcoded every check-script path as `P:/_sys/checks/...`.

This is a leftover from the pre-separation model where `P:\` *was* the live
checkout (SUBST-mounted). Since the separation, it silently meant every
`git commit` in `engram-main-worktree` ran CHK-01 (docs-MECE link check),
CHK-ENC, CHK-CONST, CHK-LEDGER, and WIRING against **`P:\`'s own frozen
`_sys/checks/*.py` and `_sys/docs-v2/**`**, never against the worktree
actually being committed. Both Increment A (`20a23f4`) and Increment B
(`e52ec4a`) commits passed this hook without it ever inspecting their real
changes at the hook level (the terminal's own independent `pytest` runs for
both increments are unaffected — that's a separate, correctly-scoped check —
but the git-hook-level guards were blind the whole time).

**Fixed**: rewrote the hook to resolve `ROOT="$(git rev-parse --show-toplevel)"`
and use `$ROOT/_sys/checks/...` for every stanza, so each worktree checks
itself. Also dropped the CHK-CONST/CHK-LEDGER stanzas as part of the fix,
since Increment C deletes both underlying check scripts (they validated
`_sys/ai/*` policy/telemetry config, out of Engram's post-separation scope).

**Immediate consequence once fixed**: running the corrected hook for the
first time surfaced 13 real CHK-01 findings — stale file references in
`_sys/docs-v2/**` pointing at files Increment A/B had already deleted
(`_sys/ai/peers.json`, `_sys/cli/peer_console.py`, `_sys/cli/codex.bat`,
`_sys/codex/session_state.json`, `_sys/ai/common/statusline/
statusline-unified.sh`, `_sys/codex/config/.sandbox/deny_read_acl_state.json`,
`_sys/cli/agy.bat`, `_sys/cli/codex_entry.py`, `_sys/codex/health.json`).
Dispatched as Increment C work item 4 (mechanical accuracy fixes only — see
below for why not more).

## Finding 2: `_sys/docs-v2/**`'s disposition is unaddressed by the ratified v8 diet plan

`grep -n "docs-v2" 2026-09-02_engram-diet-plan-v8.md` returns **zero
matches**. The ratified plan (Gates 1/5/6, 8 rounds, RATIFIED) never assigns
`_sys/docs-v2/**` — Engram's large SSOT protocol/governance documentation
tree, heavily AI/peer-governance-flavored by content (`general/protocol.md`,
`10-invariants.md`, per-peer docs under `specific/`) — to any increment or
disposition (keep-as-is / narrow / delete-in-D). This is a genuine gap in
the design, not something this session is authorized to resolve unilaterally
under the standing R:10 collab_rate (ambiguous ≥2-option decisions require
peer trade-off analysis, not an arbitrary terminal call).

**What was done about it now**: nothing beyond the 13 mechanical stale-path
fixes above (Increment C item 4) — those just stop the docs from lying about
file existence and are correct under *any* eventual disposition. The
disposition question itself (does `docs-v2` get deleted alongside `_sys/ai`
etc. in Increment D, narrowed to keep only genuinely-Engram-generic content,
or kept as peerhub's own docs mirror needing a real ownership decision) is
**tracked as an open gap requiring a dialectical round before Increment D's
directive-deletion step**, since Increment D's own precondition
(`peerhub.governance-directive.v1` existing with verified migration
receipts) already gates on directive-related content that likely lives
partly in `docs-v2`. Should be resolved together with Gate 2's discovery-
sweep design critique (also still pending a second independent voice, cx
unavailable until 2026-09-07).

## Status
Both findings documented per the standing "document before proceeding"
policy. Pre-commit hook fix is live now (affects all future commits in this
repo). The 13-reference fix is in-flight as part of Increment C's ag
dispatch. The docs-v2 disposition gap is *not* resolved — flagged for the
Increment D planning stage.
