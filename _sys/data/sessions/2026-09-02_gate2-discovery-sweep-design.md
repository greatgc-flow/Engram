# Gate 2 discovery-sweep design (ag.deepthink, 2026-09-03)

Design for Gate 2's remaining open half — the AI-CLI discovery sweep
(the contract-mapping half was already resolved by reusing
`PHASE1-MANIFEST-SCHEMA-V2`).

Terminal-verified: `_resolve_executable_path()` confirmed exactly at
`peerhub/adapters/registry.py:128`; grep confirms no `"adapter"`
subcommand exists anywhere in `peerhub/cli.py` — no naming collision.

## 1. Two-lane discovery model

**Lane 1 — bounded built-in PATH resolution**: for the 3 known aliases
(`claude`/`cc`, `codex`/`cx`, `agy`/`ag`), uses the existing
`_resolve_executable_path()` pattern (safe PATH/PATHEXT search, no
cwd-hijacking) — no manifest lookup for these, since their contracts
already exist as `RealClaudeAdapter`/`RealCodexAdapter`/`RealAgyAdapter`.

**Lane 2 — trusted-manifest discovery for third parties**: scans exactly
one machine-local trusted directory,
`%LOCALAPPDATA%\PeerHub\adapters.d` (per the earlier gate-2 critique and
deferred-shims design — machine fact, not workspace-local risk), parsing
`.json` files as `PHASE1-MANIFEST-SCHEMA-V2` declarations.

## 2. Discriminated result-type set

Maps onto PeerHub's real `EvidenceState` vocabulary
(`peerhub/core/evidence.py`):

- `AdapterFoundAndReady(peer_kind, executable_path, profiles)` →
  `MEASURED`.
- `AdapterNotReady(peer_kind, executable_path, reason)` → `UNAVAILABLE`
  (found but failed its readiness probe).
- `AdapterNotFound(peer_kind)` → `ABSENT`.
- `ManifestInvalidError(manifest_path, reason)` → `ERROR` (schema
  validation failure).
- `AliasCollisionError(manifest_path, colliding_alias, owner_kind)` →
  `ERROR` (caught during registry binding).

## 3. Registry-binding mechanism — the previously-unsolved piece

**Lane 1**: built-in kinds are already populated in `registry.py`'s
mutable `_adapter_factories` at import time — discovery **never** calls
`register_adapter_factory()` for these. It just runs
`_resolve_executable_path()` + the readiness probe and emits
`AdapterFoundAndReady`/`AdapterNotReady`/`AdapterNotFound`.

**Lane 2**: for each schema-valid manifest that resolves its executable,
extract `peer_kind`/`cli_aliases`, construct a zero-argument
`AdapterFactory` closure capturing the parsed manifest dict (resolving the
manifest's declared `engine_id` — e.g. `builtin:json-claude-v1` — at
instantiation time), then call
`register_adapter_factory(peer_kind, cli_aliases, factory)`. If that
raises `ValueError` (a real, already-registered kind/alias — built-in or
a previously-loaded manifest), catch it and emit `AliasCollisionError`
rather than crashing the sweep or polluting the registry.

## 4. CLI surface

`peerhub adapter discover` — verified no naming collision (`adapter` is
not currently a registered subcommand tree anywhere in `cli.py`). Runs
both lanes, applies registry bindings, prints the discriminated outcome
list (human-readable or `--json`) mapped to `MEASURED`/`ABSENT`/
`UNAVAILABLE`/`ERROR`.

## Status

First design pass, one voice. Not yet critiqued or ratified — `cx` is
unavailable until 2026-09-07 (see
`reference_cx_session_resume_permanent_failure_2026_09_02` in the
assistant's memory); a critique pass should happen once it recovers, or
the terminal performs it directly per the established substitution
precedent if the wait is too long.
