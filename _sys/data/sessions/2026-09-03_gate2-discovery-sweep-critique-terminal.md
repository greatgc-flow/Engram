# Gate 2 discovery-sweep design — terminal-performed full critique (2026-09-03)

`cx` remains unavailable until 2026-09-07 (see
`reference_cx_session_resume_permanent_failure_2026_09_02` in the
assistant's memory). Per the established substitution precedent (used for
the Engram diet plan's own v8 final ratification) and given this is now the
concrete blocker for Increment D, the terminal performed a full critique
directly against real `peerhub` source rather than waiting further.

## Independently re-verified (not re-trusting the design's own citations)

All read directly from `P:\workspace\peerhub\peerhub\adapters\registry.py`
and `peerhub/core/evidence.py`:

1. `_resolve_executable_path()` is real, at exactly line 128 as cited —
   PATH/PATHEXT search, explicitly avoids `shutil.which` for the documented
   cwd-hijacking reason (line 129 comment).
2. `register_adapter_factory()`'s docstring (lines 92-94) really does say
   "Registration is validated completely before anything is written: a
   rejected call leaves both the factory table and the alias table exactly
   as they were" — confirmed against the actual implementation (lines
   106-125): the `ValueError` raises (already-registered `peer_kind` at
   107-110, alias owned by a different kind at 116-120) both happen *before*
   any mutation of `_adapter_factories`/`_cli_aliases`, and normalization
   loops don't mutate module state either. The safety claim is real, not
   just documented.
3. No `"adapter"` subcommand exists anywhere in `peerhub/cli.py` (grepped
   every `add_parser(...)` call directly) — no naming collision for
   `peerhub adapter discover`.
4. `EvidenceState` (peerhub/core/evidence.py:17-23) is exactly
   `MEASURED`/`ABSENT`/`UNAVAILABLE`/`ERROR` — the design's 5-way
   discriminated result type maps onto it exactly as claimed (two error
   variants, `ManifestInvalidError`/`AliasCollisionError`, both correctly
   collapsing to the single real `ERROR` state — evidence.py has no more
   granular error state to lose fidelity against).
5. `_adapter_factories` really is pre-populated with `fake`/`ag`/`cc`/`cx`
   at module level (lines 46-51), confirming Lane 1's claim that discovery
   never needs to call `register_adapter_factory()` for built-ins.

No fabrication found — the design's own three prior citations plus these
five hold up against the real source.

## One real gap found, not previously flagged

**Lane 1's executable-resolution path is implicitly coupled to "exactly one
profile per built-in adapter," and the design doesn't say so.** The
existing pattern the design points to for Lane 1 is `resolve_peer_target()`
(registry.py:166-214), which is the only current caller of
`_resolve_executable_path()` for a built-in kind. To get from a bare
`cli_name` to an `executable_path`, it must: resolve `peer_kind` via
`_CLI_ALIASES`, instantiate the real adapter, then — without an explicit
`profile_id` — require `len(adapter.descriptor.profiles) == 1` (lines
183-186) or raise `ProfileNotFoundError`, before it can build a dummy
`AdapterRequest`, call `plan_invocation()`, and finally resolve
`plan.argv[0]` through `_resolve_executable_path()`.

Verified today this holds for all three built-ins — `claude_adapter.py`,
`codex_adapter.py`, `agy_adapter.py` each expose exactly one static
`ProfileDescriptor` (`cc.standard`/`cx.standard`/`ag.standard`) as a
1-tuple. So the design's Lane 1 works correctly *today*. But nothing in the
design documents this dependency, and if a future adapter change adds a
second profile to any of the three (a real possibility given this session's
own standing practice of "experiment with deepthink/effort tiers"), reusing
`resolve_peer_target()`/`plan_invocation()` verbatim for discovery would
start raising `ProfileNotFoundError` instead of correctly returning
`AdapterFoundAndReady` — the discovery sweep would silently misreport a
present, working CLI as `AdapterNotFound` or crash, purely because of an
unrelated profile-count change elsewhere.

**Required addition, non-blocking for design ratification** (same
treatment v8's own critique gave its one follow-up): when Lane 1 is
implemented, either (a) resolve the executable path without going through
profile selection at all — e.g. add a profile-agnostic accessor, since the
discovery sweep only needs *an* executable name from the adapter, not a
fully profile-scoped invocation plan — or (b) if `resolve_peer_target()` is
reused as-is, explicitly pass a `profile_id` (the adapter's first/default
profile) rather than relying on the implicit single-profile shortcut, so a
future multi-profile adapter doesn't silently break discovery. Track this
at Increment D implementation time, not before.

## Verdict: RATIFY

The design is sound, its cited facts are real, and its safety-critical
claim (collision-safe registry binding) is independently confirmed against
the actual implementation, not just its docstring. One real robustness gap
found and tracked as a non-blocking implementation-time requirement. Gate
2's discovery-sweep half is ready for Increment D to build on.
