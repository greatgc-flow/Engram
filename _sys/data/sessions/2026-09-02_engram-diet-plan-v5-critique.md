# Fifth-round ratification critique (cx.deepthink, 2026-09-02)

**Verdict: DO NOT RATIFY v5 as first persisted.** Architecture confirmed
sound and not reopened. The critique's headline finding was actually a
**terminal transcription error, not an ag content problem**: the first
committed version of `2026-09-02_engram-diet-plan-v5.md` summarized ag's
real JSON Schema, migration table, and acceptance matrix into prose
instead of reproducing them — cx correctly flagged this as "claims
artifacts exist that are absent from the persisted file." The terminal
re-persisted the document with ag's actual raw content restored verbatim
(see the corrected `2026-09-02_engram-diet-plan-v5.md`, which carries a
"TERMINAL RE-PERSIST NOTE" explaining this exactly). This critique
document records cx's findings as delivered; several of the "FAIL"
verdicts below (items 1, 4, 5 in the nine-item table) are resolved by the
re-persist rather than needing new peer work — see the corrected v5.md for
which is which.

## Nine-item closure table (as delivered)

| Required correction | Result | Resolved by re-persist, or real gap? |
|---|---|---|
| 1. Complete tool-catalog schema and migration mapping | FAIL | **Resolved by re-persist** — the real schema/table existed in ag's raw response |
| 2. Disposition every `peers.json` consumer and deferred state | FAIL | **Real gap** — deferred-state rule is substantively wrong (see below) |
| 3. Strip AI logic from retained Python modules | PARTIAL | **Real gap** — `manage.py`/`launcher.py` concrete, `virtualizer.py`/`scrubber.py`/`config.py`/`check_config.py` still vague |
| 4. Repair acceptance paths and name test dispositions | FAIL | **Resolved by re-persist** — the real 5-row table existed in ag's raw response |
| 5. Add full per-increment and final-suite commands | FAIL | **Partially resolved by re-persist** (per-increment commands now present); full-suite `--all`/`--full` gate still genuinely missing |
| 6. Reconcile Increment A statusline/hooks scope | PARTIAL | **Real gap** — statusline resolved, `_sys/hooks/**` never dispositioned |
| 7. Restore concrete uninstall design and tests | FAIL | **Real gap** — principle-level only, no command route/journal/receipt schema |
| 8. Correct DIR-002 and add directive-service receipt gate | PASS | Genuinely closed |
| 9. Resolve Gate 7 builder/validator ambiguity | PASS | Genuinely closed |

## Real content gaps (independent of the re-persist), all terminal-verified

**Deferred-state migration rule is wrong.** v5 said AI-CLI deferred keys
get filtered out because AI CLIs are "now PeerHub-owned" — but Engram
still owns AI-CLI *installation/update* (v5 itself retains and rewrites
`ensure_peer_cli()` for exactly this); only *invocation/collaboration* is
PeerHub's. Dropping deferred Claude/Codex/Agy install-retry records would
lose real state. Terminal-verified real deferred entries carry `kind`,
`name`, `version`, `attempts`, `first_failed_at`/`last_failed_at`,
`last_exit_code` (`provisioner.py:879-895`, confirmed exact). Also, the
proposed destination path (`_sys/state/deferred_tools.json`) doesn't match
the established convention — terminal-verified real state lives at
`_sys/data/state` (`provisioner.py:1050-1052`, `manage.py:38-40`, both
confirmed exact).

**Several "keep-generic-only" dispositions are still too vague to
implement against**: `virtualizer.py` needs `_load_peers()` and the legacy
fallback at `:13-20,349-400` named explicitly; `scrubber.py` needs
`_load_peers()` and per-peer cleanup at `:48-55,269-281` named; `config.py`
needs BOTH `get_peers_config()` AND `get_orchestration_config()`
(`:159-169`) named, not just the former; `check_config.py` is
"overwhelmingly an AI orchestration validator" (loads protocol/
orchestration/peers/routing/lifecycle configs at `:39-61`, validates peer
shapes at `:341-349`) and needs an explicit delete-vs-replace decision, not
"keep-generic-only."

**`_sys/hooks/**` was never dispositioned** — only the Claude
`PreToolUse` *registration* (in `settings.json`) was addressed; the real
hook-file tree (`ai_check.py`/`ctx_end.py`/`ctx_save.py`/
`memory_compactor.py`/`raw_log.py` + `.bat` entrypoints) needs its own
explicit delete list.

**Uninstall is still principle-only.** v5 says AI CLIs don't survive
uninstall and the Node/npm subtree is deleted wholesale — a real decision
— but supplies no command route (current `engram.cmd`'s dispatch table has
no uninstall route today, verified at `:32-47`), no implementation file/
function, no owned-artifact inventory, no receipt/journal schema, no
failure/retry semantics. A proposed test filename isn't a design.

## What's genuinely closed

DIR-002's binding correctly marked `PENDING` for both `cc` and `cx`, with
the correct real-evidence citation (PeerHub's actual Codex adapter
invocation supplies no sandbox flag, differing from the old retired-
launcher evidence). The Increment-D directive-service precondition is
correctly added. Gate 7's builder ambiguity is resolved
(`build_package.py` authoritative, the duplicate deleted, deterministic
internal validation blocking + live `winget validate` relegated to
non-blocking telemetry given its real probe failure). `manage.py`'s
`_workspace_init_legacy` deletion and `launcher.py`'s provider-logic
removal are both concrete and terminal-verified against real line ranges.

## Overall verdict

Not ready for ratification. No new architectural debate needed — four
concrete, scoped document repairs remain (fix the deferred-state rule +
path; replace "keep-generic-only" with exact branches for `virtualizer.py`/
`scrubber.py`/`config.py`/`check_config.py`; disposition `_sys/hooks/**`;
instantiate the real uninstall command/journal/tests) plus a genuine
per-increment full-suite test command. Everything else — architecture,
catalog direction, DIR-002, Gate 7 — holds.
